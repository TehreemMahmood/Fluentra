"""
Improved, project-aligned training for the FluEntra stutter analyzer.
=====================================================================

Why this exists
---------------
The original 6-class model reaches ~75% raw accuracy but only ~48-52% BALANCED
accuracy: it rides the dominant `NoStutteredWords` class and fails on minority
classes. That is the wrong objective for the FluEntra app, which really needs a
**fluency assessment** (a 0-100 score + "is this disfluent?") rather than a
single 6-way type guess.

This script trains what the project actually consumes:

  1. PRIMARY  - a balanced BINARY fluent-vs-disfluent detector.
                Its disfluency probability drives the app's fluency_score and
                fluency_rating. Balanced + honestly evaluated.

  2. SECONDARY - a rebalanced multiclass TYPE model (Block/Prolongation/SoundRep/
                 WordRep/Interjection) used ONLY to break down *which* disfluency,
                 trained with class weights. Reported honestly (macro-F1), not
                 over-claimed.

Both use the fast 86-dim classical feature set (40-MFCC mean/std + ZCR +
spectral centroid + rolloff) - no YAMNet - so inference stays light enough to
run inside Django without tensorflow_hub.

Labels come from SEP-28k annotator vote counts (the field-standard convention:
a label is "present" when >=2 of 3 annotators agree). Ambiguous / poor-audio /
no-speech / music clips are dropped.

Outputs (written to ../saved_models/ and ../training_artifacts/):
  saved_models/binary_scaler.pkl
  saved_models/binary_detector.pkl          (best binary model)
  saved_models/type_scaler.pkl
  saved_models/type_classifier.pkl
  saved_models/type_label_encoder.pkl
  saved_models/improved_config.json
  training_artifacts/binary_features.npz     (feature cache; re-runs are instant)
  training_artifacts/improved_metrics.json
  training_artifacts/binary_confusion_matrix.png
  training_artifacts/type_confusion_matrix.png

Usage:
  python train_improved.py                       # full run (SEP-28k)
  python train_improved.py --max-per-class 5000  # smaller/faster
  python train_improved.py --quick               # tiny smoke test (300/class)
"""

from __future__ import annotations

import os
import json
import time
import pickle
import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

ROOT = Path(__file__).resolve().parent.parent          # D:/Study/FYP-02
SAVED = ROOT / "saved_models"
ARTIFACTS = ROOT / "training_artifacts"
SAVED.mkdir(exist_ok=True)
ARTIFACTS.mkdir(exist_ok=True)

SEP_DIR = ROOT / "fyp downloads" / "Fluentra_datasets" / "SEP_28K"
SEP_LABELS = SEP_DIR / "SEP-28k_labels.csv"
SEP_CLIPS = SEP_DIR / "clips" / "stuttering-clips" / "clips"

SAMPLE_RATE = 16000
CLIP_DURATION_SEC = 3.0
N_MFCC = 40

DISFLUENCY_COLS = ["Prolongation", "Block", "SoundRep", "WordRep", "Interjection"]
VOTE_THRESHOLD = 2          # >=2 of 3 annotators
EXCLUDE_IF_POSITIVE = ["Unsure", "PoorAudioQuality", "DifficultToUnderstand", "Music", "NoSpeech"]


# --------------------------------------------------------------------------- #
# 1. Build clean labels from SEP-28k vote counts
# --------------------------------------------------------------------------- #
def build_label_table(max_per_class: int) -> pd.DataFrame:
    df = pd.read_csv(SEP_LABELS)

    # drop ambiguous / unusable clips
    for col in EXCLUDE_IF_POSITIVE:
        if col in df.columns:
            df = df[df[col] < VOTE_THRESHOLD]

    df["AudioPath"] = df.apply(
        lambda r: str(SEP_CLIPS / f"{r['Show'].strip()}_{int(r['EpId'])}_{int(r['ClipId'])}.wav"),
        axis=1,
    )
    df = df[df["AudioPath"].apply(os.path.exists)].copy()

    disf_max = df[DISFLUENCY_COLS].max(axis=1)
    is_disfluent = disf_max >= VOTE_THRESHOLD
    is_fluent = (df["NoStutteredWords"] >= VOTE_THRESHOLD) & (df[DISFLUENCY_COLS].sum(axis=1) == 0)

    df["binary"] = np.where(is_disfluent, "disfluent", np.where(is_fluent, "fluent", "ambiguous"))
    df = df[df["binary"] != "ambiguous"].copy()

    # primary disfluency type (only meaningful for disfluent rows)
    df["primary_type"] = df[DISFLUENCY_COLS].idxmax(axis=1)
    df.loc[df["binary"] == "fluent", "primary_type"] = "NoStutteredWords"

    # balance the binary classes
    n = min(df["binary"].value_counts().min(), max_per_class)
    balanced = pd.concat([
        df[df["binary"] == "fluent"].sample(n, random_state=42),
        df[df["binary"] == "disfluent"].sample(n, random_state=42),
    ]).reset_index(drop=True)

    print(f"  Usable clips: {len(df)}  | balanced sample: {len(balanced)} ({n}/class)")
    print("  Disfluent type distribution in sample:")
    print(balanced[balanced.binary == "disfluent"]["primary_type"].value_counts().to_string())
    return balanced


# --------------------------------------------------------------------------- #
# 2. Feature extraction (86-dim classical) + cache
# --------------------------------------------------------------------------- #
FEATURE_MODE = "classical"  # set from CLI in main(): classical | yamnet | wav2vec2


def _extract_one(path):
    from features import extract_features

    feats, _dur = extract_features(path, mode=FEATURE_MODE)
    return feats


def extract_features(df: pd.DataFrame, cache_tag: str, checkpoint_every: int = 250):
    """Extract features with a RESUMABLE checkpoint.

    The df row order is deterministic (fixed random_state), so progress is saved
    by row index to a .partial.npz every `checkpoint_every` files. If the process
    is killed (e.g. a long wav2vec2 run gets reaped), simply re-run: it loads the
    partial cache and continues from where it stopped. When all rows are done it
    writes the final cache.
    """
    from features import MODES

    fset, fdim = MODES[FEATURE_MODE]
    n = len(df)
    cache = ARTIFACTS / f"binary_features_{fset}_{cache_tag}.npz"
    partial = ARTIFACTS / f"binary_features_{fset}_{cache_tag}.partial.npz"

    if cache.exists():
        data = np.load(cache, allow_pickle=True)
        if len(data["X"]) == n and data["X"].shape[1] == fdim:
            print(f"  Loaded cached features from {cache.name}")
            return data["X"], data["y_bin"], data["y_type"]

    paths = df["AudioPath"].values
    yb_all = np.asarray(df["binary"].astype(str).tolist())
    yt_all = np.asarray(df["primary_type"].astype(str).tolist())

    # resume from partial if present
    feats = np.zeros((n, fdim), dtype=np.float32)
    ok = np.zeros(n, dtype=bool)
    start = 0
    if partial.exists():
        p = np.load(partial, allow_pickle=True)
        if p["feats"].shape == (n, fdim):
            feats = p["feats"]
            ok = p["ok"]
            start = int(p["done"])
            print(f"  Resuming from checkpoint: {start}/{n} done")

    t0 = time.time()
    for i in range(start, n):
        try:
            feats[i] = _extract_one(paths[i])
            ok[i] = True
        except Exception:
            ok[i] = False
        done = i + 1
        if done % checkpoint_every == 0 or done == n:
            np.savez(partial, feats=feats, ok=ok, done=done)
            el = time.time() - t0
            rate = el / max(1, done - start)
            eta = rate * (n - done) / 60
            print(f"    {done}/{n} features ({el:.0f}s, {rate*1000:.0f} ms/file, ETA {eta:.0f} min)",
                  flush=True)

    X = feats[ok]
    y_bin = yb_all[ok]
    y_type = yt_all[ok]
    np.savez_compressed(cache, X=X, y_bin=y_bin, y_type=y_type)
    try:
        partial.unlink()
    except OSError:
        pass
    print(f"  Extracted {len(X)} feature vectors -> cached {cache.name}")
    return X, y_bin, y_type


# --------------------------------------------------------------------------- #
# 3. Train + evaluate
# --------------------------------------------------------------------------- #
def _confusion_png(cm, labels, title, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        plt.figure(figsize=(7, 6))
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels, yticklabels=labels)
        plt.title(title)
        plt.xlabel("Predicted")
        plt.ylabel("True")
        plt.tight_layout()
        plt.savefig(path, dpi=120)
        plt.close()
        print(f"  Saved {Path(path).name}")
    except Exception as e:
        print(f"  (skipped confusion plot: {e})")


def train_binary(X, y_bin):
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (accuracy_score, balanced_accuracy_score, f1_score,
                                  roc_auc_score, confusion_matrix, classification_report)

    print("\n=== BINARY fluent-vs-disfluent ===")
    Xtr, Xte, ytr, yte = train_test_split(X, y_bin, test_size=0.2, random_state=42, stratify=y_bin)
    scaler = StandardScaler().fit(Xtr)
    Xtr_s, Xte_s = scaler.transform(Xtr), scaler.transform(Xte)

    candidates = {
        "random_forest": RandomForestClassifier(n_estimators=300, max_depth=None,
                                                 min_samples_leaf=2, class_weight="balanced",
                                                 n_jobs=-1, random_state=42),
        "logreg": LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0),
        "grad_boost": GradientBoostingClassifier(random_state=42),
    }

    pos = "disfluent"
    results, best, best_score = {}, None, -1
    for name, clf in candidates.items():
        clf.fit(Xtr_s, ytr)
        pred = clf.predict(Xte_s)
        proba = clf.predict_proba(Xte_s)[:, list(clf.classes_).index(pos)]
        acc = accuracy_score(yte, pred)
        bacc = balanced_accuracy_score(yte, pred)
        f1 = f1_score(yte, pred, pos_label=pos)
        auc = roc_auc_score((yte == pos).astype(int), proba)
        results[name] = {"accuracy": round(acc * 100, 2), "balanced_accuracy": round(bacc * 100, 2),
                         "f1_disfluent": round(f1 * 100, 2), "roc_auc": round(auc * 100, 2)}
        print(f"  {name:14} acc={acc*100:5.2f}%  bal_acc={bacc*100:5.2f}%  F1={f1*100:5.2f}%  AUC={auc*100:5.2f}%")
        if bacc > best_score:
            best_score, best, best_name = bacc, clf, name

    print(f"  -> best binary model: {best_name} (balanced acc {best_score*100:.2f}%)")
    cm = confusion_matrix(yte, best.predict(Xte_s), labels=["fluent", "disfluent"])
    _confusion_png(cm, ["fluent", "disfluent"], "Binary Detector (Test)",
                   ARTIFACTS / "binary_confusion_matrix.png")
    print(classification_report(yte, best.predict(Xte_s)))

    import joblib
    with open(SAVED / "binary_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    # compress the (large) tree model so it stays repo-friendly
    joblib.dump(best, SAVED / "binary_detector.pkl", compress=3)

    return {"best_model": best_name, "positive_label": pos, "candidates": results}


def train_type(X, y_bin, y_type):
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (accuracy_score, balanced_accuracy_score, f1_score,
                                  confusion_matrix, classification_report)

    print("\n=== SECONDARY type classifier (disfluent clips only) ===")
    mask = y_bin == "disfluent"
    Xd, yd = X[mask], y_type[mask]
    if len(np.unique(yd)) < 2 or len(Xd) < 50:
        print("  Not enough disfluent data for a type model; skipping.")
        return None

    le = LabelEncoder().fit(yd)
    y_enc = le.transform(yd)
    Xtr, Xte, ytr, yte = train_test_split(Xd, y_enc, test_size=0.2, random_state=42, stratify=y_enc)
    scaler = StandardScaler().fit(Xtr)
    Xtr_s, Xte_s = scaler.transform(Xtr), scaler.transform(Xte)

    clf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                 class_weight="balanced", n_jobs=-1, random_state=42)
    clf.fit(Xtr_s, ytr)
    pred = clf.predict(Xte_s)
    acc = accuracy_score(yte, pred)
    bacc = balanced_accuracy_score(yte, pred)
    mf1 = f1_score(yte, pred, average="macro")
    print(f"  type model: acc={acc*100:5.2f}%  bal_acc={bacc*100:5.2f}%  macroF1={mf1*100:5.2f}%  "
          f"({len(le.classes_)} classes)")
    cm = confusion_matrix(yte, pred)
    _confusion_png(cm, list(le.classes_), "Type Classifier (disfluent, Test)",
                   ARTIFACTS / "type_confusion_matrix.png")
    print(classification_report(yte, pred, target_names=le.classes_))

    import joblib
    with open(SAVED / "type_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    joblib.dump(clf, SAVED / "type_classifier.pkl", compress=3)
    with open(SAVED / "type_label_encoder.pkl", "wb") as f:
        pickle.dump(le, f)

    return {"classes": list(le.classes_), "accuracy": round(acc * 100, 2),
            "balanced_accuracy": round(bacc * 100, 2), "macro_f1": round(mf1 * 100, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-class", type=int, default=7000)
    ap.add_argument("--quick", action="store_true", help="tiny smoke test (300/class)")
    ap.add_argument("--use-yamnet", action="store_true",
                    help="append 1024-d YAMNet embedding to the 186 classical features")
    ap.add_argument("--use-wav2vec2", action="store_true",
                    help="append 768-d wav2vec2 embedding to the 186 classical features")
    args = ap.parse_args()

    global FEATURE_MODE
    if args.use_wav2vec2:
        FEATURE_MODE = "wav2vec2"
    elif args.use_yamnet:
        FEATURE_MODE = "yamnet"
    else:
        FEATURE_MODE = "classical"
    max_per_class = 300 if args.quick else args.max_per_class
    tag = f"q{max_per_class}" if args.quick else str(max_per_class)
    print(f"  Feature mode: {FEATURE_MODE}")

    print("=" * 70)
    print("FluEntra improved training  (binary fluency + type breakdown)")
    print("=" * 70)
    if not SEP_LABELS.exists():
        raise FileNotFoundError(f"SEP-28k labels not found: {SEP_LABELS}")

    print("\n[1/3] Building balanced labels...")
    df = build_label_table(max_per_class)

    print("\n[2/3] Extracting features (cached after first run)...")
    X, y_bin, y_type = extract_features(df, tag)

    print("\n[3/3] Training...")
    binary_metrics = train_binary(X, y_bin)
    type_metrics = train_type(X, y_bin, y_type)

    from features import MODES

    fset, fdim = MODES[FEATURE_MODE]
    config = {
        "feature_dim": fdim,
        "feature_set": fset,
        "feature_mode": FEATURE_MODE,
        "uses_yamnet": FEATURE_MODE == "yamnet",
        "sample_rate": SAMPLE_RATE,
        "clip_duration_sec": CLIP_DURATION_SEC,
        "vote_threshold": VOTE_THRESHOLD,
        "binary": binary_metrics,
        "type": type_metrics,
        "n_samples": int(len(X)),
    }
    with open(SAVED / "improved_config.json", "w") as f:
        json.dump(config, f, indent=2)
    with open(ARTIFACTS / "improved_metrics.json", "w") as f:
        json.dump(config, f, indent=2)

    print("\n" + "=" * 70)
    print("DONE. Artifacts written to saved_models/ and training_artifacts/")
    print("=" * 70)
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
