"""
FluEntra Stutter Classifier - Self-contained inference engine.
================================================================

This module loads the trained stutter-type classifier (Neural Network +
Random Forest + SVM weighted ensemble) and turns any audio file into:

  1. A rich model report   -> predicted_type, confidence, per-class probabilities
  2. A PROJECT-COMPATIBLE   -> the exact JSON schema the FluEntra Django app
     analysis payload           already stores on `SpeechSession`
                                (overall_score, fluency_rating, stuttering_types[]...)

It has ZERO dependency on Django, so it can be:
  - run standalone (see predict_cli.py),
  - imported into a notebook,
  - or dropped into the Django app later (see django_integration.py).

The feature pipeline is replicated EXACTLY from the training notebook so the
saved StandardScaler receives the 1110-dim vectors it was fitted on
(86 classical features + 1024 YAMNet embedding). Any deviation here silently
produces garbage predictions, which is why it lives in one audited place.

Author: FluEntra FYP team
"""

from __future__ import annotations

import os
import json
import pickle
import warnings
from pathlib import Path
from functools import lru_cache

import numpy as np

warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")  # silence TF chatter

# --------------------------------------------------------------------------- #
# Paths & constants
# --------------------------------------------------------------------------- #
# By default we look for saved_models/ as a sibling of this package's parent
# (i.e. the FYP-02 root). Override with FLUENTRA_MODEL_DIR if you move things.
_DEFAULT_MODEL_DIR = Path(
    os.environ.get(
        "FLUENTRA_MODEL_DIR",
        Path(__file__).resolve().parent.parent / "saved_models",
    )
)

SAMPLE_RATE = 16000
CLIP_DURATION_SEC = 3.0
N_MFCC = 40
EXPECTED_FEATURES = 1110  # 86 classical + 1024 YAMNet
YAMNET_HANDLE = "https://tfhub.dev/google/yamnet/1"

# Ensemble weights (mirrors saved_models/ensemble_config.pkl).
DEFAULT_ENSEMBLE_WEIGHTS = {"nn": 0.4, "rf": 0.35, "svm": 0.25}

# How severe each detected class is, used for the fluency score (0-100).
# Mirrors calculate_fluency_score() in the training notebook.
SEVERITY_WEIGHTS = {
    "NoStutteredWords": 0.0,
    "Interjection": 5.0,
    "SoundRep": 15.0,
    "WordRep": 15.0,
    "Prolongation": 20.0,
    "Block": 25.0,
}

# Rough events-per-second priors used to turn probabilities into counts.
DISFLUENCY_RATES = {
    "SoundRep": 2.0,
    "WordRep": 1.5,
    "Prolongation": 0.8,
    "Block": 0.5,
    "Interjection": 1.2,
}

# Maps the model's 6 classes onto the 4 dysfluency buckets the Django app
# stores (repetitions_count / prolongations_count / blocks_count /
# interjections_count). SoundRep + WordRep both count as repetitions.
MODEL_TO_APP_BUCKET = {
    "SoundRep": "repetitions",
    "WordRep": "repetitions",
    "Prolongation": "prolongations",
    "Block": "blocks",
    "Interjection": "interjections",
    "NoStutteredWords": None,
}

RECOMMENDATIONS = {
    "Severe": [
        "Consider a professional speech-language pathology evaluation.",
        "Practice diaphragmatic breathing before speaking.",
        "Deliberately reduce speaking rate to regain control.",
    ],
    "Moderate": [
        "Fluency-shaping practice may help, especially pacing and breathing.",
        "Use 'easy onset' to soften the start of words.",
        "Track progress across sessions to spot improvement.",
    ],
    "Mild": [
        "Mild disfluencies are present; continued light practice helps.",
        "Try 'pausing and phrasing' to keep a comfortable rhythm.",
    ],
    "Natural": [
        "Speech appears largely fluent with minimal disfluency.",
        "Keep up natural speaking habits and periodic practice.",
    ],
}


# --------------------------------------------------------------------------- #
# Lazy-loaded heavy resources (TF / models loaded once per process)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _load_yamnet():
    import tensorflow_hub as hub  # imported lazily so the module is importable without TF

    return hub.load(YAMNET_HANDLE)


class StutterModel:
    """Loads the ensemble once and exposes analyze()."""

    def __init__(self, model_dir: str | os.PathLike | None = None):
        self.model_dir = Path(model_dir) if model_dir else _DEFAULT_MODEL_DIR
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"Model directory not found: {self.model_dir}. "
                f"Set FLUENTRA_MODEL_DIR or pass model_dir=..."
            )
        self._load_artifacts()

    # -- loading -------------------------------------------------------------
    def _pkl(self, name):
        with open(self.model_dir / name, "rb") as f:
            return pickle.load(f)

    def _load_artifacts(self):
        import keras

        self.scaler = self._pkl("scaler.pkl")
        self.label_encoder = self._pkl("label_encoder.pkl")
        self.classes = [str(c) for c in self.label_encoder.classes_]

        self.nn_model = keras.models.load_model(
            self.model_dir / "fluentrra_stutter_classifier.h5", compile=False
        )
        self.rf_model = self._pkl("stutter_rf_model.pkl")
        self.svm_model = self._pkl("stutter_svm_model.pkl")

        cfg_path = self.model_dir / "ensemble_config.pkl"
        if cfg_path.exists():
            cfg = self._pkl("ensemble_config.pkl")
            self.weights = cfg.get("weights", DEFAULT_ENSEMBLE_WEIGHTS)
        else:
            self.weights = DEFAULT_ENSEMBLE_WEIGHTS

        n_in = getattr(self.scaler, "n_features_in_", EXPECTED_FEATURES)
        if n_in != EXPECTED_FEATURES:
            warnings.warn(
                f"Scaler expects {n_in} features but pipeline produces "
                f"{EXPECTED_FEATURES}. Predictions may be unreliable."
            )

    # -- feature extraction (EXACT replica of the training notebook) ---------
    @staticmethod
    def _classical_features(waveform, sr):
        import librosa

        mfccs = librosa.feature.mfcc(y=waveform, sr=sr, n_mfcc=N_MFCC)
        mfcc_mean = np.mean(mfccs, axis=1)
        mfcc_std = np.std(mfccs, axis=1)

        zcr = librosa.feature.zero_crossing_rate(waveform)
        sc = librosa.feature.spectral_centroid(y=waveform, sr=sr)
        ro = librosa.feature.spectral_rolloff(y=waveform, sr=sr)

        return np.concatenate(
            [
                mfcc_mean,
                mfcc_std,
                [np.mean(zcr), np.std(zcr)],
                [np.mean(sc), np.std(sc)],
                [np.mean(ro), np.std(ro)],
            ]
        )  # -> 86 features

    def _extract_features(self, audio_path):
        import librosa
        import tensorflow as tf

        waveform, sr = librosa.load(audio_path, sr=SAMPLE_RATE, duration=CLIP_DURATION_SEC)
        target = int(SAMPLE_RATE * CLIP_DURATION_SEC)
        if len(waveform) < target:
            waveform = np.pad(waveform, (0, target - len(waveform)))
        else:
            waveform = waveform[:target]

        classical = self._classical_features(waveform, sr)  # 86

        yamnet = _load_yamnet()
        wf = tf.convert_to_tensor(waveform, dtype=tf.float32)
        _scores, embeddings, _spec = yamnet(wf)
        yamnet_embedding = tf.reduce_mean(embeddings, axis=0).numpy()  # 1024

        combined = np.concatenate([classical, yamnet_embedding])  # 1110
        return combined, len(waveform) / SAMPLE_RATE

    # -- ensemble prediction -------------------------------------------------
    def _predict_probs(self, features):
        X = self.scaler.transform(features.reshape(1, -1))

        nn_probs = self.nn_model.predict(X, verbose=0)[0]
        rf_probs = self.rf_model.predict_proba(X)[0]
        svm_probs = self.svm_model.predict_proba(X)[0]

        w = self.weights
        combined = w["nn"] * nn_probs + w["rf"] * rf_probs + w["svm"] * svm_probs
        combined = combined / combined.sum()
        return combined

    # -- public API ----------------------------------------------------------
    def analyze(self, audio_path, audio_duration=None):
        """Analyze one audio file.

        Returns a dict with two halves:
          - 'model'   : raw model report (predicted_type, confidence, probabilities)
          - 'analysis': FluEntra project-compatible payload (drop-in for Groq output)
        """
        features, detected_duration = self._extract_features(audio_path)
        duration = float(audio_duration or detected_duration or CLIP_DURATION_SEC)

        probs = self._predict_probs(features)
        prob_map = {cls: float(p) for cls, p in zip(self.classes, probs)}
        pred_idx = int(np.argmax(probs))
        predicted_type = self.classes[pred_idx]
        confidence = float(probs[pred_idx])

        score, rating = self._fluency_score(prob_map)
        counts = self._counts(prob_map, duration)

        analysis = self._to_project_schema(
            prob_map, predicted_type, confidence, score, rating, counts, duration
        )

        return {
            "model": {
                "predicted_type": predicted_type,
                "confidence": confidence,
                "probabilities": prob_map,
                "audio_duration": duration,
            },
            "analysis": analysis,
        }

    # -- scoring helpers (mirror the notebook) -------------------------------
    @staticmethod
    def _fluency_score(prob_map):
        score = 100.0
        for stutter_type, prob in prob_map.items():
            score -= prob * SEVERITY_WEIGHTS.get(stutter_type, 0.0)
        score = max(0.0, min(100.0, score))

        if score >= 85:
            rating = "Natural"      # app uses "Natural" (notebook said "Normal")
        elif score >= 70:
            rating = "Mild"
        elif score >= 50:
            rating = "Moderate"
        else:
            rating = "Severe"
        return score, rating

    @staticmethod
    def _counts(prob_map, duration):
        """Bucketed disfluency counts in the app's 4 categories."""
        buckets = {"repetitions": 0, "prolongations": 0, "blocks": 0, "interjections": 0}
        for cls, prob in prob_map.items():
            bucket = MODEL_TO_APP_BUCKET.get(cls)
            if bucket is None:
                continue
            rate = DISFLUENCY_RATES.get(cls, 0.0)
            buckets[bucket] += int(prob * rate * duration)
        return buckets

    @staticmethod
    def _to_project_schema(prob_map, predicted_type, confidence, score, rating, counts, duration):
        """Build the EXACT JSON the Django app expects from its analyzer.

        Mirrors main/views.py: the app reads stuttering_types[].name/.count
        (extract_stutter_counts) and overall_score / fluency_rating.
        """

        def sev(*classes):
            return round(min(100.0, 100.0 * max(prob_map.get(c, 0.0) for c in classes)), 1)

        stuttering_types = [
            {"name": "Repetition", "severity": sev("SoundRep", "WordRep"), "count": counts["repetitions"]},
            {"name": "Prolongation", "severity": sev("Prolongation"), "count": counts["prolongations"]},
            {"name": "Blocking", "severity": sev("Block"), "count": counts["blocks"]},
            {"name": "Interjection", "severity": sev("Interjection"), "count": counts["interjections"]},
        ]

        key_issues = []
        for cls, prob in sorted(prob_map.items(), key=lambda kv: kv[1], reverse=True):
            if cls == "NoStutteredWords" or prob < 0.10:
                continue
            key_issues.append(f"{cls} likelihood {prob * 100:.0f}%")

        total_events = sum(counts.values())
        detailed = (
            f"Trained ensemble model (NN+RF+SVM) classified the dominant pattern as "
            f"'{predicted_type}' with {confidence * 100:.1f}% confidence over a "
            f"{duration:.1f}s clip. Estimated {total_events} disfluency events. "
            f"Overall fluency rated '{rating}' ({score:.0f}/100)."
        )

        return {
            "overall_score": round(score, 1),
            "fluency_rating": rating,
            "stuttering_types": stuttering_types,
            "key_issues": key_issues or ["No significant disfluencies detected."],
            "detailed_analysis": detailed,
            "recommendations": RECOMMENDATIONS.get(rating, RECOMMENDATIONS["Natural"]),
            "analysis_source": "fluentra_local_model",
            "model_confidence": round(confidence * 100, 1),
            "predicted_type": predicted_type,
        }


# --------------------------------------------------------------------------- #
# Convenience module-level API
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def get_model(model_dir: str | None = None) -> StutterModel:
    """Process-wide singleton so the heavy artifacts load only once."""
    return StutterModel(model_dir)


def analyze_audio(audio_path, model_dir: str | None = None, audio_duration=None) -> dict:
    """One-call helper. Returns {'model': ..., 'analysis': ...}."""
    return get_model(model_dir).analyze(audio_path, audio_duration=audio_duration)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python inference.py <audio_file>")
        raise SystemExit(1)
    print(json.dumps(analyze_audio(sys.argv[1]), indent=2))
