# Fluentra — Stutter Detection Model Training

This directory contains the **machine-learning component** of Fluentra: a stutter /
dysfluency detection model trained from scratch on public stuttering speech
datasets, evaluated honestly, and wrapped in a bridge that plugs into the Django
app.

> **How the ML relates to the live app.** Fluentra's deployed demo performs its
> speech analysis through a speech-to-text + LLM API for reliability. *In
> parallel*, we trained our own audio model (this folder) and built an
> integration layer (`fluentra_stutter_model/django_integration.py`) so the app
> can run on our own model instead of the API. Both paths produce the **same
> analysis schema** the app stores, so the model is a drop-in alternative.

## Contents

```
model_training/
├── notebooks/
│   └── stutter_model_training.ipynb   # full EDA → feature extraction → training → evaluation
├── fluentra_stutter_model/            # reusable inference + training package
│   ├── features.py                    # shared feature extractor (classical / YAMNet / wav2vec2)
│   ├── train_improved.py              # builds labels, trains binary + type models, writes metrics
│   ├── improved_inference.py          # two-stage engine (binary fluency + type breakdown)
│   ├── inference.py                   # original 6-class ensemble engine
│   ├── benchmark_v2.py                # cross-dataset evaluation
│   ├── django_integration.py          # bridge into main/views.py (project-compatible JSON)
│   ├── predict_cli.py                 # command-line demo
│   └── requirements-ml.txt
├── deep_wav2vec_pipeline.py           # wav2vec2 encoder + CNN/BiLSTM head (deep pipeline)
├── results/                           # metrics + confusion matrices (evidence)
└── saved_models/                      # trained weights (small ones; large ones regenerable)
```

## Datasets

Trained on public, labelled stuttering speech corpora (not redistributed here):

- **SEP-28k** — 28k+ labelled 3-second clips, per-annotator vote counts for
  Prolongation / Block / SoundRep / WordRep / Interjection / NoStutteredWords.
- **SEP-28k (Extended/Maintained)**, **UCLASS_2**, and a folder-organised
  **Stammering Detection** set, used for combined training and cross-dataset
  generalisation testing.

Binary labels follow the field-standard convention: a label is "present" when
≥2 of 3 annotators agree; ambiguous / poor-audio / no-speech clips are dropped.

## Approach & results (honest)

The project explored two framings:

**1. 6-class stutter-type classification** (`inference.py`, notebook).
40-MFCC + spectral + YAMNet features (1110-d), NN + Random Forest + SVM ensemble.
Reached ~75% raw accuracy but only **~48–52% balanced accuracy** — it rode the
dominant `NoStutteredWords` class and generalised poorly (~27% on a different
dataset). See `results/confusion_matrix_nn.png`, `results/model_performance_report.csv`.

**2. Binary fluent-vs-disfluent detection** (`improved_inference.py`) — the
framing that matches what the app actually needs (a fluency score). This is the
recommended model.

| Feature set | Balanced accuracy | ROC-AUC | Cross-dataset disfluent recall |
|---|---|---|---|
| 86 classical (MFCC + spectral) | 65.1% | 71.7 | — |
| 186 classical (+ delta + contrast/flatness/RMS) | 66.7% | 73.4 | 71.3% |
| 186 classical + YAMNet (1210-d) | 68.4% | 75.3 | 59.3% (overfit to source) |
| **186 classical + wav2vec 2.0 (954-d) — DEFAULT** | **77.9%** | **85.6** | **66.7%** |

Key findings:
- **wav2vec 2.0 (speech self-supervised) is the deployed default** — a large,
  reliable jump to **77.9% balanced accuracy / 0.856 ROC-AUC**, approaching the
  ~85% inter-annotator ceiling, while keeping solid cross-dataset recall (66.7%).
  Best binary classifier on these features was Logistic Regression.
- **YAMNet** (general-audio embeddings) improved in-distribution accuracy a little
  but **hurt** cross-dataset transfer (59.3%) — it over-fit the source dataset.
  wav2vec2, being speech-specific, did not.
- The 186-feature **classical** model is a lightweight fallback (no PyTorch needed).
- **Type classification** (which of the 5 stutter types) also improved with
  wav2vec2 — accuracy ~42.8%, macro-F1 ~34.9% (up from ~28%) — but remains the
  harder task and is reported as an *indicative* secondary output, not a
  definitive diagnosis.

A SEP-28k binary detector is inherently bounded by inter-annotator disagreement
(~85% ceiling), so metrics are reported with balanced accuracy + ROC-AUC +
confusion matrices rather than a single inflated number.

## Reproduce

```bash
pip install -r fluentra_stutter_model/requirements-ml.txt

# train the binary + type models (point at the SEP-28k dataset; features cache)
python fluentra_stutter_model/train_improved.py --max-per-class 7000

# cross-dataset evaluation
python fluentra_stutter_model/benchmark_v2.py

# analyse a single clip -> project-compatible JSON
python -c "from fluentra_stutter_model import analyze_audio_v2, json; \
import json; print(json.dumps(analyze_audio_v2('clip.wav')['analysis'], indent=2))"
```

> The wav2vec2 binary detector + scalers + the (compressed) type classifier are
> committed, so inference works out of the box. Only the legacy 6-class
> ensemble's large `stutter_rf_model.pkl` (~17 MB) and duplicate `.pkl` weights
> are excluded — rerun `train_improved.py` / the notebook to regenerate them.
> Running the default wav2vec2 model downloads the ~360 MB `wav2vec2-base` model
> on first use and needs PyTorch (see `requirements-ml.txt`).

## Integration with the Django app

`fluentra_stutter_model/django_integration.py` exposes `analyze_session(audio_path)`
which returns the exact JSON shape (`overall_score`, `fluency_rating`,
`stuttering_types[]`) that `main/views.py` already stores on a `SpeechSession`.
Switching the app from the API to this model is a few lines (documented at the
top of that file). It is intentionally left unwired so the live demo stays on the
API path.
