import sys
import time

import board
import microcontroller

import neopixel

# CircuitPython throws SyntaxError for multiline f-strings - either use single line or concatenation
print(f"\nRunning on {board.board_id} ({sys.platform}), {sys.implementation.name} " +
      f"{sys.version}/{'.'.join(map(str, sys.implementation.version))}, mpy {sys.implementation.mpy}")


def get_gpio(of_pin: microcontroller.Pin) -> str:
    # noinspections PyUnresolvedReferences
    pins = microcontroller.pin
    return next(p for p in dir(pins) if getattr(pins, p) == of_pin)


if hasattr(board, "NEOPIXEL"):
    print(f"Testing NeoPixel on {get_gpio(board.NEOPIXEL)}")
    pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.5)

    pixel.fill(0xFF0000)
    time.sleep(0.5)
    pixel.fill(0x00FF00)
    time.sleep(0.5)
    pixel.fill(0x0000FF)
    time.sleep(0.5)
    pixel.fill(0x000000)
