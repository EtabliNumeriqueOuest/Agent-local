from typing import Any
import torch
import torch.nn as nn
from torch.utils.data import Dataset



class BilingualDataset(Dataset):

    def __init__(self, ds, tokenizer_src, tokenizer_tgt, source_lang, target_lang, sequence_length) -> None:
        super().__init__()
        self.ds = ds
        self.tokenizer_src = tokenizer_src
        self.tokenizer_tgt = tokenizer_tgt
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.sequence_length = sequence_length

        self.sos_token = torch.Tensor([tokenizer_src.token_to_id("[SOS]")], dtype=torch.int64)
        self.eos_token = torch.Tensor([tokenizer_src.token_to_id("[EOS]")], dtype=torch.int64)
        self.pad_token = torch.Tensor([tokenizer_src.token_to_id("[PAD]")], dtype=torch.int64)
    
    def __len__(self):
        return len(self.ds)
    
    def __getitem__(self, index: Any) -> Any:
        source_target_pair = self.ds[index]
        source_text = source_target_pair["translation"][self.source_lang]
        target_text = source_target_pair["translation"][self.target_lang]

        encode_input_tokens = self.tokenizer_src.encode(source_text).ids
        decode_input_tokens = self.tokenizer_tgt.encode(target_text).ids

        encode_num_padding_tokens = self.sequence_length - len(encode_input_tokens) - 2
        decode_num_padding_tokens = self.sequence_length - len(decode_input_tokens) - 1

        if encode_num_padding_tokens < 0 or decode_num_padding_tokens < 0:
            raise ValueError("Sentence too long for the model. Please increase the sequence length.")
        
        