
import os
import requests
import time
import sys

# Setup
os.environ['DJANGO_SETTINGS_MODULE'] = 'fluentra.settings'
import django
django.setup()
from django.conf import settings

API_KEY = getattr(settings, 'KIE_API_KEY', '')
if not API_KEY:
    print("❌ No API KEY found in settings!")
    sys.exit(1)

print(f"✅ Using API Key: {API_KEY[:5]}...{API_KEY[-5:]}")

API_BASE = "https://api.kie.ai"
UPLOAD_URL = f"{API_BASE}/api/v1/files/upload"
CREATE_TASK_URL = f"{API_BASE}/api/v1/jobs/createTask"
GET_TASK_URL = f"{API_BASE}/api/v1/jobs/getTaskDetail"

def test_stt():
    # 1. Create a dummy audio file (small wav header)
    # 44 bytes specific to WAV 
    dummy_audio = bytes.fromhex('524946462400000057415645666d7420100000000100010044ac000088580100020010006461746100000000')
    
    # 2. Probe Upload Endpoints
    potential_endpoints = [
        "/api/v1/files",  # Like OpenAI
        "/api/files",
        "/v1/files",
        "/files",
        "/api/v1/media",
        "/api/v1/content/upload"
    ]
    
    upload_success = False
    audio_url = None
    
    print(f"\n[1] Probing upload endpoints...")
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    for path in potential_endpoints:
        url = f"{API_BASE}{path}"
        print(f"    Trying {url}...", end=" ")
        try:
            # Re-create file tuple for each request
            files = {"file": ("test.wav", dummy_audio, "audio/wav")}
            resp = requests.post(url, headers=headers, files=files, timeout=10)
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                print(f"    ✅ FOUND! Response: {resp.text}")
                json_resp = resp.json()
                # Try to find URL in common locations
                if "data" in json_resp and "url" in json_resp["data"]:
                    audio_url = json_resp["data"]["url"]
                elif "url" in json_resp:
                    audio_url = json_resp["url"]
                
                if audio_url:
                    print(f"    ✅ Got Audio URL: {audio_url}")
                    upload_success = True
                    break
        except Exception as e:
            print(f"Error: {e}")
            
    if not upload_success:
        print("❌ Could not find working upload endpoint")
        return

    # 3. Create Task
    print(f"\n[2] Creating task at {CREATE_TASK_URL}...")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "elevenlabs/speech-to-text",
        "input": {
            "audio_url": audio_url,
            "language_code": "eng",
            "tag_audio_events": False,
            "diarize": False
        }
    }
    
    try:
        resp = requests.post(CREATE_TASK_URL, json=payload, headers=headers, timeout=30)
        print(f"    Status: {resp.status_code}")
        print(f"    Response: {resp.text}")
        
        if resp.status_code != 200:
            print("❌ Task creation failed")
            return
            
        json_resp = resp.json()
        task_id = json_resp.get("data", {}).get("taskId")
        if not task_id:
            print("❌ No taskId in response")
            return
            
        print(f"✅ Task created: {task_id}")
        
    except Exception as e:
        print(f"❌ Task creation exception: {e}")
        return

    # 4. Poll Status
    print(f"\n[3] Polling status at {GET_TASK_URL}...")
    for i in range(10):
        try:
            resp = requests.get(f"{GET_TASK_URL}?taskId={task_id}", headers=headers, timeout=10)
            print(f"    Attempt {i+1}: Status {resp.status_code}")
            
            if resp.status_code == 200:
                json_resp = resp.json()
                print(f"    Response: {json_resp}")
                status = json_resp.get("data", {}).get("status")
                
                if status == "completed":
                    print("✅ Task COMPLETED!")
                    output = json_resp.get("data", {}).get("output")
                    print(f"    Output: {output}")
                    return
                elif status == "failed":
                    print("❌ Task FAILED")
                    return
            
            time.sleep(2)
        except Exception as e:
            print(f"❌ Polling exception: {e}")
            break

if __name__ == "__main__":
    test_stt()
