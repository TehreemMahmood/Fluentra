import os
import requests
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fluentra.settings')
django.setup()

def test_integration():
    print("Testing KIE.ai Integration...")
    
    # 1. Test API Key
    api_key = settings.KIE_API_KEY
    print(f"API Key: {api_key}")
    
    # 2. Test Tmpfiles Upload
    print("\nTesting Upload...")
    try:
        # Create dummy audio
        with open('test_audio.txt', 'wb') as f:
            f.write(b'fake audio data')
            
        url = "https://tmpfiles.org/api/v1/upload"
        # Changed to .mp3 to match the fix in speech_analysis.py
        files = {'file': ('test.mp3', open('test_audio.txt', 'rb'))}
        response = requests.post(url, files=files, timeout=30)
        print(f"Upload Status: {response.status_code}")
        print(f"Upload Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            display_url = data['data']['url']
            dl_url = display_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
            print(f"Download URL: {dl_url}")
            
            # 3. Test Create Task
            print("\nTesting Create Task...")
            create_url = "https://api.kie.ai/api/v1/jobs/createTask"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "elevenlabs/speech-to-text",
                "input": {
                    "audio_url": dl_url, # Use URL from upload
                    "language_code": "",
                    "tag_audio_events": True,
                    "diarize": True
                }
            }
            res = requests.post(create_url, json=payload, headers=headers)
            print(f"Create Task Status: {res.status_code}")
            print(f"Create Task Response: {res.text}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if os.path.exists('test_audio.txt'):
            os.remove('test_audio.txt')

if __name__ == "__main__":
    test_integration()