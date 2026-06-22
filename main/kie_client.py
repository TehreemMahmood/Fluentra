import requests
import time
import os
import json
import tempfile
import io
import re

KIE_BASE_URL = "https://api.kie.ai/api/v1"

class KieClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def create_task(self, audio_url, language_code="", tag_audio_events=True, diarize=True):
        """
        Creates a new Speech-to-Text task using elevenlabs/speech-to-text model.
        """
        url = f"{KIE_BASE_URL}/jobs/createTask"
        payload = {
            "model": "elevenlabs/speech-to-text",
            "input": {
                "audio_url": audio_url,
                "language_code": language_code,
                "tag_audio_events": tag_audio_events,
                "diarize": diarize
            }
        }
        
        response = requests.post(url, json=payload, headers=self.headers)
        
        # Check for HTTP errors
        if not response.ok:
            raise Exception(f"Failed to create task: {response.status_code} {response.text}")
            
        data = response.json()
        if data.get("code") != 200:
             raise Exception(f"API Error: {data.get('msg', 'Unknown error')}")
             
        return data["data"]["taskId"]

    def get_task_status(self, task_id):
        """
        Polls the task status using the /jobs/recordInfo endpoint.
        """
        url = f"{KIE_BASE_URL}/jobs/recordInfo"
        params = {"taskId": task_id}
        
        response = requests.get(url, params=params, headers=self.headers)
        
        if not response.ok:
            raise Exception(f"Failed to get task status: {response.status_code} {response.text}")
            
        return response.json()

    def wait_for_result(self, task_id, poll_interval=2, max_attempts=90):
        """
        Helper method to poll until the task is complete.
        Increased max_attempts from 60 to 90 to handle longer processing (3 min timeout).
        """
        for attempt in range(max_attempts):
            try:
                result = self.get_task_status(task_id)
                data = result.get("data", {})
                state = data.get("state")
                
                print(f"[DEBUG] Task poll attempt {attempt + 1}/{max_attempts}: state={state}")
                
                if state == "success":
                    print(f"[DEBUG] Task completed successfully")
                    return data
                
                if state == "failed":
                    error_msg = data.get('failMsg', 'Unknown failure')
                    print(f"[DEBUG] Task failed: {error_msg}")
                    raise Exception(f"Task failed: {error_msg}")
                
                if state == "error":
                    error_msg = data.get('errorMsg', data.get('msg', 'Unknown error'))
                    print(f"[DEBUG] Task error: {error_msg}")
                    raise Exception(f"Task error: {error_msg}")
                    
                time.sleep(poll_interval)
                
            except requests.RequestException as req_err:
                print(f"[DEBUG] Network error during polling: {req_err}")
                # Don't fail on transient network errors, just retry
                time.sleep(poll_interval)
                continue
            
        raise Exception("Timeout waiting for task completion (exceeded 3 minutes)")

def convert_audio_to_mp3(file_obj, original_filename):
    """
    Convert audio file to MP3 format using ffmpeg binary from imageio-ffmpeg.
    Returns the converted file content and new filename.
    Raises exception if conversion fails - API only supports MP3.
    """
    import imageio_ffmpeg
    import subprocess

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    print(f"[DEBUG] Using ffmpeg at: {ffmpeg_path}")
    
    # Determine source format from filename
    ext = original_filename.lower().split('.')[-1] if '.' in original_filename else 'webm'
    
    # If already mp3, just return as-is
    if ext in ('mp3', 'mpeg'):
        print(f"[DEBUG] File is already MP3, skipping conversion")
        file_obj.seek(0)
        return file_obj, original_filename
    
    print(f"[DEBUG] Converting {ext} to MP3...")
    
    # Read the file into memory
    file_obj.seek(0)
    audio_data = file_obj.read()
    print(f"[DEBUG] Read {len(audio_data)} bytes from original file")
    
    if len(audio_data) < 100:
        raise Exception(f"Audio file too small ({len(audio_data)} bytes), recording may have failed")
    
    # Create temporary files for conversion
    with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmp_in:
        tmp_in.write(audio_data)
        tmp_in_path = tmp_in.name
    
    tmp_out_path = tmp_in_path.rsplit('.', 1)[0] + '.mp3'
    
    try:
        # Use ffmpeg directly for more reliable conversion
        print(f"[DEBUG] Converting with ffmpeg: {tmp_in_path} -> {tmp_out_path}")
        
        cmd = [
            ffmpeg_path,
            '-y',  # Overwrite output
            '-i', tmp_in_path,  # Input file
            '-vn',  # No video
            '-acodec', 'libmp3lame',  # MP3 codec
            '-ab', '128k',  # Bitrate
            '-ar', '44100',  # Sample rate
            '-ac', '2',  # Stereo
            tmp_out_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"[DEBUG] ffmpeg stderr: {result.stderr}")
            raise Exception(f"ffmpeg conversion failed: {result.stderr[:200]}")
        
        # Read the converted MP3
        with open(tmp_out_path, 'rb') as f:
            mp3_data = f.read()
        
        mp3_buffer = io.BytesIO(mp3_data)
        mp3_size = len(mp3_data)
        print(f"[DEBUG] Successfully converted to MP3: {mp3_size} bytes")
        
        if mp3_size < 100:
            raise Exception("MP3 conversion resulted in empty file")
        
        new_filename = original_filename.rsplit('.', 1)[0] + '.mp3'
        return mp3_buffer, new_filename
        
    finally:
        # Clean up temp files
        for path in [tmp_in_path, tmp_out_path]:
            try:
                os.unlink(path)
            except:
                pass


def upload_to_tmpfiles(file_obj, filename):
    """
    Uploads a file to tmpfiles.org to get a temporary public URL.
    Converts all audio formats to mp3 first for API compatibility.
    Includes retry logic for transient failures.
    """
    print(f"[DEBUG] Original filename: {filename}")

    def sanitize_filename(name, default_ext='mp3'):
        base = (name or '').strip().replace('\\', '/').split('/')[-1]
        base = base.split(';')[0].strip()  # remove blobs like "; codecs=opus"
        if '.' in base:
            stem, ext_part = base.rsplit('.', 1)
            ext_part = re.sub(r'[^a-zA-Z0-9]', '', ext_part).lower() or default_ext
        else:
            stem, ext_part = base or 'recording', default_ext

        stem = re.sub(r'[^a-zA-Z0-9._-]+', '_', stem).strip('._-') or 'recording'
        return f"{stem}.{ext_part}"
    
    # Get original file extension
    filename = sanitize_filename(filename, default_ext='webm')
    ext = filename.lower().split('.')[-1] if '.' in filename else 'unknown'
    print(f"[DEBUG] Original format: {ext}")
    print(f"[DEBUG] Sanitized original filename: {filename}")
    
    # Convert to MP3 for better API compatibility, but fallback to original if conversion fails
    upload_file = file_obj
    upload_filename = filename
    converted_ok = False

    try:
        converted_file, converted_filename = convert_audio_to_mp3(file_obj, filename)
        upload_file = converted_file
        upload_filename = sanitize_filename(converted_filename, default_ext='mp3')
        converted_ok = True
        print(f"[DEBUG] Converted filename: {upload_filename}")
        print(f"[DEBUG] Conversion: {ext} -> {upload_filename.split('.')[-1]}")
    except Exception as conv_err:
        print(f"[DEBUG] MP3 conversion failed, falling back to original file: {conv_err}")
        file_obj.seek(0)
    
    url = "https://tmpfiles.org/api/v1/upload"
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] Upload attempt {attempt + 1}/{max_retries}")

            # Reset file pointer before each attempt
            upload_file.seek(0)
            payload = upload_file.read()
            payload_size = len(payload)
            upload_file = io.BytesIO(payload)

            if payload_size < 100:
                raise Exception(f"Upload payload too small ({payload_size} bytes)")

            mime = 'audio/mpeg' if upload_filename.lower().endswith('.mp3') else 'application/octet-stream'
            files = {'file': (upload_filename, upload_file, mime)}
            response = requests.post(url, files=files, timeout=30)
            
            print(f"[DEBUG] tmpfiles response: {response.status_code} - {response.text[:300]}")
            
            if response.ok:
                try:
                    data = response.json()
                    if data.get('status') == 'success' and data.get('data') and data['data'].get('url'):
                        display_url = data['data']['url']
                        final_url = display_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                        print(f"[DEBUG] Final upload URL: {final_url}")
                        return final_url
                    else:
                        error_msg = data.get('msg', 'Unknown API error')
                        print(f"[DEBUG] API returned non-success status: {data}")
                        if attempt < max_retries - 1:
                            time.sleep(2)  # Wait before retry
                            continue
                        raise Exception(f"tmpfiles API error: {error_msg}")
                except (ValueError, KeyError) as json_err:
                    print(f"[DEBUG] JSON parsing error: {json_err}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    raise Exception(f"Invalid response from tmpfiles: {response.text[:100]}")
            else:
                error_detail = f"HTTP {response.status_code}"

                # tmpfiles sometimes rejects converted file format; fallback to original input once
                if response.status_code == 422 and converted_ok:
                    print("[DEBUG] tmpfiles returned 422 for converted file, retrying with original audio")
                    file_obj.seek(0)
                    upload_file = file_obj
                    upload_filename = filename
                    converted_ok = False
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue

                if attempt < max_retries - 1:
                    print(f"[DEBUG] Upload failed with {error_detail}, retrying...")
                    time.sleep(2)
                    continue
                raise Exception(f"Failed to upload file: {error_detail} ({response.text[:120]})")
                
        except requests.RequestException as req_err:
            print(f"[DEBUG] Network error: {req_err}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise Exception(f"Network error during upload: {str(req_err)[:100]}")
    
    raise Exception("Failed to upload file to temporary storage after retries")
