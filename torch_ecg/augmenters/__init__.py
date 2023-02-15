"""
Augmenters for training ECG neural networks
===========================================

Augmenters are used to augment the training data.

.. currentmodule:: torch_ecg.augmenters

.. autosummary::
    :toctree: generated/

    AugmenterManager
    Augmenter
    BaselineWanderAugmenter
    CutMix
    LabelSmooth
    Mixup
    RandomFlip
    RandomMasking
    RandomRenormalize
    StretchCompress
    StretchCompressOffline

"""

from .augmenter_manager import AugmenterManager
from .base import Augmenter
from .baseline_wander import BaselineWanderAugmenter
from .cutmix import CutMix
from .label_smooth import LabelSmooth
from .mixup import Mixup
from .random_flip import RandomFlip
from .random_masking import RandomMasking
from .random_renormalize import RandomRenormalize
from .stretch_compress import StretchCompress, StretchCompressOffline


__all__ = [
    "Augmenter",
    "BaselineWanderAugmenter",
    "CutMix",
    "LabelSmooth",
    "Mixup",
    "RandomFlip",
    "RandomMasking",
    "RandomRenormalize",
    "StretchCompress",
    "StretchCompressOffline",
    "AugmenterManager",
]
