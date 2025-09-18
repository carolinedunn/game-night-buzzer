#!/usr/bin/env python3
# Pi 3 + Google AIY Voice Kit v1 (Voice HAT)
# Two-player turn timer using the HAT's button, button LED, and speaker.
# Requires the AIY Python libs (aiy.board, aiy.voice.audio).

import io, math, struct, wave, time, os, tempfile
from aiy.board import Board, Led
from aiy.voice import audio as aiy_audio  # play_wav(path)

# ---- CONFIG ----
TURN_SECONDS = 10
WARN_YELLOW = 4
WARN_RED = 2

# ---- Tone/WAV helpers ----
def make_tone_wav_bytes(freq_hz=1000, ms=120, volume=0.5, sample_rate=44100):
    """Return stereo 16-bit PCM WAV bytes for a sine tone."""
    n = int(sample_rate * ms / 1000.0)
    frames = bytearray()
    amp = int(32767 * max(0.0, min(1.0, volume)))
    for i in range(n):
        s = int(amp * math.sin(2 * math.pi * freq_hz * i / sample_rate))
        frames += struct.pack('<h', s) * 2  # stereo L+R
    b = io.BytesIO()
    with wave.open(b, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return b.getvalue()

def play_wav_bytes(wav_bytes):
    """Write bytes to a temp WAV and play with aiy.voice.audio.play_wav(path)."""
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    try:
        tmp.write(wav_bytes)
        tmp.flush()
        tmp.close()
        aiy_audio.play_wav(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

def beep(freq=1000, ms=100, vol=0.5):
    play_wav_bytes(make_tone_wav_bytes(freq, ms, vol))

def start_sound(for_player):
    tone = 1200 if for_player == 1 else 900
    count = 2 if for_player == 1 else 3
    for _ in range(count):
        beep(tone, 80, 0.6)
        time.sleep(0.07)

def timeout_alarm():
    for f in (1200, 1000, 800, 600, 400):
        beep(f, 120, 0.7)
        time.sleep(0.04)

# ---- LED helpers with compatibility fallbacks ----
def led_pattern_for_remaining(r):
    """
    Map remaining seconds to an LED pattern that most AIY builds support.
    Uses BEACON when safe, BLINK when critical. Falls back to ON if unknown.
    """
    try:
        if r > WARN_YELLOW:
            return Led.BEACON          # slow pulsing
        elif r <= WARN_RED:
            return Led.BLINK           # fast blink near timeout
        else:
            return Led.BEACON_DARK     # dimmer beacon if available
    except AttributeError:
        # Fallbacks for older images without BEACON_DARK etc.
        return Led.ON if r > WARN_RED else Led.BLINK

# ---- State machine ----
state = "IDLE"   # IDLE, P1_RUNNING, P2_RUNNING, TIMEOUT
active_player = 1
deadline = 0.0

def start_turn(player):
    global state, active_player, deadline
    active_player = player
    deadline = time.monotonic() + TURN_SECONDS
    state = "P1_RUNNING" if player == 1 else "P2_RUNNING"
    start_sound(player)

def next_player():
    start_turn(2 if active_player == 1 else 1)

def remaining():
    return max(0, int(round(deadline - time.monotonic())))

# ---- Main ----
print("AIY Timer: press the big button to start Player 1. Ctrl+C to exit.")
with Board() as board:
    board.led.state = Led.OFF
    try:
        while True:
            pressed = board.button.wait_for_press(timeout=0.05)
            if pressed:
                if state in ("IDLE", "TIMEOUT"):
                    start_turn(1 if state == "IDLE" else (2 if active_player == 1 else 1))
                else:
                    next_player()

            if state in ("P1_RUNNING", "P2_RUNNING"):
                r = remaining()
                board.led.state = led_pattern_for_remaining(r)
                if r <= 0:
                    state = "TIMEOUT"
                    try:
                        board.led.state = Led.BLINK_3
                    except AttributeError:
                        board.led.state = Led.BLINK
                    timeout_alarm()
            else:
                if state == "IDLE":
                    board.led.state = Led.OFF
                time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        board.led.state = Led.OFF
