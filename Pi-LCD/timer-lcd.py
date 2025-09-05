#!/usr/bin/env python3
# pi_timer_lcd.py
# Two-player turn timer with LCD readout, LEDs, and buzzer.
# Self-contained: custom I2C LCD driver (no RPLCD).
# Requires: gpiozero, smbus (or smbus2)

from gpiozero import Button, PWMOutputDevice, LED
from time import monotonic, sleep
import smbus

# --- CONFIG ---
TURN_SECONDS = 10
WARN_YELLOW = 4
WARN_RED = 2

# GPIO Pins
BUTTON_PIN = 17
BUZZER_PIN = 18
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
    """Helper class for I2C communication."""
    def __init__(self, addr, port=1):
        self.addr = addr
        self.port = port               # <-- remember port so we can reopen bus
        self.bus = smbus.SMBus(port)
    def reopen(self):
        try:
            # Some smbus impls don't have .close(); ignore if missing
            if hasattr(self.bus, "close"):
                self.bus.close()
        except Exception:
            pass
        self.bus = smbus.SMBus(self.port)
    def write_cmd(self, cmd):
        self.bus.write_byte(self.addr, cmd)
        sleep(0.0001)

class lcd:
    """16x2 I2C LCD (HD44780 over PCF8574)."""
    # Commands
    LCD_CLEARDISPLAY   = 0x01
    LCD_RETURNHOME     = 0x02
    LCD_ENTRYMODESET   = 0x04
    LCD_DISPLAYCONTROL = 0x08
    LCD_FUNCTIONSET    = 0x20
    LCD_SETDDRAMADDR   = 0x80

    # Entry mode flags
    LCD_ENTRYLEFT            = 0x02   # increment cursor
    # (do NOT set LCD_ENTRYSHIFTINCREMENT to avoid display shifting)

    # Display control flags
    LCD_DISPLAYON  = 0x04
    LCD_CURSOROFF  = 0x00
    LCD_BLINKOFF   = 0x00

    # Function set flags
    LCD_4BITMODE = 0x00
    LCD_2LINE    = 0x08
    LCD_5x8DOTS  = 0x00

    # Backlight
    LCD_BACKLIGHT   = 0x08

    # Control bits
    En = 0b00000100  # Enable
    Rw = 0b00000010  # Read/Write (unused)
    Rs = 0b00000001  # Register select

    def __init__(self, addr, port):
        self.lcd_device = i2c_device(addr, port)
        self.init_hw()

    # --- init/reset helpers ---
    def init_hw(self):
        """Send the standard 4-bit init sequence + basic config."""
        self.lcd_write(0x03); self.lcd_write(0x03); self.lcd_write(0x03); self.lcd_write(0x02)
        self.lcd_write(self.LCD_FUNCTIONSET | self.LCD_2LINE | self.LCD_5x8DOTS | self.LCD_4BITMODE)
        self.lcd_write(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF)
        self.lcd_write(self.LCD_ENTRYMODESET | self.LCD_ENTRYLEFT)  # increment, no display shift
        self.lcd_clear()
        sleep(0.2)

    def soft_reset(self):
        """Reopen I²C bus and re-init the LCD (used after I/O errors)."""
        self.lcd_device.reopen()
        self.init_hw()

    # --- low-level write primitives ---
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

    # --- user-facing ops ---
    def lcd_clear(self):
        self.lcd_write(self.LCD_CLEARDISPLAY)
        self.lcd_write(self.LCD_RETURNHOME)
        sleep(0.002)

    def lcd_display_string(self, string, line):
        """Write string at column 0 of line 1 or 2."""
        if line == 1:
            self.lcd_write(self.LCD_SETDDRAMADDR | 0x00)  # line 1 start
        elif line == 2:
            self.lcd_write(self.LCD_SETDDRAMADDR | 0x40)  # line 2 start
        string = string.ljust(16)[:16]
        for ch in string:
            self.lcd_write(ord(ch), self.Rs)

# =================================================================
# == END: I2C LCD DRIVER CODE
# =================================================================

# --- MAIN TIMER APP ---

btn = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
buzzer = PWMOutputDevice(BUZZER_PIN, frequency=1000)
LED_G = LED(LED_G_PIN)
LED_Y = LED(LED_Y_PIN)
LED_R = LED(LED_R_PIN)

lcd = lcd(addr=I2C_ADDRESS, port=I2C_BUS)

state = "IDLE"
active_player = 1
deadline = None

# ---- LCD safe helpers (retry once on I2C error) ----
def lcd_safe_clear():
    try:
        lcd.lcd_clear()
    except OSError:
        lcd.soft_reset()
        lcd.lcd_clear()

def lcd_safe_show(player, remaining):
    for attempt in range(2):  # try once, then reset+retry
        try:
            lcd.lcd_display_string(f"Player {player}", 1)
            lcd.lcd_display_string(f"Time: {remaining:>3}s", 2)
            return
        except OSError:
            lcd.soft_reset()

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

def lcd_idle(msg_top="Press to start", msg_bot="   Game Timer"):
    lcd_safe_clear()
    lcd_safe_show(msg_top if isinstance(msg_top, int) else msg_top, 0)  # reuse helper for line formatting
    # Overwrite line 2 explicitly:
    for attempt in range(2):
        try:
            lcd.lcd_display_string(msg_bot, 2)
            break
        except OSError:
            lcd.soft_reset()

def start_turn(player):
    """Start new turn (also does LCD cleanup each turn)."""
    global state, active_player, deadline
    active_player = player
    deadline = monotonic() + TURN_SECONDS
    state = "P1_RUNNING" if player == 1 else "P2_RUNNING"

    # Stop any timeout blinking and wipe old text (CLEANUP EACH TURN)
    LED_R.off()
    lcd_safe_clear()

    # Start tones: P1=2 beeps @1200Hz, P2=3 beeps @900Hz
    count = 2 if player == 1 else 3
    freq  = 1200 if player == 1 else 900
    for _ in range(count):
        beep(freq, 0.08)
        sleep(0.07)

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
        print("LCD Game Timer Ready. Press button to start.")
        while True:
            if state in ("P1_RUNNING", "P2_RUNNING"):
                remaining = max(0, int(round(deadline - monotonic())))
                lights_for(remaining)
                lcd_safe_show(active_player, remaining)

                if remaining <= 0:
                    state = "TIMEOUT"
                    # Timeout tones
                    for f in (1200, 1000, 800, 600, 400):
                        beep(f, 0.1, 0.7)
                        sleep(0.03)
                    LED_G.off(); LED_Y.off()
                    LED_R.blink(on_time=0.15, off_time=0.15)
                    # Show timeout UI with guards
                    try:
                        lcd_safe_clear()
                        for attempt in range(2):
                            try:
                                lcd.lcd_display_string("   TIME IS UP", 1)
                                lcd.lcd_display_string("Press for next", 2)
                                break
                            except OSError:
                                lcd.soft_reset()
                    except OSError:
                        lcd.soft_reset()
            else:
                sleep(0.05)  # idle/time-out chill
    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        print("Cleaning up GPIO and LCD.")
        try:
            lcd_safe_clear()
        except Exception:
            pass
        buzzer.close()
        LED_G.close(); LED_Y.close(); LED_R.close()
        btn.close()
