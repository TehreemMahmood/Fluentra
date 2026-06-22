# FluEntra Stutter Analyzer — Inference + Training Package

A **self-contained, framework-independent** package that turns any audio file
into the **exact analysis JSON the FluEntra Django app uses**, so the model can
be presented as part of the project and dropped into the live app later —
without coupling the two.

It ships **two engines**:

| Engine | What it is | Use it for |
|---|---|---|
| **v2 (recommended)** | Two-stage: balanced **binary fluent-vs-disfluent** detector drives the fluency score, then a type model breaks it down. 186 classical features, **no YAMNet**. | The project-aligned, honest, generalizing model. |
| v1 (legacy) | Original 6-class 1110-feature NN+RF+SVM ensemble (needs YAMNet). | Kept for comparison only; over-fits the majority class. |

```
fluentra_stutter_model/
├── features.py             # SHARED 186-dim feature extractor (train + infer use this)
├── train_improved.py       # builds balanced labels, trains v2 models, writes metrics
├── improved_inference.py   # v2 engine: binary fluency + type breakdown -> project schema
├── benchmark_v2.py         # cross-dataset sanity check
├── inference.py            # v1 engine (legacy 6-class ensemble)
├── predict_cli.py          # command-line demo for v1
├── django_integration.py   # ready-to-paste bridge for main/views.py (not wired in)
├── requirements-ml.txt     # ML deps, kept out of the Django app on purpose
└── README.md
```

## Results (honest)

The original 6-class model reported ~75% accuracy but only **~48% balanced
accuracy** and collapsed to **~27%** on a different dataset — it was riding the
dominant `NoStutteredWords` class.

The v2 reframe targets what the app actually needs (a fluency judgment):

| Metric | v1 (6-class) | **v2 (binary fluency)** |
|---|---|---|
| Balanced accuracy (held-out) | ~48% | **66.7%** |
| ROC-AUC | — | **73.4%** |
| Cross-dataset disfluent recall | ~27% | **71.3%** |

Trained on 10,760 balanced SEP-28k clips (labels from annotator majority vote).
The **binary fluency score is the reliable signal**; the secondary type model
(~40% acc / ~30% macro-F1 across 5 hard classes) only colours in *which*
disfluency and is reported candidly, not over-claimed.

## What the model is

| Property | Value |
|---|---|
| Task | 6-class stutter-type classification from a 3-second clip |
| Classes | `Block`, `Interjection`, `NoStutteredWords`, `Prolongation`, `SoundRep`, `WordRep` |
| Features | **1110** = 86 classical (40-MFCC mean/std + ZCR + spectral centroid + rolloff) **+ 1024 YAMNet** embedding |
| Models | Neural Net + Random Forest + (calibrated Linear)SVM, weighted soft-vote **0.40 / 0.35 / 0.25** |
| Artifacts | `../saved_models/` (`*.h5`, `scaler.pkl`, `label_encoder.pkl`, `stutter_rf_model.pkl`, `stutter_svm_model.pkl`, `ensemble_config.pkl`) |

The feature pipeline here is an **exact** replica of the notebook's
`extract_features` + `extract_combined_features`. This matters: the saved
`StandardScaler` was fit on 1110-dim vectors, and feeding it anything else
silently produces meaningless predictions. Keeping the pipeline in one audited
file is the whole point of this package.

## Quick start

```bash
# one-time: install deps
pip install -r fluentra_stutter_model/requirements-ml.txt

# (re)train the v2 models from SEP-28k  (features cache after first run)
python fluentra_stutter_model/train_improved.py                  # full
python fluentra_stutter_model/train_improved.py --max-per-class 5000
python fluentra_stutter_model/train_improved.py --quick           # smoke test

# cross-dataset sanity check
python fluentra_stutter_model/benchmark_v2.py
```

From Python (v2, recommended):

```python
from fluentra_stutter_model import analyze_audio_v2

out = analyze_audio_v2("clip.wav")
out["model"]      # {'disfluent_probability', 'is_disfluent', 'type_probabilities', ...}
out["analysis"]   # the Django-compatible payload (see below)
```

v1 legacy engine is still available via `analyze_audio(...)` / `predict_cli.py`.

`FLUENTRA_MODEL_DIR` (default `../saved_models`) controls where weights load from.

## How it maps onto the Django project

The app stores per-session dysfluency counts and a fluency score on
`SpeechSession` (see `main/models.py`). The model's 6 classes fold into the
app's 4 buckets:

| Model class | App field (`SpeechSession`) |
|---|---|
| `SoundRep` + `WordRep` | `repetitions_count` |
| `Prolongation` | `prolongations_count` |
| `Block` | `blocks_count` |
| `Interjection` | `interjections_count` |
| score / rating | `fluency_score`, `stuttering_type` |
| `NoStutteredWords` | (fluent — no event) |

`analyze_audio()["analysis"]` returns the same schema the Groq call produces,
so `main/views.extract_stutter_counts()` and `parse_analysis_payload()` consume
it with **no app changes**:

```json
{
  "overall_score": 86.2,
  "fluency_rating": "Natural",            // Natural | Mild | Moderate | Severe
  "stuttering_types": [
    {"name": "Repetition",   "severity": 23.1, "count": 1},
    {"name": "Prolongation", "severity": 9.3,  "count": 0},
    {"name": "Blocking",     "severity": 30.1, "count": 0},
    {"name": "Interjection", "severity": 12.6, "count": 0}
  ],
  "key_issues": ["Block likelihood 30%", "..."],
  "detailed_analysis": "...",
  "recommendations": ["..."],
  "analysis_source": "fluentra_local_model",
  "predicted_type": "Block",
  "model_confidence": 30.1
}
```

To actually switch the live app over later, see the step-by-step block at the
top of `django_integration.py`. It is intentionally left unwired.

## Further improving accuracy

The v2 binary detector (~67% balanced / 73 AUC) is near the ceiling for purely
*classical* features. The highest-leverage next steps, in order:

1. **Deep embeddings.** Add YAMNet (1024-d) to the 186 classical features, or
   use the wav2vec2 pipeline already in the repo (`../deep_wav2vec_pipeline.py`).
   Expect the biggest single jump (~+5-10 pts). Cost: slower per-file feature
   extraction; cache it once.
2. **Soft-vote the binary candidates** (RF + LogReg + GradientBoosting) and tune
   the decision threshold for the precision/recall balance you want.
3. **Event-centered windows** instead of a fixed 3-second clip, so the disfluency
   isn't padded/clipped away.

For an FYP defense, the honest framing — a balanced binary fluency detector with
a reported ROC-AUC and confusion matrix, plus a candid note on the harder 5-way
type breakdown — is far more defensible than an over-claimed single accuracy
number. Confusion matrices are written to `../training_artifacts/`.

This package keeps working unchanged after any retrain, as long as the
saved-artifact filenames and the shared `features.py` extractor stay in sync
(training and inference both import the latter, so they cannot drift).
