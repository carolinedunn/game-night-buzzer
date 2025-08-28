# pi_timer_leds.py
# Two-player turn timer with a single button, LED status, and buzzer.
# Hardware: Raspberry Pi GPIO, one momentary button (to GND), 3 LEDs (G/Y/R), piezo buzzer on PWM pin.
# Usage: python3 pi_timer_leds.py

from gpiozero import Button, PWMOutputDevice, LED
from time import monotonic, sleep

# --- CONFIG ---
TURN_SECONDS = 60          # default per-turn time
WARN_YELLOW = 20           # turn yellow under 20s
WARN_RED = 5               # turn red under 5s

BUTTON_PIN = 17
BUZZER_PIN = 18            # PWM-capable
LED_G_PIN = 23
LED_Y_PIN = 24
LED_R_PIN = 25

# Hardware
btn = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
buzzer = PWMOutputDevice(BUZZER_PIN, frequency=1000)  # 1 kHz tone when value>0
LED_G = LED(LED_G_PIN)
LED_Y = LED(LED_Y_PIN)
LED_R = LED(LED_R_PIN)

# State
state = "IDLE"             # IDLE, P1_RUNNING, P2_RUNNING, TIMEOUT
active_player = 1
deadline = None

def lights_for(remaining):
    if remaining > WARN_YELLOW:
        LED_G.on(); LED_Y.off(); LED_R.off()
    elif remaining > WARN_RED:
        LED_G.off(); LED_Y.on(); LED_R.off()
    else:
        LED_G.off(); LED_Y.off(); LED_R.on()

def beep(freq=1000, duration=0.2, vol=0.5):
    buzzer.frequency = freq
    buzzer.value = vol
    sleep(duration)
    buzzer.value = 0

def start_turn(player):
    global state, active_player, deadline
    active_player = player
    deadline = monotonic() + TURN_SECONDS
    state = "P1_RUNNING" if player == 1 else "P2_RUNNING"
    # start sound (two short beeps for P1, three for P2)
    for _ in range(2 if player == 1 else 3):
        beep(1200 if player == 1 else 900, 0.08)
        sleep(0.07)

def next_player():
    start_turn(2 if active_player == 1 else 1)

def on_press():
    global state
    if state in ("IDLE", "TIMEOUT"):
        start_turn(1 if state == "IDLE" else (2 if active_player == 1 else 1))
    else:
        next_player()

btn.when_pressed = on_press

try:
    print("Game Timer Ready. Press button to start Player 1.")
    while True:
        if state in ("P1_RUNNING", "P2_RUNNING"):
            remaining = max(0, int(round(deadline - monotonic())))
            lights_for(remaining)
            if remaining <= 0:
                state = "TIMEOUT"
                # timeout alarm (descending tones)
                for f in (1200, 1000, 800, 600, 400):
                    beep(f, 0.1, 0.7)
                    sleep(0.03)
                LED_G.off(); LED_Y.off(); LED_R.blink(on_time=0.15, off_time=0.15)
        else:
            sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    buzzer.value = 0
    LED_G.off(); LED_Y.off(); LED_R.off()
