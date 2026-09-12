"""ElevenLabs Scribe STT + TTS helper.
Keys in NordPass. Call from backend/main.py — never from the watch.
"""
import os
from elevenlabs import ElevenLabs

ELEVEN_API_KEY = os.environ["ELEVENLABS_API_KEY"]
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # "George"

_client = ElevenLabs(api_key=ELEVEN_API_KEY)


def transcribe(wav_bytes: bytes, language: str = "eng") -> str:
    """Scribe v2 STT. Returns plain text."""
    result = _client.speech_to_text.convert(
        file=("audio.wav", wav_bytes, "audio/wav"),
        model_id="scribe_v2",
        language_code=language,
    )
    return result.text.strip()


def speak(text: str) -> bytes:
    """TTS → raw PCM 16 kHz 16-bit mono (no MP3 decode on ESP32)."""
    audio = _client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="pcm_16000",
    )
    # convert generator to bytes
    return b"".join(audio)


def speak_wav(text: str) -> bytes:
    """TTS → WAV file bytes (PCM wrapped in a WAV header)."""
    pcm = speak(text)
    return _pcm_to_wav(pcm, sample_rate=16000, channels=1, bit_depth=16)


def _pcm_to_wav(pcm: bytes, sample_rate=16000, channels=1, bit_depth=16) -> bytes:
    import struct

    byte_rate = sample_rate * channels * bit_depth // 8
    block_align = channels * bit_depth // 8
    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,        # subchunk1 size
        1,         # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bit_depth,
        b"data",
        data_size,
    )
    return header + pcm


if __name__ == "__main__":
    import sys, pathlib

    if len(sys.argv) == 2:
        wav = pathlib.Path(sys.argv[1]).read_bytes()
        print("Transcription:", transcribe(wav))
    else:
        # generate canned coaching WAV
        line = (
            "You have senior design until 10. You can play after that. "
            "You'll regret this block later — go back to the project."
        )
        out = pathlib.Path(__file__).parent.parent / "audio" / "off_task.wav"
        out.write_bytes(speak_wav(line))
        print("Wrote", out)

        goals = "Got both. Send the email first — that's the short one. Then you have a straight run at senior design until 10."
        out2 = pathlib.Path(__file__).parent.parent / "audio" / "goals_ok.wav"
        out2.write_bytes(speak_wav(goals))
        print("Wrote", out2)
