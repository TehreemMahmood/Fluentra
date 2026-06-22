from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import timedelta
import json
import uuid
import re
import os
import requests

from .models import User, SubscriptionPlan, Subscription, Payment, SpeechSession


def parse_analysis_payload(raw_analysis):
    if isinstance(raw_analysis, dict):
        return raw_analysis
    if not raw_analysis:
        return {}

    cleaned = str(raw_analysis).strip()
    if cleaned.startswith('```json'):
        cleaned = cleaned.replace('```json', '', 1).rsplit('```', 1)[0].strip()
    elif cleaned.startswith('```'):
        cleaned = cleaned.replace('```', '', 1).rsplit('```', 1)[0].strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {'raw_text': cleaned}
    except Exception:
        return {'raw_text': cleaned}


def extract_stutter_counts(analysis_payload):
    counts = {
        'repetitions': 0,
        'prolongations': 0,
        'blocks': 0,
        'interjections': 0,
    }

    types = analysis_payload.get('stuttering_types') if isinstance(analysis_payload, dict) else None
    if isinstance(types, list):
        for item in types:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or '').lower()
            try:
                count = int(item.get('count') or 0)
            except Exception:
                count = 0

            if 'repetition' in name or 'repeat' in name:
                counts['repetitions'] = count
            elif 'prolong' in name:
                counts['prolongations'] = count
            elif 'block' in name:
                counts['blocks'] = count
            elif 'interjection' in name or 'filler' in name:
                counts['interjections'] = count

    return counts


def serialize_practice_session(session):
    if not session:
        return None

    analysis_data = session.analysis_data if isinstance(session.analysis_data, dict) else parse_analysis_payload(session.analysis_data)
    return {
        'id': session.id,
        'created_at': session.created_at,
        'session_type': session.session_type,
        'duration_seconds': session.duration_seconds,
        'words_analyzed': session.words_analyzed,
        'fluency_score': session.fluency_score,
        'transcript': session.transcription_text,
        'analysis_data': analysis_data,
        'analysis_raw_text': analysis_data.get('raw_text', '') if isinstance(analysis_data, dict) else '',
        'flagged_words': session.flagged_words or [],
        'audio_url': session.audio_file.url if session.audio_file else '',
        'stuttering_type': session.stuttering_type,
        'repetitions_count': session.repetitions_count,
        'prolongations_count': session.prolongations_count,
        'blocks_count': session.blocks_count,
        'interjections_count': session.interjections_count,
        'user_email': session.user.email,
    }


def send_verification_email(request, user, token):
    """Send email verification link to user."""
    verification_url = request.build_absolute_uri(f'/verify-email/{token}/')
    
    subject = 'Verify your FluEntra account'
    message = f"""
Hi {user.full_name or 'there'},

Welcome to FluEntra! Please verify your email address by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you didn't create an account with FluEntra, please ignore this email.

Best regards,
The FluEntra Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@fluentra.com',
            [user.email],
            fail_silently=True,  # Don't crash if email fails
        )
    except Exception as e:
        print(f"Email sending failed: {e}")  # Log error but don't crash


def index(request):
    return render(request, 'index.html')


def about(request):
    return render(request, 'about.html')


@login_required
def app(request):
    # Redirect to complete profile if onboarding not completed
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    
    context = {
        'user': request.user,
        'email_verified': request.user.email_verified,
        'active_tab': 'dashboard',
    }
    return render(request, 'app.html', context)

@login_required
def techniques(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/techniques.html', {'active_tab': 'techniques'})

@login_required
def technique_breathing(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/technique_breathing.html', {'active_tab': 'techniques'})

@login_required
def technique_articulation(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/technique_articulation.html', {'active_tab': 'techniques'})

@login_required
def technique_cancellation(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/technique_cancellation.html', {'active_tab': 'techniques'})

@login_required
def technique_prolonged(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/technique_prolonged.html', {'active_tab': 'techniques'})

@login_required
def technique_onset(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/technique_onset.html', {'active_tab': 'techniques'})

@login_required
def exercises(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/exercises.html', {'active_tab': 'exercises'})

@login_required
def exercise_repetition(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/exercise_repetition.html', {'active_tab': 'exercises'})

@login_required
def exercise_prolongation(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/exercise_prolongation.html', {'active_tab': 'exercises'})

@login_required
def exercise_blocking(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/exercise_blocking.html', {'active_tab': 'exercises'})

@login_required
def exercise_interjection(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/exercise_interjection.html', {'active_tab': 'exercises'})

@login_required
def analytics(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/analytics.html', {'active_tab': 'analytics'})

@login_required
def settings_view(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')
    return render(request, 'dashboard/settings.html', {'active_tab': 'settings'})

@login_required
def practice_view(request):
    if not request.user.onboarding_completed:
        return redirect('complete_profile')

    latest_session = (
        SpeechSession.objects
        .filter(user=request.user, session_type='speech_analysis')
        .order_by('-created_at')
        .first()
    )

    context = {
        'active_tab': 'practice',
        'latest_practice_session': serialize_practice_session(latest_session),
    }
    return render(request, 'dashboard/practice.html', context)

@login_required
@require_http_methods(["POST"])
def transcribe_audio(request):
    """
    Handle audio upload and transcription via ElevenLabs + AI analysis.
    """
    if 'audio_file' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No audio file provided'}, status=400)
    
    file_obj = request.FILES['audio_file']
    filename = file_obj.name
    
    # Ensure filename has an extension (for recorded blobs)
    if not filename or '.' not in filename:
        # Try to guess extension from content type
        content_type = file_obj.content_type or ''
        if 'webm' in content_type:
            filename = 'recording.webm'
        elif 'ogg' in content_type:
            filename = 'recording.ogg'
        elif 'mp4' in content_type or 'm4a' in content_type:
            filename = 'recording.m4a'
        else:
            filename = 'recording.webm'  # Default to webm
    
    # Reset file pointer to beginning
    file_obj.seek(0)
    
    # Analyze with Groq via OpenAI-compatible SDK
    groq_key = getattr(settings, 'GROQ_API_KEY', None) or os.environ.get('GROQ_API_KEY')
    if not groq_key:
         return JsonResponse({'success': False, 'error': 'Groq API Key missing (GROQ_API_KEY)'}, status=500)

    # Allow UI/clients to choose different analysis model dynamically.
    # For multipart/form-data requests this arrives in POST.
    requested_ai_model = (request.POST.get('ai_model') or '').strip()
    default_ai_model = getattr(settings, 'GROQ_DEFAULT_MODEL', None) or 'openai/gpt-oss-20b'
    ai_model = requested_ai_model or default_ai_model
        
    try:
        # Keep KIE helpers available for other flows but use Eleven Labs Scribe v2 here.
        from openai import OpenAI
        from .kie_client import KieClient, upload_to_tmpfiles

        # Prefer ELEVEN_API_KEY from Django settings, fallback to environment
        eleven_key = getattr(settings, 'ELEVEN_API_KEY', None) or os.environ.get('ELEVEN_API_KEY')
        if not eleven_key:
            raise Exception('Server configuration error: ElevenLabs API key missing (ELEVEN_API_KEY)')

        transcript_text = ""
        analysis_result = ""
        result_payload = None
        ai_flagged_words = []

        # Try direct upload to Eleven Labs (multipart file upload)
        try:
            file_obj.seek(0)
            eleven_url = 'https://api.elevenlabs.io/v1/speech-to-text'
            headers = {
                'xi-api-key': eleven_key
            }

            files = {
                'file': (filename, file_obj, file_obj.content_type or 'application/octet-stream')
            }

            data = {
                'model_id': 'scribe_v2'
            }

            resp = requests.post(eleven_url, headers=headers, files=files, data=data, timeout=120)
            # If API returns direct text/plain we accept that, otherwise try to parse JSON
            if resp.ok:
                ctype = resp.headers.get('content-type', '')
                if 'application/json' in ctype:
                    try:
                        result_payload = resp.json()
                        # Try common keys
                        transcript_text = result_payload.get('text') or result_payload.get('transcript') or ''
                    except Exception:
                        transcript_text = resp.text or ''
                else:
                    # Some ElevenLabs endpoints return plain text
                    transcript_text = resp.text or ''
            else:
                # If direct upload failed, fall back to uploading the audio to tmpfiles and use URL flow
                raise Exception(f'ElevenLabs direct upload failed: {resp.status_code} {resp.text[:200]}')

        except Exception as primary_err:
            # Fallback: upload to tmpfiles.org, fetch bytes back, and retry multipart upload.
            print(f"ElevenLabs direct upload failed, falling back to tmpfiles multipart retry: {primary_err}")
            try:
                file_obj.seek(0)
                public_url = upload_to_tmpfiles(file_obj, filename)
                dl_resp = requests.get(public_url, timeout=60)
                if not dl_resp.ok:
                    raise Exception(f"Failed to download fallback audio URL: {dl_resp.status_code}")

                eleven_url = 'https://api.elevenlabs.io/v1/speech-to-text'
                headers = {
                    'xi-api-key': eleven_key
                }
                files2 = {
                    'file': (filename, dl_resp.content, file_obj.content_type or 'application/octet-stream')
                }
                data2 = {
                    'model_id': 'scribe_v2',
                }

                resp2 = requests.post(eleven_url, headers=headers, files=files2, data=data2, timeout=120)
                if resp2.ok:
                    ctype = resp2.headers.get('content-type', '')
                    if 'application/json' in ctype:
                        try:
                            result_payload = resp2.json()
                            transcript_text = result_payload.get('text') or result_payload.get('transcript') or ''
                        except Exception:
                            transcript_text = resp2.text or ''
                    else:
                        transcript_text = resp2.text or ''
                else:
                    raise Exception(f'ElevenLabs fallback multipart transcription failed: {resp2.status_code} {resp2.text[:200]}')

            except Exception as fallback_err:
                # Re-raise a helpful error for the outer except to catch and return
                raise Exception(f'ElevenLabs transcription failed (direct: {primary_err}; url-fallback: {fallback_err})')

        # Keep the original result structure for backward compatibility
        result_data = result_payload or {'provider': 'elevenlabs', 'note': 'transcription returned as text'}
        analysis_payload = parse_analysis_payload(analysis_result)
        stutter_counts = extract_stutter_counts(analysis_payload)
        duration_seconds = 0
        try:
            duration_seconds = int(float(request.POST.get('duration_seconds') or 0))
        except Exception:
            duration_seconds = 0

        saved_session = None

        # If we have a transcript, analyze it with Groq/OpenAI-compatible API.
        if transcript_text:
            try:
                groq_client = OpenAI(
                    api_key=groq_key,
                    base_url='https://api.groq.com/openai/v1'
                )

                prompt = f"""
                        Analyze the following speech transcript for stuttering patterns as an expert speech pathologist.
                        Return ONLY a valid JSON object (no markdown formatting) with the following structure:
                        {{
                            "overall_score": <number 0-100, where 100 is perfectly fluent>,
                            "fluency_rating": <string: "Natural", "Mild", "Moderate", "Severe">,
                            "stuttering_types": [
                                {{"name": "Repetition", "severity": <number 0-100>, "count": <number>}},
                                {{"name": "Prolongation", "severity": <number 0-100>, "count": <number>}},
                                {{"name": "Blocking", "severity": <number 0-100>, "count": <number>}}
                            ],
                            "key_issues": [<list of strings identifying specific patterns found>],
                            "detailed_analysis": "<string with detailed clinical analysis>",
                            "recommendations": [<list of actionable advice strings>]
                        }}

                        Transcript:
                        "{transcript_text}"
                        """

                response = groq_client.responses.create(
                    model=ai_model,
                    input=prompt
                )
                analysis_result = getattr(response, 'output_text', '') or ''

                # AI word-level stutter detection for transcript highlighting.
                # Returns indexes to reduce ambiguity when repeated words appear.
                try:
                    transcript_words = re.findall(r"\b[\w']+\b", transcript_text)
                    indexed_words = "\n".join([f"{i}: {w}" for i, w in enumerate(transcript_words)])

                    word_prompt = f"""
Identify likely stutter events in this indexed transcript.
Return ONLY valid JSON (no markdown) in this exact shape:
{{
  "flagged_words": [
    {{"index": <int>, "word": "<word>", "reason": "Repetition|Prolongation|Blocking|Interjection"}}
  ]
}}

Rules:
- Use indexes from the provided list.
- Only include words you strongly suspect are stutter-related.
- Max 30 items.

Indexed words:
{indexed_words}
"""

                    word_resp = groq_client.responses.create(
                        model=ai_model,
                        input=word_prompt
                    )
                    flagged_raw = (getattr(word_resp, 'output_text', '') or '').strip()

                    if flagged_raw.startswith('```json'):
                        flagged_raw = flagged_raw.replace('```json', '', 1).rsplit('```', 1)[0].strip()
                    elif flagged_raw.startswith('```'):
                        flagged_raw = flagged_raw.replace('```', '', 1).rsplit('```', 1)[0].strip()

                    flagged_obj = json.loads(flagged_raw)
                    flagged_list = flagged_obj.get('flagged_words', []) if isinstance(flagged_obj, dict) else []

                    safe_flags = []
                    for item in flagged_list:
                        if not isinstance(item, dict):
                            continue
                        idx = item.get('index')
                        try:
                            idx = int(idx)
                        except Exception:
                            continue
                        if idx < 0 or idx >= len(transcript_words):
                            continue

                        reason = str(item.get('reason') or '').strip() or 'Stutter Event'
                        safe_flags.append({
                            'index': idx,
                            'word': transcript_words[idx],
                            'reason': reason
                        })

                    # De-duplicate by index
                    seen_idx = set()
                    for f in safe_flags:
                        if f['index'] in seen_idx:
                            continue
                        seen_idx.add(f['index'])
                        ai_flagged_words.append(f)
                except Exception as ai_flag_err:
                    print(f"Groq word-level highlighting failed: {ai_flag_err}")
            except Exception as g_err:
                print(f"Groq analysis failed: {g_err}")
                analysis_result = local_analyze_stuttering(transcript_text)
                analysis_payload = parse_analysis_payload(analysis_result)
                stutter_counts = extract_stutter_counts(analysis_payload)
        else:
            analysis_result = local_analyze_stuttering("")
            analysis_payload = parse_analysis_payload(analysis_result)
            stutter_counts = extract_stutter_counts(analysis_payload)

        if request.user.is_authenticated:
            try:
                transcript_words = re.findall(r"\b[\w']+\b", transcript_text)
                saved_session = SpeechSession.objects.create(
                    user=request.user,
                    session_type='speech_analysis',
                    duration_seconds=duration_seconds,
                    fluency_score=float(analysis_payload.get('overall_score') or 0) if not analysis_payload.get('raw_text') else None,
                    words_analyzed=len(transcript_words),
                    audio_file=file_obj,
                    transcription_text=transcript_text,
                    transcription_data=result_data,
                    analysis_data=analysis_payload,
                    stuttering_type=str(analysis_payload.get('fluency_rating') or analysis_payload.get('stuttering_type') or ''),
                    repetitions_count=stutter_counts['repetitions'],
                    prolongations_count=stutter_counts['prolongations'],
                    blocks_count=stutter_counts['blocks'],
                    interjections_count=stutter_counts['interjections'],
                    flagged_words=ai_flagged_words,
                )
            except Exception as save_err:
                print(f"Failed to save speech session: {save_err}")

        return JsonResponse({
            'success': True,
            'result': result_data,
            'transcript': transcript_text,
            'analysis': analysis_result,
            'flagged_words_ai': ai_flagged_words,
            'analysis_model_used': ai_model,
            'practice_session': serialize_practice_session(saved_session),
            'available_ai_models': [
                'openai/gpt-oss-20b',
                'openai/gpt-oss-120b',
                'llama-3.3-70b-versatile'
            ]
        })

    except Exception as e:
        print(f"Transcription error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def ai_chat(request):
    """
    Chat endpoint for dashboard assistant using Groq via OpenAI-compatible SDK.
    Accepts JSON body: { message: string, history?: [{role, content}] }
    """
    try:
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body'}, status=400)

        user_message = (payload.get('message') or '').strip()
        if not user_message:
            return JsonResponse({'success': False, 'error': 'Message is required'}, status=400)

        history = payload.get('history') or []
        if not isinstance(history, list):
            history = []

        groq_key = getattr(settings, 'GROQ_API_KEY', None) or os.environ.get('GROQ_API_KEY')
        if not groq_key:
            return JsonResponse({'success': False, 'error': 'Groq API Key missing (GROQ_API_KEY)'}, status=500)

        ai_model = getattr(settings, 'GROQ_DEFAULT_MODEL', None) or 'openai/gpt-oss-20b'

        # Keep context compact and safe: only last few turns, plain text only.
        trimmed_history = history[-8:]
        formatted_history = []
        for item in trimmed_history:
            if not isinstance(item, dict):
                continue
            role = (item.get('role') or '').strip().lower()
            content = (item.get('content') or '').strip()
            if role in ('user', 'assistant') and content:
                formatted_history.append((role, content[:1200]))

        conversation_text = "\n".join(
            [f"{role.capitalize()}: {content}" for role, content in formatted_history]
        )

        coach_prompt = f"""
You are FluEntra's AI speech coach.
- Be supportive, practical, and concise.
- Give actionable stuttering/fluency advice.
- Do not claim medical diagnosis; suggest professional help when needed.
- Keep responses under 180 words unless user asks for detail.

Conversation so far:
{conversation_text}

Latest user message:
{user_message}
"""

        from openai import OpenAI

        client = OpenAI(
            api_key=groq_key,
            base_url='https://api.groq.com/openai/v1'
        )

        response = client.responses.create(
            model=ai_model,
            input=coach_prompt,
        )

        reply = (getattr(response, 'output_text', '') or '').strip()
        if not reply:
            reply = "I couldn't generate a response right now. Please try again."

        return JsonResponse({
            'success': True,
            'reply': reply,
            'model_used': ai_model
        })

    except Exception as e:
        print(f"AI chat error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)




def auth_view(request):
    if request.user.is_authenticated:
        if not request.user.onboarding_completed:
            return redirect('complete_profile')
        return redirect('app')
    return render(request, 'auth.html')


def contact(request):
    return render(request, 'contact.html')


def pricing(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    # Get current user's subscription if authenticated
    current_plan = None
    user_subscription = None
    if request.user.is_authenticated:
        try:
            user_subscription = request.user.subscription
            if user_subscription.is_active():
                current_plan = user_subscription.plan.name
        except:
            pass
    
    context = {
        'plans': plans,
        'current_plan': current_plan,
        'user_subscription': user_subscription,
    }
    return render(request, 'pricing.html', context)


# Authentication Views
@require_http_methods(["POST"])
def signup_view(request):
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        full_name = data.get('name', '').strip()
        
        # Validation
        if not email or not password:
            return JsonResponse({'success': False, 'error': 'Email and password are required'}, status=400)
        
        # Email validation
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return JsonResponse({'success': False, 'error': 'Please enter a valid email address'}, status=400)
        
        # Password validation
        if len(password) < 8:
            return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters'}, status=400)
        
        if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            return JsonResponse({'success': False, 'error': 'Password must include at least one letter and one number'}, status=400)
        
        # Check if user exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'error': 'An account with this email already exists'}, status=400)
        
        # Create user (not verified yet)
        user = User.objects.create_user(email=email, password=password, full_name=full_name)
        
        # Generate verification token and send email
        token = user.generate_verification_token()
        send_verification_email(request, user, token)
        
        # Create free subscription
        basic_plan = SubscriptionPlan.objects.filter(name='basic').first()
        if basic_plan:
            Subscription.objects.create(user=user, plan=basic_plan, status='active')
        
        # Don't log in user yet - they need to verify email first
        # Store email in session to show on verification pending page
        request.session['pending_verification_email'] = email
        
        return JsonResponse({
            'success': True, 
            'message': 'Account created! Please check your email to verify your account.',
            'redirect': '/verify-pending/',
            'verification_pending': True
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["POST"])
def login_view(request):
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return JsonResponse({'success': False, 'error': 'Email and password are required'}, status=400)
        
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            # Only enforce verification when explicitly required by settings.
            verification_required = getattr(settings, 'ACCOUNT_EMAIL_VERIFICATION', 'none') == 'mandatory'

            # Check if email is verified (skip for social auth users)
            if verification_required and not user.email_verified:
                from allauth.socialaccount.models import SocialAccount
                has_social_account = SocialAccount.objects.filter(user=user).exists()
                
                if not has_social_account:
                    # Store email in session and redirect to verification pending
                    request.session['pending_verification_email'] = email
                    return JsonResponse({
                        'success': False,
                        'error': 'Please verify your email before logging in.',
                        'redirect': '/verify-pending/',
                        'verification_required': True
                    }, status=403)
            
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Check if onboarding is complete
            redirect_url = '/complete-profile/' if not user.onboarding_completed else '/app/'
            
            return JsonResponse({
                'success': True,
                'message': 'Logged in successfully',
                'redirect': redirect_url
            })
        else:
            return JsonResponse({'success': False, 'error': 'Invalid email or password'}, status=401)
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def logout_view(request):
    logout(request)
    return redirect('index')


# Email Verification Pending View
def verify_pending_view(request):
    """Show the email verification pending page."""
    # If user is already logged in and verified, redirect appropriately
    if request.user.is_authenticated:
        if request.user.email_verified:
            if request.user.onboarding_completed:
                return redirect('app')
            return redirect('complete_profile')
        else:
            # User logged in but not verified (shouldn't normally happen)
            email = request.user.email
    else:
        # Get email from session
        email = request.session.get('pending_verification_email', '')
    
    return render(request, 'verify_pending.html', {'email': email})


# Resend Verification Email
@require_http_methods(["POST"])
def resend_verification_view(request):
    """Resend verification email."""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        
        if not email:
            return JsonResponse({'success': False, 'error': 'Email is required'}, status=400)
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'No account found with this email'}, status=404)
        
        if user.email_verified:
            return JsonResponse({'success': False, 'error': 'Email is already verified'}, status=400)
        
        # Check rate limiting
        if user.email_verification_sent_at:
            time_since_last = timezone.now() - user.email_verification_sent_at
            if time_since_last.total_seconds() < 60:  # 60 second rate limit
                seconds_left = 60 - int(time_since_last.total_seconds())
                return JsonResponse({
                    'success': False, 
                    'error': f'Please wait {seconds_left} seconds before requesting another email'
                }, status=429)
        
        # Generate new token and send email
        token = user.generate_verification_token()
        send_verification_email(request, user, token)
        
        return JsonResponse({
            'success': True,
            'message': 'Verification email sent! Please check your inbox.'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# Profile Completion Views
@login_required
def complete_profile_view(request):
    """Show the complete profile page for new users."""
    # For non-Google users, check if email is verified
    # Google OAuth users are automatically verified
    if not request.user.email_verified:
        # Check if user has social account (Google login)
        from allauth.socialaccount.models import SocialAccount
        has_social_account = SocialAccount.objects.filter(user=request.user).exists()
        
        if not has_social_account:
            # Regular email signup - need to verify first
            request.session['pending_verification_email'] = request.user.email
            logout(request)  # Log them out until verified
            return redirect('verify_pending')
    
    # If user already completed onboarding, redirect to app
    if request.user.onboarding_completed:
        return redirect('app')
    return render(request, 'complete_profile.html')


@login_required
@require_http_methods(["POST"])
def complete_profile_api(request):
    """API endpoint to complete user profile with all onboarding data."""
    try:
        data = json.loads(request.body)
        full_name = data.get('full_name', '').strip()
        age = data.get('age')
        referral = data.get('referral', '')
        goal = data.get('goal', '')
        experience = data.get('experience', '')
        
        if not full_name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)
        
        user = request.user
        user.full_name = full_name
        
        # Save age if provided
        if age:
            try:
                user.age = int(age)
            except (ValueError, TypeError):
                pass
        
        # Save referral source
        if referral:
            user.referral_source = referral
        
        # Save primary goal
        if goal:
            user.primary_goal = goal
        
        # Save experience level
        if experience:
            user.experience_level = experience
        
        # Mark onboarding as completed
        user.onboarding_completed = True
        user.save()
        
        # Clear session flags
        if 'needs_profile_completion' in request.session:
            del request.session['needs_profile_completion']
        if 'is_new_user' in request.session:
            del request.session['is_new_user']
        
        # Create a basic subscription for new users if they don't have one
        if not hasattr(user, 'subscription') or user.subscription is None:
            basic_plan = SubscriptionPlan.objects.filter(name='basic').first()
            if basic_plan:
                Subscription.objects.create(user=user, plan=basic_plan, status='active')
        
        return JsonResponse({
            'success': True,
            'message': 'Profile completed successfully',
            'redirect': '/app/'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# Email Verification Views
def verify_email_view(request, token):
    """Verify user's email address."""
    try:
        user = User.objects.get(email_verification_token=token)
        
        # Check if token is expired (24 hours)
        if user.email_verification_sent_at:
            token_age = timezone.now() - user.email_verification_sent_at
            if token_age > timedelta(hours=24):
                return render(request, 'email_verification.html', {
                    'success': False,
                    'error': 'This verification link has expired. Please request a new one.',
                    'email': user.email,
                    'can_resend': True
                })
        
        # Verify email
        user.email_verified = True
        user.email_verification_token = None
        user.save()
        
        # Log the user in
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Clear any pending verification session
        if 'pending_verification_email' in request.session:
            del request.session['pending_verification_email']
        
        return render(request, 'email_verification.html', {
            'success': True,
            'message': 'Your email has been verified successfully!',
            'redirect_to': 'complete_profile' if not user.onboarding_completed else 'app'
        })
        
    except User.DoesNotExist:
        return render(request, 'email_verification.html', {
            'success': False,
            'error': 'Invalid verification link.'
        })


@login_required
def resend_verification_email(request):
    """Resend verification email to the current user."""
    user = request.user
    
    if user.email_verified:
        return JsonResponse({'success': False, 'error': 'Email is already verified'})
    
    # Check rate limiting (one email per 5 minutes)
    if user.email_verification_sent_at:
        time_since_last = timezone.now() - user.email_verification_sent_at
        if time_since_last < timedelta(minutes=5):
            remaining = 5 - int(time_since_last.total_seconds() / 60)
            return JsonResponse({
                'success': False, 
                'error': f'Please wait {remaining} minute(s) before requesting another email.'
            })
    
    token = user.generate_verification_token()
    send_verification_email(request, user, token)
    
    return JsonResponse({
        'success': True,
        'message': 'Verification email sent! Please check your inbox.'
    })


# Subscription and Payment Views
@login_required
def subscription_view(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    current_subscription = getattr(request.user, 'subscription', None)
    
    context = {
        'plans': plans,
        'current_subscription': current_subscription,
    }
    return render(request, 'subscription.html', context)


@login_required
def checkout_view(request, plan_name):
    plan = get_object_or_404(SubscriptionPlan, name=plan_name, is_active=True)
    
    context = {
        'plan': plan,
    }
    return render(request, 'checkout.html', context)


@login_required
@require_http_methods(["POST"])
def process_payment(request):
    try:
        data = json.loads(request.body)
        plan_name = data.get('plan')
        card_number = data.get('card_number', '').replace(' ', '')
        card_expiry = data.get('card_expiry', '')
        card_cvc = data.get('card_cvc', '')
        card_name = data.get('card_name', '')
        
        # Basic validation
        if not all([plan_name, card_number, card_expiry, card_cvc, card_name]):
            return JsonResponse({'success': False, 'error': 'All card details are required'}, status=400)
        
        # Get plan
        plan = get_object_or_404(SubscriptionPlan, name=plan_name, is_active=True)
        
        # Simulate card validation (fake gateway)
        if len(card_number) < 13 or len(card_number) > 19:
            return JsonResponse({'success': False, 'error': 'Invalid card number'}, status=400)
        
        if len(card_cvc) < 3 or len(card_cvc) > 4:
            return JsonResponse({'success': False, 'error': 'Invalid CVC'}, status=400)
        
        # Simulate payment processing
        # Card numbers starting with 4000 0000 0000 will fail for testing
        if card_number.startswith('4000000000000'):
            return JsonResponse({'success': False, 'error': 'Card declined. Please try another card.'}, status=400)
        
        # Create or update subscription
        subscription, created = Subscription.objects.update_or_create(
            user=request.user,
            defaults={
                'plan': plan,
                'status': 'active',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=30),
                'auto_renew': True,
            }
        )
        
        # Detect card brand
        card_brand = 'Unknown'
        if card_number.startswith('4'):
            card_brand = 'Visa'
        elif card_number.startswith(('51', '52', '53', '54', '55')):
            card_brand = 'Mastercard'
        elif card_number.startswith(('34', '37')):
            card_brand = 'Amex'
        
        # Create payment record
        payment = Payment.objects.create(
            user=request.user,
            subscription=subscription,
            amount=plan.price,
            currency=plan.currency,
            status='completed',
            payment_method='card',
            transaction_id=f"TXN_{uuid.uuid4().hex[:12].upper()}",
            completed_at=timezone.now(),
            card_last_four=card_number[-4:],
            card_brand=card_brand,
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Payment successful! Your subscription is now active.',
            'transaction_id': payment.transaction_id,
            'redirect': '/app/'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def cancel_subscription(request):
    try:
        subscription = getattr(request.user, 'subscription', None)
        if subscription:
            subscription.status = 'cancelled'
            subscription.auto_renew = False
            subscription.save()
            return JsonResponse({'success': True, 'message': 'Subscription cancelled successfully'})
        return JsonResponse({'success': False, 'error': 'No active subscription found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# API endpoints for the app
@login_required
def get_user_profile(request):
    user = request.user
    subscription = getattr(user, 'subscription', None)
    
    return JsonResponse({
        'email': user.email,
        'full_name': user.full_name,
        'initials': user.get_initials(),
        'xp_points': user.xp_points,
        'level': user.level,
        'streak_days': user.streak_days,
        'subscription': {
            'plan': subscription.plan.name if subscription else 'basic',
            'status': subscription.status if subscription else 'active',
            'end_date': subscription.end_date.isoformat() if subscription and subscription.end_date else None,
        } if subscription else None,
    })


@login_required
def get_payment_history(request):
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    return JsonResponse({
        'payments': [
            {
                'id': str(p.id),
                'amount': float(p.amount),
                'currency': p.currency,
                'status': p.status,
                'transaction_id': p.transaction_id,
                'card_brand': p.card_brand,
                'card_last_four': p.card_last_four,
                'created_at': p.created_at.isoformat(),
            }
            for p in payments
        ]
    })


def local_analyze_stuttering(text):
    """
    Fallback analysis when AI APIs are unavailable.
    Performs deterministic regex-based analysis on the transcript.
    """
    # 1. Detection Logic
    # Part-word repetitions with dashes (e.g., "St- st-", "I- I- I-", "c- c-")
    dash_reps = re.findall(r'\b(\w+)-\s*(?:\1-?\s*)+', text, re.IGNORECASE)
    # Word repetitions (e.g., "I I I", "the the")
    word_reps = re.findall(r'\b(\w+)(?:\s+\1)+\b', text, re.IGNORECASE)
    # Part-word repetitions without dash (e.g., "st st stuttering")  
    part_word_reps = re.findall(r'\b(\w{1,3})\s+\1+\s+\w+', text, re.IGNORECASE)
    # Prolongations (heuristic: repeated characters like "sssome")
    prolongations = re.findall(r'\b\w*([a-zA-Z])\1{2,}\w*\b', text)
    # Filler words
    fillers = re.findall(r'\b(um|uh|er|ah|like|you know)\b', text, re.IGNORECASE)
    # Audio events (sighs, laughs, etc.)
    audio_events = re.findall(r'\((laughs|sighs|breathes heavily|dramatic breath|coughs)\)', text, re.IGNORECASE)
    
    total_words = len(text.split())
    if total_words == 0:
        return json.dumps({
            "overall_score": 0,
            "fluency_rating": "No Speech Detected",
            "stuttering_types": [],
            "detailed_analysis": "No speech was detected in the recording.",
            "recommendations": []
        })

    # 2. Metrics Calculation
    repetition_count = len(dash_reps) + len(word_reps) + len(part_word_reps)
    prolongation_count = len(prolongations) + len(audio_events)
    filler_count = len(fillers)
    
    dysfluency_count = repetition_count + prolongation_count + filler_count
    dysfluency_rate = (dysfluency_count / total_words) * 100 if total_words > 0 else 0
    
    # Simple scoring model (0-100)
    # Base 100, deduct points based on dysfluency severity
    score = max(0, min(100, 100 - (dysfluency_count * 3) - (dysfluency_rate * 2)))
    
    # Rating
    if score >= 85: rating = "Natural"
    elif score >= 65: rating = "Mild"
    elif score >= 40: rating = "Moderate"
    else: rating = "Severe"
    
    # 3. Construct Detailed Analysis
    issues_found = []
    if dash_reps:
        issues_found.append(f"Part-word repetitions detected: {', '.join(list(set(dash_reps))[:5])}")
    if word_reps:
        issues_found.append(f"Word repetitions detected: {', '.join(list(set(word_reps))[:5])}")
    if fillers:
        issues_found.append(f"Filler words used: {', '.join(list(set(fillers))[:5])}")
    if audio_events:
        issues_found.append(f"Non-speech sounds: {', '.join(list(set(audio_events))[:3])}")
    
    detailed_text = (
        f"Speech Analysis Summary: Analyzed {total_words} words. "
        f"Found {repetition_count} repetition events, {prolongation_count} prolongation/pause events, "
        f"and {filler_count} filler words. "
        f"Overall dysfluency rate: {dysfluency_rate:.1f}%. "
    )
    
    if dysfluency_rate > 10:
        detailed_text += "Speech patterns indicate significant stuttering behaviors that may benefit from targeted therapy techniques. "
    elif dysfluency_rate > 5:
        detailed_text += "Speech shows moderate dysfluency patterns. Consider practicing smooth speech techniques. "
    else:
        detailed_text += "Speech flows relatively well with only minor hesitation events. "

    # 4. JSON Structure
    result = {
        "overall_score": int(score),
        "fluency_rating": rating,
        "stuttering_types": [
            {
                "name": "Repetition",
                "severity": min(100, repetition_count * 12),
                "count": repetition_count
            },
            {
                "name": "Prolongation",
                "severity": min(100, prolongation_count * 10),
                "count": prolongation_count
            },
            {
                "name": "Blocking",
                "severity": min(100, len(audio_events) * 15),
                "count": len(audio_events)
            }
        ],
        "key_issues": issues_found,
        "detailed_analysis": detailed_text,
        "recommendations": [
            "Practice 'Easy Onset' technique to smooth out initial word sounds.",
            "Use 'Pausing and Phrasing' to maintain a comfortable speech rate.",
            "Try 'Light Articulatory Contacts' to reduce tension on consonants.",
            "Practice diaphragmatic breathing before speaking.",
            "Focus on continuous airflow during phrases."
        ]
    }
    return json.dumps(result)


@login_required
@require_http_methods(["POST"])
def evaluate_exercise(request):
    """
    Evaluate a user's exercise recording by:
    1. Transcribing their speech via KIE.ai
    2. Comparing it with the expected text
    3. Calculating accuracy score
    4. Awarding XP points
    5. Saving the result
    """
    from .models import ExerciseResult
    from .kie_client import KieClient, upload_to_tmpfiles
    from difflib import SequenceMatcher
    
    try:
        # Get form data
        if 'audio_file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No audio file provided'}, status=400)
        
        audio_file = request.FILES['audio_file']
        expected_text = request.POST.get('expected_text', '').strip()
        exercise_type = request.POST.get('exercise_type', 'repetition')
        difficulty = request.POST.get('difficulty', 'easy')
        
        if not expected_text:
            return JsonResponse({'success': False, 'error': 'Expected text not provided'}, status=400)
        
        # Get API key
        api_key = getattr(settings, 'KIE_API_KEY', None) or os.environ.get('KIE_API_KEY')
        if not api_key:
            return JsonResponse({'success': False, 'error': 'API Key not configured'}, status=500)
        
        # Determine filename
        filename = audio_file.name if hasattr(audio_file, 'name') else 'recording.webm'
        if not filename or '.' not in filename:
            content_type = getattr(audio_file, 'content_type', '')
            if 'webm' in content_type:
                filename = 'recording.webm'
            elif 'ogg' in content_type:
                filename = 'recording.ogg'
            else:
                filename = 'recording.webm'
        
        # Upload and transcribe
        audio_file.seek(0)
        public_url = upload_to_tmpfiles(audio_file, filename)
        
        client = KieClient(api_key)
        task_id = client.create_task(audio_url=public_url)
        result_data = client.wait_for_result(task_id, poll_interval=1, max_attempts=30)
        
        # Extract transcript
        transcribed_text = ""
        if 'resultJson' in result_data:
            try:
                outer_json = json.loads(result_data['resultJson'])
                if isinstance(outer_json, dict) and 'resultObject' in outer_json:
                    res_json = outer_json['resultObject']
                else:
                    res_json = outer_json
                
                if 'text' in res_json:
                    transcribed_text = res_json['text']
                elif 'transcript' in res_json:
                    transcribed_text = res_json['transcript']
            except:
                pass
        
        # Clean texts for comparison
        def clean_text(text):
            # Remove punctuation and convert to lowercase
            text = re.sub(r'[^\w\s]', '', text.lower())
            return ' '.join(text.split())
        
        clean_expected = clean_text(expected_text)
        clean_transcribed = clean_text(transcribed_text)
        
        # Calculate accuracy using SequenceMatcher
        matcher = SequenceMatcher(None, clean_expected, clean_transcribed)
        accuracy_score = matcher.ratio() * 100
        
        # Word-by-word comparison
        expected_words = clean_expected.split()
        transcribed_words = clean_transcribed.split()
        
        word_matches = []
        for i, expected_word in enumerate(expected_words):
            if i < len(transcribed_words):
                match = expected_word == transcribed_words[i]
                word_matches.append({
                    'expected': expected_word,
                    'said': transcribed_words[i],
                    'match': match
                })
            else:
                word_matches.append({
                    'expected': expected_word,
                    'said': '',
                    'match': False
                })
        
        # Calculate scores
        words_correct = sum(1 for w in word_matches if w['match'])
        words_total = len(expected_words)
        word_accuracy = (words_correct / words_total * 100) if words_total > 0 else 0
        
        # Overall score (0-10 scale)
        # Weight: 70% word accuracy, 30% sequence similarity
        combined_accuracy = (word_accuracy * 0.7) + (accuracy_score * 0.3)
        overall_score = round(combined_accuracy / 10, 1)  # Convert to 0-10 scale
        overall_score = max(0, min(10, overall_score))  # Clamp to 0-10
        
        # Calculate XP based on difficulty and score
        xp_multiplier = {'easy': 10, 'medium': 15, 'hard': 20}
        base_xp = xp_multiplier.get(difficulty, 10)
        xp_earned = int(overall_score * base_xp / 10)  # Scale XP by score
        
        # Generate feedback
        if overall_score >= 8:
            feedback = "Excellent! Your pronunciation was clear and matched the expected text very well."
            is_good = True
        elif overall_score >= 6:
            feedback = "Good job! Most words were pronounced correctly. Keep practicing for perfection."
            is_good = True
        elif overall_score >= 4:
            feedback = "Nice effort! Focus on speaking more slowly and clearly. Try again!"
            is_good = False
        else:
            feedback = "Keep practicing! Try to match each word carefully. Slow and steady wins the race."
            is_good = False
        
        # Save result to database
        exercise_result = ExerciseResult.objects.create(
            user=request.user,
            exercise_type=exercise_type,
            difficulty=difficulty,
            expected_text=expected_text,
            transcribed_text=transcribed_text,
            accuracy_score=word_accuracy,
            fluency_score=accuracy_score,
            overall_score=overall_score,
            xp_earned=xp_earned,
            feedback=feedback,
            word_matches={'words': word_matches}
        )
        
        # Award XP to user
        request.user.xp_points += xp_earned
        
        # Update level if needed (100 XP per level)
        new_level = (request.user.xp_points // 100) + 1
        if new_level > request.user.level:
            request.user.level = new_level
        
        # Update streak
        from datetime import date
        today = date.today()
        if request.user.last_practice_date != today:
            if request.user.last_practice_date and (today - request.user.last_practice_date).days == 1:
                request.user.streak_days += 1
            elif request.user.last_practice_date and (today - request.user.last_practice_date).days > 1:
                request.user.streak_days = 1
            else:
                request.user.streak_days = max(1, request.user.streak_days)
            request.user.last_practice_date = today
        
        request.user.save()
        
        return JsonResponse({
            'success': True,
            'transcribed_text': transcribed_text,
            'expected_text': expected_text,
            'accuracy_score': round(word_accuracy, 1),
            'overall_score': overall_score,
            'xp_earned': xp_earned,
            'feedback': feedback,
            'is_good': is_good,
            'word_matches': word_matches,
            'words_correct': words_correct,
            'words_total': words_total,
            'user_xp': request.user.xp_points,
            'user_level': request.user.level,
            'user_streak': request.user.streak_days
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
