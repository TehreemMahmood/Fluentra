"""
Shared audio feature extraction for the FluEntra stutter analyzer.

IMPORTANT: training (train_improved.py) and inference (improved_inference.py)
both import `extract_classical` from here, so they can never drift apart. A
mismatch between the features a scaler was fit on and the features fed at
inference silently produces garbage predictions, so it lives in exactly one
audited place.

Feature set (186 dims, classical only - no YAMNet so it runs light in Django):
  - 40 MFCC               mean+std = 80
  - 40 MFCC delta         mean+std = 80
  - spectral contrast (7) mean+std = 14
  - spectral bandwidth    mean+std = 2
  - spectral flatness     mean+std = 2
  - spectral centroid     mean+std = 2
  - spectral rolloff      mean+std = 2
  - zero-crossing rate    mean+std = 2
  - RMS energy            mean+std = 2
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

SAMPLE_RATE = 16000
CLIP_DURATION_SEC = 3.0
N_MFCC = 40

# classical-only set
FEATURE_DIM = 186
FEATURE_SET = "classical_v2_mfcc40_delta_contrast"

# classical + YAMNet embedding (1024) set
YAMNET_DIM = 1024
FEATURE_DIM_YAMNET = FEATURE_DIM + YAMNET_DIM          # 1210
FEATURE_SET_YAMNET = "classical_v2_plus_yamnet"
YAMNET_HANDLE = "https://tfhub.dev/google/yamnet/1"

# classical + wav2vec2 embedding (768) set  (speech self-supervised)
WAV2VEC2_MODEL = "facebook/wav2vec2-base-960h"
W2V2_DIM = 768
FEATURE_DIM_W2V2 = FEATURE_DIM + W2V2_DIM              # 954
FEATURE_SET_W2V2 = "classical_v2_plus_wav2vec2"

# mode -> (feature_set name, dim)
MODES = {
    "classical": (FEATURE_SET, FEATURE_DIM),
    "yamnet": (FEATURE_SET_YAMNET, FEATURE_DIM_YAMNET),
    "wav2vec2": (FEATURE_SET_W2V2, FEATURE_DIM_W2V2),
}
# reverse lookup: feature_set name -> mode (used by inference reading config)
FEATURE_SET_TO_MODE = {fs: mode for mode, (fs, _dim) in MODES.items()}


def mode_for_feature_set(feature_set: str) -> str:
    return FEATURE_SET_TO_MODE.get(feature_set, "classical")


def extract_classical(audio_path):
    """Return (features[186], detected_duration_seconds)."""
    import librosa

    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, duration=CLIP_DURATION_SEC)
    detected_dur = len(y) / SAMPLE_RATE if len(y) else 0.0

    target = int(SAMPLE_RATE * CLIP_DURATION_SEC)
    y = np.pad(y, (0, target - len(y))) if len(y) < target else y[:target]

    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    mfcc_delta = librosa.feature.delta(mfccs)
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)        # (7, t)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    flatness = librosa.feature.spectral_flatness(y=y)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y)
    rms = librosa.feature.rms(y=y)

    feats = np.concatenate([
        mfccs.mean(axis=1), mfccs.std(axis=1),                       # 80
        mfcc_delta.mean(axis=1), mfcc_delta.std(axis=1),             # 80
        contrast.mean(axis=1), contrast.std(axis=1),                 # 14
        [bandwidth.mean(), bandwidth.std()],                         # 2
        [flatness.mean(), flatness.std()],                           # 2
        [centroid.mean(), centroid.std()],                           # 2
        [rolloff.mean(), rolloff.std()],                             # 2
        [zcr.mean(), zcr.std()],                                     # 2
        [rms.mean(), rms.std()],                                     # 2
    ])
    return feats.astype(np.float32), detected_dur


@lru_cache(maxsize=1)
def _load_yamnet():
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    import tensorflow_hub as hub

    return hub.load(YAMNET_HANDLE)


def extract_yamnet(audio_path):
    """Return the 1024-d mean YAMNet embedding for a 3s clip."""
    import librosa
    import tensorflow as tf

    y, _sr = librosa.load(audio_path, sr=SAMPLE_RATE, duration=CLIP_DURATION_SEC)
    target = int(SAMPLE_RATE * CLIP_DURATION_SEC)
    y = np.pad(y, (0, target - len(y))) if len(y) < target else y[:target]
    wf = tf.convert_to_tensor(y, dtype=tf.float32)
    _scores, embeddings, _spec = _load_yamnet()(wf)
    return tf.reduce_mean(embeddings, axis=0).numpy().astype(np.float32)


@lru_cache(maxsize=1)
def _load_wav2vec2():
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    import torch
    from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2Model

    fe = Wav2Vec2FeatureExtractor.from_pretrained(WAV2VEC2_MODEL)
    model = Wav2Vec2Model.from_pretrained(WAV2VEC2_MODEL)
    model.eval()
    torch.set_grad_enabled(False)
    return fe, model


def extract_wav2vec2(audio_path):
    """Return the 768-d mean-pooled wav2vec2 last-hidden-state embedding."""
    import librosa
    import torch

    y, _sr = librosa.load(audio_path, sr=SAMPLE_RATE, duration=CLIP_DURATION_SEC)
    target = int(SAMPLE_RATE * CLIP_DURATION_SEC)
    y = np.pad(y, (0, target - len(y))) if len(y) < target else y[:target]

    fe, model = _load_wav2vec2()
    inputs = fe(y, sampling_rate=SAMPLE_RATE, return_tensors="pt")
    with torch.no_grad():
        out = model(inputs["input_values"])
    # mean-pool over the time axis -> (768,)
    return out.last_hidden_state.mean(dim=1).squeeze(0).numpy().astype(np.float32)


def extract_features(audio_path, mode="classical"):
    """Unified entry point. Returns (feature_vector, detected_duration).

    mode="classical" -> 186 classical features
    mode="yamnet"    -> 1210 = 186 classical + 1024 YAMNet (general-audio)
    mode="wav2vec2"  -> 954  = 186 classical + 768 wav2vec2 (speech self-supervised)
    """
    classical, dur = extract_classical(audio_path)
    if mode == "classical":
        return classical, dur
    if mode == "yamnet":
        return np.concatenate([classical, extract_yamnet(audio_path)]).astype(np.float32), dur
    if mode == "wav2vec2":
        return np.concatenate([classical, extract_wav2vec2(audio_path)]).astype(np.float32), dur
    raise ValueError(f"unknown feature mode: {mode}")
