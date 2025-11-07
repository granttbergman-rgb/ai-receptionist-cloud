import os, httpx, sys, json
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("ELEVENLABS_API_KEY")
if not API:
    sys.exit("Missing ELEVENLABS_API_KEY in .env")

url_voices = "https://api.elevenlabs.io/v1/voices"
r = httpx.get(url_voices, headers={"xi-api-key": API}, timeout=20)
if r.status_code != 200:
    print("Voice list error:", r.status_code, r.text[:200])
    sys.exit(1)

voices = r.json().get("voices", [])
if not voices:
    sys.exit("No voices found.")
voice_id = voices[0]["voice_id"]
voice_name = voices[0]["name"]
print("Using voice:", voice_name)

tts_url = (
    "https://api.elevenlabs.io/v1/text-to-speech/"
    + voice_id + "/stream"
)
headers = {
    "xi-api-key": API,
    "accept": "audio/mpeg",
    "content-type": "application/json",
}
data = {
    "text": "This is a test using " + voice_name + ".",
    "model_id": "eleven_turbo_v2_5",
}

resp = httpx.post(tts_url, headers=headers, json=data, timeout=60)
ctype = resp.headers.get("content-type", "")
if resp.status_code != 200 or "audio" not in ctype:
    print("TTS error:", resp.status_code, resp.text[:300])
    sys.exit(1)

with open("test_output.mp3", "wb") as f:
    f.write(resp.content)

print("✅ Saved test_output.mp3 (", len(resp.content), "bytes)")
import os, httpx, sys, json
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("ELEVENLABS_API_KEY")
if not API:
    sys.exit("Missing ELEVENLABS_API_KEY in .env")

url_voices = "https://api.elevenlabs.io/v1/voices"
r = httpx.get(url_voices, headers={"xi-api-key": API}, timeout=20)
if r.status_code != 200:
    print("Voice list error:", r.status_code, r.text[:200])
    sys.exit(1)

voices = r.json().get("voices", [])
if not voices:
    sys.exit("No voices found.")
voice_id = voices[0]["voice_id"]
voice_name = voices[0]["name"]
print("Using voice:", voice_name)

tts_url = (
    "https://api.elevenlabs.io/v1/text-to-speech/"
    + voice_id + "/stream"
)
headers = {
    "xi-api-key": API,
    "accept": "audio/mpeg",
    "content-type": "application/json",
}
data = {
    "text": "This is a test using " + voice_name + ".",
    "model_id": "eleven_turbo_v2_5",
}

resp = httpx.post(tts_url, headers=headers, json=data, timeout=60)
ctype = resp.headers.get("content-type", "")
if resp.status_code != 200 or "audio" not in ctype:
    print("TTS error:", resp.status_code, resp.text[:300])
    sys.exit(1)

with open("test_output.mp3", "wb") as f:
    f.write(resp.content)

print("✅ Saved test_output.mp3 (", len(resp.content), "bytes)")

