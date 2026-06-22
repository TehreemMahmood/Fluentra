"""
Django integration helper for the FluEntra stutter classifier.
==============================================================

This file is NOT wired into the live app. It is a ready-to-use bridge so that
*if/when* you decide to use the locally trained model instead of (or alongside)
the Groq/ElevenLabs API, the change is a few lines.

The function below returns the EXACT same dict shape that
`main/views.transcribe_audio` already builds from Groq, so the rest of the app
(serialize_practice_session, extract_stutter_counts, the SpeechSession fields)
keeps working unchanged.

------------------------------------------------------------------------------
HOW TO PLUG IN LATER
------------------------------------------------------------------------------
1. Copy this `fluentra_stutter_model/` package next to your Django project, or
   `pip install -e` it, and set the env var so it can find the weights:

       FLUENTRA_MODEL_DIR=D:/Study/FYP-02/saved_models

2. Add the ML deps to the Django venv (see requirements-ml.txt). These are
   heavy (tensorflow, librosa), which is exactly why the live app currently
   stays API-only and this remains optional.

3. In main/views.transcribe_audio, after you obtain `transcript_text`, branch
   on a flag instead of always calling Groq:

       if request.POST.get('analysis_engine') == 'local_model':
           from fluentra_stutter_model.django_integration import analyze_session
           payload = analyze_session(saved_audio_path)   # project schema dict
           analysis_result = json.dumps(payload)
       else:
           ... existing Groq call ...

   `analyze_session` already returns overall_score / fluency_rating /
   stuttering_types[], so extract_stutter_counts() populates
   repetitions_count / prolongations_count / blocks_count / interjections_count
   with no other changes.
------------------------------------------------------------------------------
"""

from .improved_inference import analyze_audio_v2
from .inference import analyze_audio


def analyze_session(audio_path, audio_duration=None, engine="v2") -> dict:
    """Return the FluEntra project-compatible analysis payload for one clip.

    The returned dict matches what main/views.parse_analysis_payload expects
    and what gets stored in SpeechSession.analysis_data.

    engine="v2" (default) uses the improved two-stage binary-fluency model
    (recommended, lightweight, no YAMNet). engine="v1" uses the original
    6-class 1110-feature ensemble.
    """
    fn = analyze_audio_v2 if engine == "v2" else analyze_audio
    return fn(audio_path, audio_duration=audio_duration)["analysis"]


def analyze_session_full(audio_path, audio_duration=None, engine="v2") -> dict:
    """Same as analyze_session but also includes the raw model report under
    'model' for debugging / a side-by-side comparison against the API."""
    fn = analyze_audio_v2 if engine == "v2" else analyze_audio
    return fn(audio_path, audio_duration=audio_duration)
