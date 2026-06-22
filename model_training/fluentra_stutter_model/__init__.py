"""FluEntra stutter classifier - self-contained inference package.

Two engines are available:
  - v1 (inference.py):          original 6-class 1110-feature ensemble (YAMNet).
  - v2 (improved_inference.py): improved two-stage binary-fluency + type model
                                (86-feature, no YAMNet). Recommended.
"""

from .inference import StutterModel, analyze_audio, get_model
from .improved_inference import (
    ImprovedStutterModel,
    analyze_audio_v2,
    get_improved_model,
)

__all__ = [
    "StutterModel", "analyze_audio", "get_model",
    "ImprovedStutterModel", "analyze_audio_v2", "get_improved_model",
]
