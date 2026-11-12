import base64
import json
import os
import math
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional, Union
from urllib.parse import urlparse

import requests
import torch
from PIL import Image
from torch import nn
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

class Transformer(nn.Module):
    save_in_root: bool = True
    
    def __init__(
        self,
        model_name_or_path: str = 'llamaindex/vdr-2b-multi-v1',
        processor_name_or_path: Optional[str] = None,
        max_pixels: int = 768 * 28 * 28,
        min_pixels: int = 1 * 28 * 28,
        dimension: int = 2048,
        max_seq_length: Optional[int] = None,
        model_args: Optional[Dict[str, Any]] = None,
        processor_args: Optional[Dict[str, Any]] = None,
        tokenizer_args: Optional[Dict[str, Any]] = None,
        config_args: Optional[Dict[str, Any]] = None,
        cache_dir: Optional[str] = None,
        backend: Literal['torch', 'onnx', 'openvino'] = 'torch',
        **kwargs,
    ) -> None:
        super(Transformer, self).__init__()

        if backend != 'torch':
            raise ValueError(
                f'Backend \'{backend}\' is not supported, please use \'torch\' instead'
            )
        
        self.dimension = dimension
        self.max_pixels = max_pixels
        self.min_pixels = min_pixels
        self.max_seq_length = max_seq_length
        
        # Handle args
        model_kwargs = model_args or {}
        model_kwargs.update(kwargs)

        processor_kwargs = processor_args or {}
        processor_kwargs.update({
            'min_pixels': min_pixels,
            'max_pixels': max_pixels,
            'cache_dir': cache_dir
        })
        
        # Initialize model
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name_or_path,
            cache_dir=cache_dir,
            **model_kwargs
        ).eval()

        # Initialize processor
        self.processor = AutoProcessor.from_pretrained(
            processor_name_or_path or model_name_or_path,
            **processor_kwargs
        )

        # Set padding sides
        self.model.padding_side = "left"
        self.processor.tokenizer.padding_side = "left"

        # Store prompts
        self.document_prompt = "<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n<|im_start|>user\n<|vision_start|><|image_pad|><|vision_end|>What is shown in this image?<|im_end|>\n<|endoftext|>"
        self.query_prompt = "<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n<|im_start|>user\n<|vision_start|><|image_pad|><|vision_end|>Query: %s<|im_end|>\n<|endoftext|>"

        # Try to infer max_seq_length if not provided
        if self.max_seq_length is None:
            if (
                hasattr(self.model, 'config') 
                and hasattr(self.model.config, 'max_position_embeddings')
                and hasattr(self.processor.tokenizer, 'model_max_length')
            ):
                self.max_seq_length = min(
                    self.model.config.max_position_embeddings,
                    self.processor.tokenizer.model_max_length,
                )

    def _smart_resize(self, height: int, width: int) -> tuple[int, int]:
        h_bar = max(28, self._round_by_factor(height, 28))
        w_bar = max(28, self._round_by_factor(width, 28))
        # beta is a linear scale: the pixel count moves by beta², hence the sqrt of the area ratio
        if h_bar * w_bar > self.max_pixels:
            beta = math.sqrt((height * width) / self.max_pixels)
            h_bar = self._floor_by_factor(height / beta, 28)
            w_bar = self._floor_by_factor(width / beta, 28)
        elif h_bar * w_bar < self.min_pixels:
            beta = math.sqrt(self.min_pixels / (height * width))
            h_bar = self._ceil_by_factor(height * beta, 28)
            w_bar = self._ceil_by_factor(width * beta, 28)
        return w_bar, h_bar

    @staticmethod
    def _round_by_factor(number: float, factor: int) -> int:
        return round(number / factor) * factor

    @staticmethod
    def _ceil_by_factor(number: float, factor: int) -> int:
        return math.ceil(number / factor) * factor

    @staticmethod
    def _floor_by_factor(number: float, factor: int) -> int:
        return math.floor(number / factor) * factor

    def _resize_image(self, image: Image.Image) -> Image.Image:
        # resize keeps the PIL mode, so an RGBA scan keeps its alpha channel until the processor converts it to RGB
        new_size = self._smart_resize(image.height, image.width)
        return image.resize(new_size)

    @staticmethod
    def _decode_data_image(data_image_str: str) -> Image.Image:
        header, data = data_image_str.split(',', 1)
        image_data = base64.b64decode(data)
        return Image.open(BytesIO(image_data))

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            result = urlparse(url)
            # Check if scheme and netloc are present and scheme is http/https
            return all([result.scheme in ('http', 'https'), result.netloc])
        except Exception:
            return False

    @staticmethod
    def _is_safe_path(path: str) -> bool:
        try:
            # Convert to absolute path and normalize
            abs_path = os.path.abspath(os.path.normpath(path))
            # Check if file exists and is a regular file (not a directory or special file)
            return os.path.isfile(abs_path)
        except Exception:
            return False

    @staticmethod
    def _load_image_from_url(url: str) -> Image.Image:
        try:
            response = requests.get(
                url, 
                stream=True, 
                timeout=10,  # Add timeout
                headers={'User-Agent': 'Mozilla/5.0'}  # Add user agent
            )
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise ValueError(f"Invalid content type: {content_type}")
            
            # Limit file size (e.g., 10MB)
            content = BytesIO()
            size = 0
            max_size = 10 * 1024 * 1024  # 10MB
            
            for chunk in response.iter_content(chunk_size=8192):
                size += len(chunk)
                if size > max_size:
                    raise ValueError("File too large")
                content.write(chunk)
            
            content.seek(0)
            return Image.open(content)
        except Exception as e:
            raise ValueError(f"Failed to load image from URL: {str(e)}")

    @staticmethod
    def _load_image_from_path(image_path: str) -> Image.Image:
        try:
            # Convert to absolute path and normalize
            abs_path = os.path.abspath(os.path.normpath(image_path))
            
            # Check file size before loading
            file_size = os.path.getsize(abs_path)
            max_size = 10 * 1024 * 1024  # 10MB
            if file_size > max_size:
                raise ValueError("File too large")
            
            with Image.open(abs_path) as img:
                # Make a copy to ensure file handle is closed
                return img.copy()
        except Exception as e:
            raise ValueError(f"Failed to load image from path: {str(e)}")

    @staticmethod
    def _load_image_from_bytes(image_bytes: bytes) -> Image.Image:
        try:
            # Check size
            if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
                raise ValueError("Image data too large")
            
            return Image.open(BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"Failed to load image from bytes: {str(e)}")

    def _process_input(self, texts: List[Union[str, Image.Image, bytes]]) -> tuple[List[str], List[Image.Image]]:
        processed_texts = []
        processed_images = []
        dummy_image = Image.new('RGB', (56, 56))

        for sample in texts:
            if isinstance(sample, str):
                # Check if the string is a valid URL
                if self._is_valid_url(sample):
                    try:
                        img = self._load_image_from_url(sample)
                        processed_texts.append(self.document_prompt)
                        processed_images.append(self._resize_image(img))
                    except Exception as e:
                        # If URL loading fails, treat as regular text
                        processed_texts.append(self.query_prompt % sample)
                        processed_images.append(dummy_image)
                # Check if the string is a valid file path
                elif self._is_safe_path(sample):
                    try:
                        img = self._load_image_from_path(sample)
                        processed_texts.append(self.document_prompt)
                        processed_images.append(self._resize_image(img))
                    except Exception as e:
                        # If image loading fails, treat as regular text
                        processed_texts.append(self.query_prompt % sample)
                        processed_images.append(dummy_image)
                else:
                    # Regular text query
                    processed_texts.append(self.query_prompt % sample)
                    processed_images.append(dummy_image)
            elif isinstance(sample, Image.Image):
                processed_texts.append(self.document_prompt)
                processed_images.append(self._resize_image(sample))
            elif isinstance(sample, bytes):
                try:
                    img = self._load_image_from_bytes(sample)
                    processed_texts.append(self.document_prompt)
                    processed_images.append(self._resize_image(img))
                except Exception as e:
                    # If bytes can't be converted to image, use dummy
                    processed_texts.append(self.document_prompt)
                    processed_images.append(dummy_image)

        return processed_texts, processed_images

    def forward(self, features: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        cache_position = torch.arange(0, features['input_ids'].shape[1])
        inputs = self.model.prepare_inputs_for_generation(
            **features, cache_position=cache_position, use_cache=False
        )

        # ensure inputs are on the same device as the model
        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items() if isinstance(v, torch.Tensor)}

        with torch.no_grad():
            output = self.model(
                **inputs,
                return_dict=True,
                output_hidden_states=True
            )

        embeddings = output.hidden_states[-1][:, -1]
        features['sentence_embedding'] = torch.nn.functional.normalize(
            embeddings[:, :self.dimension], p=2, dim=-1
        )
        return features

    def tokenize(self, texts: List[Union[str, Image.Image, bytes]], padding: str = 'longest') -> Dict[str, torch.Tensor]:
        processed_texts, processed_images = self._process_input(texts)
        
        return self.processor(
            text=processed_texts,
            images=processed_images,
            videos=None,
            padding=padding,
            return_tensors='pt'
        )

    def save(self, output_path: str, safe_serialization: bool = True) -> None:
        """Save the model, tokenizer and processor to the given path."""
        self.model.save_pretrained(output_path, safe_serialization=safe_serialization)
        self.processor.save_pretrained(output_path)

        # Save the configuration
        config = {
            'model_name_or_path': output_path,
            'max_pixels': self.max_pixels,
            'min_pixels': self.min_pixels,
            'dimension': self.dimension,
            'max_seq_length': self.max_seq_length,
        }
        
        config_path = os.path.join(output_path, 'sentence_bert_config.json')
        with open(config_path, 'w') as f:
            json.dump(config, f)

    @staticmethod
    def load(input_path: str) -> 'Transformer':
        """Load a saved model from the given path."""
        # Load configuration
        config_path = os.path.join(input_path, 'sentence_bert_config.json')
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
        else:
            config = {'model_name_or_path': input_path}

        return Transformer(**config)