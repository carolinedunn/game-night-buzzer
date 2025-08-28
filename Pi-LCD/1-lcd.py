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
        """Displays a string on a specific line."""
        if line == 1:
            self.lcd_write(0x06)
        if line == 2:
            self.lcd_write(0xC0)

        # Pad string to 16 characters to clear the rest of the line
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

# --- MAIN LOOP ---
while True:
    lcd.lcd_clear()
    lcd.lcd_display_string("Welcome to", 1)
    lcd.lcd_display_string("Game Night Buzzer", 2)
