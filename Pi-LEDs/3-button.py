# 3-button.py
# Hardware: Raspberry Pi GPIO, one momentary button (to GND), 3 LEDs (G/Y/R), piezo buzzer on PWM pin.
# Usage: python3 3-button.py

from gpiozero import Button, PWMOutputDevice, LED
from time import monotonic, sleep

# --- CONFIG ---
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

def beep(freq=1000, duration=0.2, vol=0.5):
    buzzer.frequency = freq
    buzzer.value = vol
    sleep(duration)
    buzzer.value = 0

while True:
	print("press button to start")
	btn.wait_for_press()
	print("button pressed")
	LED_G.on(); LED_Y.on(); LED_R.on()
	beep(1000, 0.1, 0.7)
	sleep(1)
	LED_G.off(); LED_Y.off(); LED_R.off()
