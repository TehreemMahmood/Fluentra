"""
Test script to verify ElevenLabs and Google Gemini API keys work
"""
import os
import sys

# Add the project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['DJANGO_SETTINGS_MODULE'] = 'fluentra.settings'

import django
django.setup()

from django.conf import settings

def test_elevenlabs():
    """Test ElevenLabs API"""
    print("\n" + "="*50)
    print("Testing ElevenLabs API...")
    print("="*50)
    
    api_key = settings.ELEVENLABS_API_KEY
    print(f"API Key length: {len(api_key)}")
    
    try:
        from elevenlabs.client import ElevenLabs
        
        client = ElevenLabs(api_key=api_key)
        
        # Try to get user info to verify API key works
        # We'll use a simple API call
        print("Attempting to verify API key...")
        
        # Test with a simple audio URL
        import requests
        from io import BytesIO
        
        # Download a short test audio
        audio_url = "https://storage.googleapis.com/eleven-public-cdn/audio/marketing/nicole.mp3"
        print(f"Downloading test audio from: {audio_url}")
        response = requests.get(audio_url, timeout=10)
        audio_data = BytesIO(response.content)
        audio_data.name = "test.mp3"
        
        print("Calling ElevenLabs Speech-to-Text API...")
        transcription = client.speech_to_text.convert(
            file=audio_data,
            model_id="scribe_v2",
            language_code="eng",
        )
        
        print(f"✅ ElevenLabs API WORKS!")
        print(f"Transcription: {transcription.text[:100]}..." if len(transcription.text) > 100 else f"Transcription: {transcription.text}")
        return True
        
    except Exception as e:
        print(f"❌ ElevenLabs API FAILED: {e}")
        return False


def test_gemini():
    """Test Google Gemini API"""
    print("\n" + "="*50)
    print("Testing Google Gemini API...")
    print("="*50)
    
    api_key = settings.GEMINI_API_KEY
    print(f"API Key length: {len(api_key)}")
    
    try:
        from google import genai
        
        client = genai.Client(api_key=api_key)
        
        print("Calling Gemini API with model gemini-2.0-flash...")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Say 'Hello, the API is working!' in exactly those words."
        )
        
        print(f"✅ Gemini API WORKS!")
        print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Gemini API FAILED: {e}")
        
        # Try alternative model names
        print("\nTrying alternative approach with google-generativeai...")
        try:
            import google.generativeai as genai_old
            genai_old.configure(api_key=api_key)
            
            model = genai_old.GenerativeModel('gemini-pro')
            response = model.generate_content("Say 'Hello, the API is working!' in exactly those words.")
            
            print(f"✅ Gemini API WORKS (using google-generativeai)!")
            print(f"Response: {response.text}")
            return True
        except Exception as e2:
            print(f"❌ Alternative also failed: {e2}")
            return False


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# FluEntra API Test Script")
    print("#"*60)
    
    elevenlabs_ok = test_elevenlabs()
    gemini_ok = test_gemini()
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"ElevenLabs: {'✅ WORKING' if elevenlabs_ok else '❌ FAILED'}")
    print(f"Gemini:     {'✅ WORKING' if gemini_ok else '❌ FAILED'}")
    print("="*50)
