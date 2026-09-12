# voice/ — ElevenLabs STT + TTS

**Owner:** Suyog (P1)  
**Keys:** ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID — in NordPass

## What lives here

| File | Purpose |
|---|---|
| `eleven.py` | Scribe v2 STT (`transcribe`) + TTS (`speak_wav`) helper |

## Responsibilities

- `transcribe(wav_bytes)` → plain text string via ElevenLabs Scribe v2
- `speak(text)` → raw PCM 16 kHz 16-bit mono bytes
- `speak_wav(text)` → WAV-wrapped bytes (44-byte header + PCM) — safe for ESP32 playback
- Generate the two canned fallback WAVs (run this file directly)

## How backend calls this

```python
from voice.eleven import transcribe, speak_wav

text    = transcribe(wav_bytes)   # STT
wav_out = speak_wav(reply_text)   # TTS
```

You do **not** run Gemini. `backend/main.py` owns that step between your two calls.

## Generate canned WAVs (run once tonight)

```bash
python voice/eleven.py
# writes audio/off_task.wav and audio/goals_ok.wav
```

## Tonight exit

- [ ] `transcribe` returns text from a local test WAV
- [ ] `speak_wav` returns valid WAV bytes audible through system speakers
- [ ] `audio/off_task.wav` and `audio/goals_ok.wav` exist
