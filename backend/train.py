import torch
import torch.nn as nn
from torch.utils.data import Dataset, dataloader, random_split

from datasets import load_dataset
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.trainers import WordLevelTrainer
from tokenizers.pre_tokenizers import Whitespace

from pathlib import Path
# model side: Adam with betas=(0.9, 0.98), eps=1e-9 as in the original transformer paper
# nn.LayerNorm already learns gamma (weight) and beta (bias), no need for a hand-written norm layer



def get_all_sentences(ds, lang):
    for item in ds:
        yield item["translation"][lang]



def get_or_build_tokenizer(config, ds, lang):
    tokenizer_path = Path(config["tokenizer_file"].format(lang))
    if not Path.exists(tokenizer_path):
        print(f"Tokenizer not found at {tokenizer_path}, building it.")
        tokenizer = Tokenizer(WordLevel(unk_token="[UNK]"))
        tokenizer.pre_tokenizer = Whitespace()
        trainer = WordLevelTrainer(special_tokens=["[UNK]", "[PAD]", "[SOS]", "[EOS]"], min_frequency=2)
        tokenizer.train_from_iterator(get_all_sentences(ds, lang), trainer=trainer)
        tokenizer.save(str(tokenizer_path))
    else:
        print(f"Loading tokenizer from {tokenizer_path}")
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
    return tokenizer



def get_ds(config):
    ds_raw = load_dataset(config["opus_books"], f"{config["lang_src"]}-{config["lang_tgt"]}", split="train")

    # Build the tokenizer
    tokenizer_src = get_or_build_tokenizer(config, ds_raw, config["lang_src"])
    tokenizer_tgt = get_or_build_tokenizer(config, ds_raw, config["lang_tgt"])

    # Keep 90% of the dataset for training and 10% for validation
    train_ds_size = int(0.9 * len(ds_raw))
    val_ds_size = len(ds_raw) - train_ds_size
    train_ds_raw, val_ds_raw = random_split(ds_raw, [train_ds_size, val_ds_size])