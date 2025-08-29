# 1-leds.py

from gpiozero import LED
from time import sleep

# --- CONFIG ---
LED_G_PIN = 23
LED_Y_PIN = 24
LED_R_PIN = 25

# Hardware
LED_G = LED(LED_G_PIN)
LED_Y = LED(LED_Y_PIN)
LED_R = LED(LED_R_PIN)

while True:
	LED_G.off(); LED_Y.off(); LED_R.off()
	LED_G.on()
	print("green")
	sleep(1)
	LED_G.off()
	LED_Y.on()
	print("yellow")
	sleep(1)
	LED_Y.off()
	LED_R.on()
	print("red")
	sleep(1)
	LED_G.off(); LED_Y.off(); LED_R.off()
