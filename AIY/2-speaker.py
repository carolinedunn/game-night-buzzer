import time
import math
import wave
import io
import os
import array
import tempfile

from aiy.board import Board
from aiy.voice.audio import play_wav

def make_beep_wav_bytes(frequency=1000, duration=0.2, volume=0.5, sample_rate=16000):
    """Return WAV bytes for a mono 16-bit PCM sine wave."""
    n = int(sample_rate * duration)
    samples = array.array("h", (
        int(volume * 32767.0 * math.sin(2.0 * math.pi * frequency * t / sample_rate))
        for t in range(n)
    ))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()

def beep(frequency=1000, duration=0.15, volume=0.5):
    """Generate a sine beep and play it with aiy.voice.audio.play_wav."""
    wav_bytes = make_beep_wav_bytes(frequency=frequency, duration=duration, volume=volume)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name
    try:
        play_wav(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

with Board() as board:
    print("Press the AIY button to toggle the LED. Ctrl+C to exit.")
    state = False
    while True:
        board.button.wait_for_press()
        next_state = not state
        # Different tone for ON vs OFF to make feedback clear
        tone = 1200 if next_state else 800
        beep(frequency=tone, duration=0.12, volume=0.55)
        state = next_state
        board.led.state = board.led.ON if state else board.led.OFF
        time.sleep(0.2)  # simple debounce
