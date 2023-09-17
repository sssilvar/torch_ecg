"""
wav2vec2 does not exists in torchaudio before version 0.9
"""

from . import utils
from .model import (
    HuBERTPretrainModel,
    Wav2Vec2Model,
    hubert_base,
    hubert_large,
    hubert_pretrain_base,
    hubert_pretrain_large,
    hubert_pretrain_model,
    hubert_pretrain_xlarge,
    hubert_xlarge,
    wav2vec2_base,
    wav2vec2_large,
    wav2vec2_large_lv60k,
    wav2vec2_model,
)

__all__ = [
    "Wav2Vec2Model",
    "HuBERTPretrainModel",
    "wav2vec2_model",
    "wav2vec2_base",
    "wav2vec2_large",
    "wav2vec2_large_lv60k",
    "hubert_base",
    "hubert_large",
    "hubert_xlarge",
    "hubert_pretrain_model",
    "hubert_pretrain_base",
    "hubert_pretrain_large",
    "hubert_pretrain_xlarge",
    "utils",
]
