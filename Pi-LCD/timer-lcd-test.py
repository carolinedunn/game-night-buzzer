#!/usr/bin/env python3
# pi_timer_lcd.py
# Two-player turn timer with LCD readout, LEDs, and buzzer.
# This version is self-contained and uses a custom I2C LCD driver
# instead of the RPLCD library.
# Requires: smbus2, gpiozero

from gpiozero import Button, PWMOutputDevice, LED
from time import monotonic, sleep
import smbus

# --- HARDWARE CONFIG ---
TURN_SECONDS = 60
WARN_YELLOW = 20
WARN_RED = 5

# GPIO Pin Configuration
BUTTON_PIN = 17
BUZZER_PIN = 18
LED_G_PIN = 23
LED_Y_PIN = 24
LED_R_PIN = 25

# I2C LCD Configuration
I2C_ADDRESS = 0x27  # Change to 0x3F if your backpack differs
I2C_BUS = 1         # 0 for original Pi, 1 for Rev 2 Pi and later

# =================================================================
# == START: I2C LCD DRIVER CODE (from i2c_lcd_driver.py)
# =================================================================

class i2c_device:
    """Helper class for I2C communication."""
    def __init__(self, addr, port=1):
        self.addr = addr
        self.bus = smbus.SMBus(port)

    def write_cmd(self, cmd):
        """Write a single command."""
        self.bus.write_byte(self.addr, cmd)
        sleep(0.0001)

class lcd:
    """Class to control the 16x2 I2C LCD."""
    # commands
    LCD_CLEARDISPLAY = 0x01
    LCD_RETURNHOME = 0x02
    LCD_ENTRYMODESET = 0x04
    LCD_DISPLAYCONTROL = 0x08
    LCD_FUNCTIONSET = 0x20
    LCD_SETDDRAMADDR = 0x80

    # flags for display entry mode
    LCD_ENTRYLEFT = 0x02
    LCD_ENTRYSHIFTINCREMENT = 0x01

    # flags for display on/off control
    LCD_DISPLAYON = 0x04
    LCD_CURSOROFF = 0x00
    LCD_BLINKOFF = 0x00

    # flags for function set
    LCD_4BITMODE = 0x00
    LCD_2LINE = 0x08
    LCD_5x8DOTS = 0x00

    # flags for backlight control
    LCD_BACKLIGHT = 0x08
    LCD_NOBACKLIGHT = 0x00

    # Bitmasks for commands
    En = 0b00000100  # Enable bit
    Rw = 0b00000010  # Read/Write bit
    Rs = 0b00000001  # Register select bit

    def __init__(self, addr, port):
        """Initializes the LCD object and the display."""
        self.lcd_device = i2c_device(addr, port)

        # Initialization sequence
        self.lcd_write(0x03)
        self.lcd_write(0x03)
        self.lcd_write(0x03)
        self.lcd_write(0x02)

        self.lcd_write(self.LCD_FUNCTIONSET | self.LCD_2LINE | self.LCD_5x8DOTS | self.LCD_4BITMODE)
        self.lcd_write(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF)
        self.lcd_write(self.LCD_ENTRYMODESET | self.LCD_ENTRYLEFT | self.LCD_ENTRYSHIFTINCREMENT)
        self.lcd_clear()
        sleep(0.2)

    def lcd_strobe(self, data):
        """Clocks EN to latch command."""
        self.lcd_device.write_cmd(data | self.En | self.LCD_BACKLIGHT)
        sleep(0.0005)
        self.lcd_device.write_cmd(((data & ~self.En) | self.LCD_BACKLIGHT))
        sleep(0.0001)

    def lcd_write_four_bits(self, data):
        """Writes four bits of data to the LCD."""
        self.lcd_device.write_cmd(data | self.LCD_BACKLIGHT)
        self.lcd_strobe(data)

    def lcd_write(self, cmd, mode=0):
        """Writes a command to the LCD."""
        self.lcd_write_four_bits(mode | (cmd & 0xF0))
        self.lcd_write_four_bits(mode | ((cmd << 4) & 0xF0))

    def lcd_display_string(self, string, line):
    """Displays a string on a specific line (1 or 2), starting at column 0."""
    # Set DDRAM address: line 1 starts at 0x00, line 2 at 0x40
        if line == 1:
            self.lcd_write(self.LCD_SETDDRAMADDR | 0x00)   # 0x80 | 0x00
        elif line == 2:
            self.lcd_write(self.LCD_SETDDRAMADDR | 0x40)   # 0x80 | 0x40

        string = string.ljust(16, " ")
        for char in string:
            self.lcd_write(ord(char), self.Rs)


    def lcd_clear(self):
        """Clears the LCD and sets the cursor to home."""
        self.lcd_write(self.LCD_CLEARDISPLAY)
        self.lcd_write(self.LCD_RETURNHOME)

# =================================================================
# == END: I2C LCD DRIVER CODE
# =================================================================


# --- MAIN TIMER APPLICATION ---

# Hardware Initialization
btn = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
buzzer = PWMOutputDevice(BUZZER_PIN, frequency=1000)
LED_G = LED(LED_G_PIN)
LED_Y = LED(LED_Y_PIN)
LED_R = LED(LED_R_PIN)

# Initialize LCD using the custom driver
lcd = lcd(addr=I2C_ADDRESS, port=I2C_BUS)

# State variables
state = "IDLE"
active_player = 1
deadline = None

def lights_for(remaining):
    """Controls the LEDs based on remaining time."""
    if remaining > WARN_YELLOW:
        LED_G.on(); LED_Y.off(); LED_R.off()
    elif remaining > WARN_RED:
        LED_G.off(); LED_Y.on(); LED_R.off()
    else:
        LED_G.off(); LED_Y.off(); LED_R.on()

def beep(freq=1000, duration=0.2, vol=0.5):
    """Activates the buzzer for a short duration."""
    buzzer.frequency = freq
    buzzer.value = vol
    sleep(duration)
    buzzer.value = 0

def lcd_show(player, remaining):
    """
    Displays the active player and remaining time on the LCD.
    (MODIFIED to use the new driver)
    """
    lcd.lcd_display_string(f"Player {player}", 1)
    lcd.lcd_display_string(f"Time: {remaining:>3}s", 2)

def lcd_idle(msg_top="Press to start", msg_bot="   Game Timer"):
    """
    Displays an idle message on the LCD.
    (MODIFIED to use the new driver)
    """
    lcd.lcd_clear()
    lcd.lcd_display_string(msg_top, 1)
    lcd.lcd_display_string(msg_bot, 2)

def start_turn(player):
    """Starts a new turn for the given player."""
    global state, active_player, deadline
    active_player = player
    deadline = monotonic() + TURN_SECONDS
    state = "P1_RUNNING" if player == 1 else "P2_RUNNING"
    # Beep twice for player 1, three times for player 2
    for _ in range(2 if player == 1 else 3):
        beep(1200 if player == 1 else 900, 0.08)
        sleep(0.07)

def next_player():
    """Switches to the next player's turn."""
    start_turn(2 if active_player == 1 else 1)

def on_press():
    """Callback function for when the button is pressed."""
    global state
    if state in ("IDLE", "TIMEOUT"):
        # If idle, start with player 1. If timeout, start with the other player.
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
                lcd_show(active_player, remaining)
                if remaining <= 0:
                    state = "TIMEOUT"
                    # Play a descending tone sequence for timeout
                    for f in (1200, 1000, 800, 600, 400):
                        beep(f, 0.1, 0.7)
                        sleep(0.03)
                    LED_G.off(); LED_Y.off()
                    LED_R.blink(on_time=0.15, off_time=0.15)
                    lcd_idle("   TIME IS UP", "Press for next")
            else:
                # Sleep briefly when idle to reduce CPU usage
                sleep(0.05)
    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        # Cleanup resources on exit
        print("Cleaning up GPIO and LCD.")
        lcd.lcd_clear()
        buzzer.close()
        LED_G.close(); LED_Y.close(); LED_R.close()
        btn.close()
