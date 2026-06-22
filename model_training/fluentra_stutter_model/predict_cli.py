"""
Command-line demo for the FluEntra stutter classifier.

Usage:
    python predict_cli.py path/to/audio.wav
    python predict_cli.py path/to/audio.wav --json     # raw project payload only
    python predict_cli.py path/to/folder/               # batch over a folder

This prints both the raw model report and the project-compatible analysis
payload (the exact JSON the Django app would store on a SpeechSession).
"""

import sys
import os
import glob
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inference import analyze_audio  # noqa: E402

AUDIO_EXTS = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".webm")


def _print_human(path, result):
    m = result["model"]
    a = result["analysis"]
    print("\n" + "=" * 64)
    print(f"FILE: {os.path.basename(path)}")
    print("=" * 64)
    print(f"  Predicted type : {m['predicted_type']}  ({m['confidence']*100:.1f}% confidence)")
    print(f"  Fluency score  : {a['overall_score']}/100  ->  {a['fluency_rating']}")
    print(f"  Duration       : {m['audio_duration']:.1f}s")
    print("\n  All class probabilities:")
    for cls, p in sorted(m["probabilities"].items(), key=lambda kv: kv[1], reverse=True):
        bar = "#" * int(p * 30)
        print(f"    {cls:18} {p*100:5.1f}%  {bar}")
    print("\n  Project dysfluency buckets (-> SpeechSession fields):")
    for t in a["stuttering_types"]:
        print(f"    {t['name']:14} count={t['count']:<3} severity={t['severity']}")
    print(f"\n  Key issues: {', '.join(a['key_issues'])}")


def main():
    ap = argparse.ArgumentParser(description="FluEntra stutter classifier demo")
    ap.add_argument("path", help="audio file or folder")
    ap.add_argument("--json", action="store_true", help="print only the project payload JSON")
    args = ap.parse_args()

    if os.path.isdir(args.path):
        files = [f for f in sorted(glob.glob(os.path.join(args.path, "*")))
                 if f.lower().endswith(AUDIO_EXTS)]
    else:
        files = [args.path]

    if not files:
        print("No audio files found.")
        raise SystemExit(1)

    for f in files:
        try:
            result = analyze_audio(f)
        except Exception as e:  # noqa: BLE001
            print(f"[error] {f}: {e}")
            continue
        if args.json:
            print(json.dumps(result["analysis"], indent=2))
        else:
            _print_human(f, result)


if __name__ == "__main__":
    main()
