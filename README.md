# Fluentra

Fluentra is a Django-based web application for **speech analysis and stutter
therapy**. It helps users practise speech techniques, record and analyse
sessions, and track progress through a structured dashboard with exercises,
analytics, gamification, and account management.

## Project components

**1. Web application (Django)** — `main/`, `fluentra/`, `templates/`, `static/`
User accounts (email + Google OAuth), onboarding, subscription/payments,
practice & exercise modules, a dashboard with analytics, and an AI speech-coach
chat. Speech is transcribed and analysed for dysfluencies (repetitions,
prolongations, blocks, interjections) and scored for fluency.

**2. Machine-learning model** — [`model_training/`](model_training/)
A stutter / dysfluency **detection model trained from scratch** on public
stuttering speech datasets (SEP-28k and others), with a full training notebook,
classical → YAMNet → wav2vec2 feature progression, honest evaluation (balanced
accuracy, ROC-AUC, confusion matrices), and a bridge that plugs the model into
the Django app. See [model_training/README.md](model_training/README.md).

> The live demo runs speech analysis through a speech-to-text + LLM API for
> reliability; the trained model is a drop-in alternative that produces the same
> analysis output. Both are part of the project.

## Tech stack

- **Backend:** Django, custom email-based user model, django-allauth (Google OAuth)
- **Speech / AI:** speech-to-text + LLM analysis API; custom-trained audio model
- **ML:** librosa, scikit-learn, TensorFlow/Keras, YAMNet, wav2vec2 (transformers)
- **Frontend:** Django templates, vanilla JS, custom CSS

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in your keys
python manage.py migrate
python manage.py runserver
```

Configuration (API keys, secret key, OAuth, email) is read from environment
variables — see `.env.example` for the full list.
