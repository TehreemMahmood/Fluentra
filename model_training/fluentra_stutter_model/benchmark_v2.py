"""
Quick cross-dataset sanity benchmark for the improved (v2) model.

The honest in-distribution metrics come from train_improved.py's held-out test
split (see training_artifacts/improved_metrics.json). This script is a
complementary cross-dataset check: it runs the v2 engine on the folder-based
Stammering Detection dataset (all clips are disfluent) to measure how often the
binary detector correctly flags disfluency on data from a different source.
"""

import sys
import os
import glob
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from improved_inference import get_improved_model  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER_DS = os.path.join(ROOT, "fyp downloads", "Fluentra_datasets", "Stammering Detection")


def main(n_per_folder=30):
    random.seed(0)
    model = get_improved_model()
    folders = ["Block", "Prolongation", "SoundRep", "WordRep", "Interjection"]

    print("Cross-dataset check on 'Stammering Detection' (all DISFLUENT):")
    print(f"{'Folder':<14} {'flagged disfluent':<18} {'avg P(disfluent)'}")
    print("-" * 50)
    total_correct = total = 0
    for folder in folders:
        files = glob.glob(os.path.join(FOLDER_DS, folder, "*.wav"))
        random.shuffle(files)
        files = files[:n_per_folder]
        if not files:
            continue
        flagged = 0
        psum = 0.0
        for f in files:
            try:
                r = model.analyze(f)
            except Exception as e:
                print(f"  err {f}: {e}")
                continue
            p = r["model"]["disfluent_probability"]
            psum += p
            if r["model"]["is_disfluent"]:
                flagged += 1
            total += 1
            total_correct += int(r["model"]["is_disfluent"])
        print(f"{folder:<14} {flagged}/{len(files):<16} {psum/len(files):.2f}")
    print("-" * 50)
    if total:
        print(f"Disfluent recall (cross-dataset): {total_correct}/{total} = {100*total_correct/total:.1f}%")


if __name__ == "__main__":
    main()
