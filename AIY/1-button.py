import time
from aiy.board import Board

with Board() as board:
    print("Press the AIY button to toggle the LED. Ctrl+C to exit.")
    state = False
    while True:
        board.button.wait_for_press()
        state = not state
        board.led.state = board.led.ON if state else board.led.OFF
        time.sleep(0.2)  # simple debounce
