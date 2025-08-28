#!/usr/bin/env python3
# pi_timer_lcd_speaker.py
# Two-player turn timer with LCD readout + LEDs.
# Sound via 3.5mm jack (ALSA 'aplay'); no GPIO buzzer required.
# Requires: gpiozero, smbus (or smbus2), alsa-utils (aplay)

from gpiozero import Button, LED
from time import monotonic, sleep
import smbus
import math, struct, wave, io, tempfile, subprocess, os

# --- CONFIG ---
TURN_SECONDS = 60
WARN_YELLOW = 20
WARN_RED = 5

# GPIO Pins
BUTTON_PIN = 17
LED_G_PIN = 23
LED_Y_PIN = 24
LED_R_PIN = 25

# I2C LCD
I2C_ADDRESS = 0x27   # use 0x3F for some backpacks
I2C_BUS = 1          # 0 for very old Pi, otherwise 1

# =================================================================
# == START: I2C LCD DRIVER CODE
# =================================================================

class i2c_device:
    def __init__(self, addr, port=1):
        self.addr = addr
        self.bus = smbus.SMBus(port)
    def write_cmd(self, cmd):
        self.bus.write_byte(self.addr, cmd)
        sleep(0.0001)

class lcd:
    # Commands
    LCD_CLEARDISPLAY   = 0x01
    LCD_RETURNHOME     = 0x02
    LCD_ENTRYMODESET   = 0x04
    LCD_DISPLAYCONTROL = 0x08
    LCD_FUNCTIONSET    = 0x20
    LCD_SETDDRAMADDR   = 0x80
    # Entry mode flags
    LCD_ENTRYLEFT = 0x02
    # Display control
    LCD_DISPLAYON = 0x04
    LCD_CURSOROFF = 0x00
    LCD_BLINKOFF  = 0x00
    # Function set
    LCD_4BITMODE = 0x00
    LCD_2LINE    = 0x08
    LCD_5x8DOTS  = 0x00
    # Backlight + control bits
    LCD_BACKLIGHT   = 0x08
    En = 0b00000100
    Rw = 0b00000010
    Rs = 0b00000001

    def __init__(self, addr, port):
        self.lcd_device = i2c_device(addr, port)
        # Init sequence
        self.lcd_write(0x03); self.lcd_write(0x03); self.lcd_write(0x03); self.lcd_write(0x02)
        self.lcd_write(self.LCD_FUNCTIONSET | self.LCD_2LINE | self.LCD_5x8DOTS | self.LCD_4BITMODE)
        self.lcd_write(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF)
        self.lcd_write(self.LCD_ENTRYMODESET | self.LCD_ENTRYLEFT)  # increment, no display shift
        self.lcd_clear(); sleep(0.2)

    def lcd_strobe(self, data):
        self.lcd_device.write_cmd(data | self.En | self.LCD_BACKLIGHT)
        sleep(0.0005)
        self.lcd_device.write_cmd((data & ~self.En) | self.LCD_BACKLIGHT)
        sleep(0.0001)

    def lcd_write_four_bits(self, data):
        self.lcd_device.write_cmd(data | self.LCD_BACKLIGHT)
        self.lcd_strobe(data)

    def lcd_write(self, cmd, mode=0):
        self.lcd_write_four_bits(mode | (cmd & 0xF0))
        self.lcd_write_four_bits(mode | ((cmd << 4) & 0xF0))

    def lcd_clear(self):
        self.lcd_write(self.LCD_CLEARDISPLAY)
        self.lcd_write(self.LCD_RETURNHOME)
        sleep(0.002)

    def lcd_display_string(self, string, line):
        if line == 1:
            self.lcd_write(self.LCD_SETDDRAMADDR | 0x00)
        elif line == 2:
            self.lcd_write(self.LCD_SETDDRAMADDR | 0x40)
        string = string.ljust(16)[:16]
        for ch in string:
            self.lcd_write(ord(ch), self.Rs)

# =================================================================
# == END: I2C LCD DRIVER CODE
# =================================================================

# --- AUDIO (3.5mm jack via ALSA) ---
SR = 44100

def _tone_wav_bytes(freq_hz=1000, ms=120, volume=0.5):
    n = int(SR * ms / 1000.0)
    amp = int(32767 * max(0.0, min(1.0, volume)))
    frames = bytearray()
    for i in range(n):
        s = int(amp * math.sin(2 * math.pi * freq_hz * i / SR))
        frames += struct.pack('<h', s) * 2  # stereo
    bio = io.BytesIO()
    with wave.open(bio, 'wb') as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes(frames)
    return bio.getvalue()

def play_tone(freq=1000, ms=120, vol=0.5):
    data = _tone_wav_bytes(freq, ms, vol)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
        f.write(data)
        path = f.name
    try:
        subprocess.run(['aplay', '-q', path], check=False)
    finally:
        try: os.unlink(path)
        except OSError: pass

# --- MAIN TIMER APP ---

btn = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
LED_G = LED(LED_G_PIN)
LED_Y = LED(LED_Y_PIN)
LED_R = LED(LED_R_PIN)

lcd = lcd(addr=I2C_ADDRESS, port=I2C_BUS)

state = "IDLE"
active_player = 1
deadline = None

def lights_for(remaining):
    if remaining > WARN_YELLOW:
        LED_G.on(); LED_Y.off(); LED_R.off()
    elif remaining > WARN_RED:
        LED_G.off(); LED_Y.on(); LED_R.off()
    else:
        LED_G.off(); LED_Y.off(); LED_R.on()

def start_beeps(for_player):
    count = 2 if for_player == 1 else 3
    freq = 1200 if for_player == 1 else 900
    for _ in range(count):
        play_tone(freq, 80, 0.6); sleep(0.07)

def timeout_alarm():
    for f in (1200, 1000, 800, 600, 400):
        play_tone(f, 120, 0.7); sleep(0.03)

def lcd_show(player, remaining):
    lcd.lcd_display_string(f"Player {player}", 1)
    lcd.lcd_display_string(f"Time: {remaining:>3}s", 2)

def lcd_idle(msg_top="Press to start", msg_bot="   Game Timer"):
    lcd.lcd_clear()
    lcd.lcd_display_string(msg_top, 1)
    lcd.lcd_display_string(msg_bot, 2)

def start_turn(player):
    """Start new turn (also clears TIMEOUT UI)."""
    global state, active_player, deadline
    active_player = player
    deadline = monotonic() + TURN_SECONDS
    state = "P1_RUNNING" if player == 1 else "P2_RUNNING"

    LED_R.off()
    lcd.lcd_clear()
    start_beeps(player)

def next_player():
    start_turn(2 if active_player == 1 else 1)

def on_press():
    global state
    if state in ("IDLE", "TIMEOUT"):
        next_p = 1 if state == "IDLE" else (2 if active_player == 1 else 1)
        start_turn(next_p)
    else:
        next_player()

# --- MAIN LOOP ---
if __name__ == "__main__":
    btn.when_pressed = on_press
    try:
        lcd_idle()
        print("LCD Game Timer (speaker) ready. Press button to start.")
        while True:
            if state in ("P1_RUNNING", "P2_RUNNING"):
                remaining = max(0, int(round(deadline - monotonic())))
                lights_for(remaining)
                lcd_show(active_player, remaining)

                if remaining <= 0:
                    state = "TIMEOUT"
                    timeout_alarm()
                    LED_G.off(); LED_Y.off()
                    LED_R.blink(on_time=0.15, off_time=0.15)
                    lcd_idle("   TIME IS UP", "Press for next")
            else:
                sleep(0.05)
    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        print("Cleaning up GPIO and LCD.")
        lcd.lcd_clear()
        LED_G.close(); LED_Y.close(); LED_R.close()
        btn.close()
