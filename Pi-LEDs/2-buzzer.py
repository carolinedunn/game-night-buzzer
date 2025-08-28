#2-buzzer.py

from gpiozero import Button, PWMOutputDevice, LED
from time import monotonic, sleep

# --- CONFIG ---
BUZZER_PIN = 18            # PWM-capable
LED_G_PIN = 23
LED_Y_PIN = 24
LED_R_PIN = 25

# Hardware
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
	beep(1000, 0.1, 0.7)
	print("beep")
	sleep(0.3)
