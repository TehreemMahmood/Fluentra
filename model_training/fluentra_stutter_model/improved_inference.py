"""
Improved two-stage inference for the FluEntra stutter analyzer.
===============================================================

Stage 1 (PRIMARY):  balanced binary fluent-vs-disfluent detector.
                    Its disfluency probability drives the fluency score/rating,
                    which is what the FluEntra app actually consumes.

Stage 2 (SECONDARY): rebalanced type classifier, run only to break the detected
                     disfluency down into the app's 4 buckets (repetition /
                     prolongation / blocking / interjection).

Uses the fast 86-dim classical feature set (no YAMNet), so this can run inside
Django without tensorflow_hub. Emits the exact project-compatible analysis
schema (same shape as the Groq output the app stores on SpeechSession).

Train the underlying models with train_improved.py first.
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
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

_DEFAULT_MODEL_DIR = Path(
    os.environ.get("FLUENTRA_MODEL_DIR", Path(__file__).resolve().parent.parent / "saved_models")
)

SAMPLE_RATE = 16000
CLIP_DURATION_SEC = 3.0
N_MFCC = 40

# events-per-second priors, used only to turn type probabilities into rough counts
DISFLUENCY_RATES = {"SoundRep": 2.0, "WordRep": 1.5, "Prolongation": 0.8, "Block": 0.5, "Interjection": 1.2}
MODEL_TO_APP_BUCKET = {
    "SoundRep": "repetitions", "WordRep": "repetitions",
    "Prolongation": "prolongations", "Block": "blocks", "Interjection": "interjections",
}
RECOMMENDATIONS = {
    "Severe": ["Consider a professional speech-language pathology evaluation.",
               "Practice diaphragmatic breathing before speaking.",
               "Deliberately reduce speaking rate to regain control."],
    "Moderate": ["Fluency-shaping practice may help, especially pacing and breathing.",
                 "Use 'easy onset' to soften the start of words.",
                 "Track progress across sessions to spot improvement."],
    "Mild": ["Mild disfluencies are present; continued light practice helps.",
             "Try 'pausing and phrasing' to keep a comfortable rhythm."],
    "Natural": ["Speech appears largely fluent with minimal disfluency.",
                "Keep up natural speaking habits and periodic practice."],
}


def _extract(audio_path, mode):
    # Single shared extractor so inference features always match training.
    try:
        from .features import extract_features
    except ImportError:
        from features import extract_features
    return extract_features(audio_path, mode=mode)


class ImprovedStutterModel:
    def __init__(self, model_dir=None):
        self.model_dir = Path(model_dir) if model_dir else _DEFAULT_MODEL_DIR
        self._load()

    def _pkl(self, name):
        # joblib.load transparently reads both joblib-compressed and plain
        # pickle files, so model weights can be stored compressed to keep the
        # repo small.
        import joblib
        return joblib.load(self.model_dir / name)

    def _load(self):
        required = ["binary_scaler.pkl", "binary_detector.pkl"]
        missing = [r for r in required if not (self.model_dir / r).exists()]
        if missing:
            raise FileNotFoundError(
                f"Improved models not found in {self.model_dir} (missing {missing}). "
                f"Run train_improved.py first."
            )
        self.binary_scaler = self._pkl("binary_scaler.pkl")
        self.binary_detector = self._pkl("binary_detector.pkl")
        self.bin_classes = list(self.binary_detector.classes_)
        self.disf_idx = self.bin_classes.index("disfluent")

        # type model is optional
        self.type_clf = self.type_scaler = self.type_le = None
        if (self.model_dir / "type_classifier.pkl").exists():
            self.type_clf = self._pkl("type_classifier.pkl")
            self.type_scaler = self._pkl("type_scaler.pkl")
            self.type_le = self._pkl("type_label_encoder.pkl")

        cfg = self.model_dir / "improved_config.json"
        self.config = json.loads(cfg.read_text()) if cfg.exists() else {}
        # match inference features to whatever the saved models were trained on
        mode = self.config.get("feature_mode")
        if not mode:
            try:
                from .features import mode_for_feature_set
            except ImportError:
                from features import mode_for_feature_set
            mode = mode_for_feature_set(self.config.get("feature_set", ""))
        self.feature_mode = mode

    def analyze(self, audio_path, audio_duration=None):
        feats, detected = _extract(audio_path, self.feature_mode)
        duration = float(audio_duration or detected or CLIP_DURATION_SEC)
        x = feats.reshape(1, -1)

        # Stage 1: disfluency probability
        p_disf = float(self.binary_detector.predict_proba(self.binary_scaler.transform(x))[0][self.disf_idx])

        # Stage 2: type breakdown (only meaningful when disfluent)
        type_probs = {}
        if self.type_clf is not None:
            tp = self.type_clf.predict_proba(self.type_scaler.transform(x))[0]
            type_probs = {str(c): float(p) for c, p in zip(self.type_le.classes_, tp)}

        score, rating = self._score(p_disf)
        counts = self._counts(p_disf, type_probs, duration, rating)
        analysis = self._schema(p_disf, type_probs, score, rating, counts, duration)
        return {
            "model": {
                "disfluent_probability": round(p_disf, 4),
                "is_disfluent": p_disf >= 0.5,
                "type_probabilities": type_probs,
                "audio_duration": duration,
            },
            "analysis": analysis,
        }

    @staticmethod
    def _score(p_disf):
        score = max(0.0, min(100.0, 100.0 * (1.0 - p_disf)))
        if score >= 85:
            rating = "Natural"
        elif score >= 70:
            rating = "Mild"
        elif score >= 50:
            rating = "Moderate"
        else:
            rating = "Severe"
        return score, rating

    @staticmethod
    def _counts(p_disf, type_probs, duration, rating):
        # Generate events for any non-Natural rating, scaled by disfluency prob,
        # so counts stay consistent with the fluency rating (no "Moderate but 0 events").
        buckets = {"repetitions": 0, "prolongations": 0, "blocks": 0, "interjections": 0}
        if rating == "Natural" or not type_probs:
            return buckets
        for cls, prob in type_probs.items():
            bucket = MODEL_TO_APP_BUCKET.get(cls)
            if bucket is None:
                continue
            buckets[bucket] += int(p_disf * prob * DISFLUENCY_RATES.get(cls, 0.0) * duration)
        # a non-Natural clip should show at least one event of its dominant type
        if sum(buckets.values()) == 0:
            top = max(type_probs, key=type_probs.get)
            b = MODEL_TO_APP_BUCKET.get(top)
            if b:
                buckets[b] = 1
        return buckets

    @staticmethod
    def _schema(p_disf, type_probs, score, rating, counts, duration):
        def sev(*classes):
            if not type_probs:
                return 0.0
            return round(min(100.0, 100.0 * p_disf * max(type_probs.get(c, 0.0) for c in classes)), 1)

        stuttering_types = [
            {"name": "Repetition", "severity": sev("SoundRep", "WordRep"), "count": counts["repetitions"]},
            {"name": "Prolongation", "severity": sev("Prolongation"), "count": counts["prolongations"]},
            {"name": "Blocking", "severity": sev("Block"), "count": counts["blocks"]},
            {"name": "Interjection", "severity": sev("Interjection"), "count": counts["interjections"]},
        ]
        top_type = max(type_probs, key=type_probs.get) if type_probs else None
        disfluent = rating != "Natural"

        key_issues = []
        if not disfluent:
            key_issues.append("Speech appears fluent.")
        elif rating == "Mild":
            key_issues.append(f"Minor disfluencies detected (disfluency probability {p_disf*100:.0f}%).")
            if top_type:
                key_issues.append(f"Most likely type: {top_type}")
        else:
            key_issues.append(f"Disfluency detected (probability {p_disf*100:.0f}%).")
            if top_type:
                key_issues.append(f"Most likely type: {top_type}")

        detailed = (
            f"Binary fluency detector estimated {p_disf*100:.1f}% likelihood of disfluency over a "
            f"{duration:.1f}s clip, giving a fluency score of {score:.0f}/100 ('{rating}'). "
            + (f"Dominant disfluency type: {top_type}. " if (disfluent and top_type) else "")
            + f"Estimated {sum(counts.values())} disfluency events."
        )

        return {
            "overall_score": round(score, 1),
            "fluency_rating": rating,
            "stuttering_types": stuttering_types,
            "key_issues": key_issues,
            "detailed_analysis": detailed,
            "recommendations": RECOMMENDATIONS.get(rating, RECOMMENDATIONS["Natural"]),
            "analysis_source": "fluentra_local_model_v2",
            "disfluent_probability": round(p_disf * 100, 1),
            "predicted_type": top_type if disfluent else "NoStutteredWords",
        }


@lru_cache(maxsize=1)
def get_improved_model(model_dir=None) -> ImprovedStutterModel:
    return ImprovedStutterModel(model_dir)


def analyze_audio_v2(audio_path, model_dir=None, audio_duration=None) -> dict:
    return get_improved_model(model_dir).analyze(audio_path, audio_duration=audio_duration)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python improved_inference.py <audio_file>")
        raise SystemExit(1)
    print(json.dumps(analyze_audio_v2(sys.argv[1]), indent=2))
