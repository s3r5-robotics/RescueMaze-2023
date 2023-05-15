import sys
import time

import board
# noinspection PyUnresolvedReferences
from micropython import const

from hardware import motors, distance_sensors as ds, button, pixel

try:
    # This is only needed for typing
    from typing import Tuple, Optional
    from adafruit_debouncer import Button
    import neopixel
except ImportError:
    pass


def get_color_gradient(amplitude: float) -> Tuple[int, int, int]:
    # 0 ... red ... green ... blue ... 1
    if amplitude < 0.5:
        return int(0xFF * (0.5 - amplitude) * 2), int(0xFF * amplitude * 2), 0x00
    else:
        return 0x00, int(0xFF * (1 - amplitude) * 2), int(0xFF * amplitude * 2)


def wait_for_button_to_start(button: Button, pixel: Optional[neopixel.NeoPixel] = None,
                             led_delay: float = 0.01, led_brightness: int = 0x20) -> None:
    print("Waiting for button press...")
    while not button.pressed:
        button.update()
        if pixel:
            pixel.fill((led_brightness, 0, 0))
            time.sleep(led_delay)
            pixel.fill((0, led_brightness, 0))
            time.sleep(led_delay)
            pixel.fill((0, 0, led_brightness))
            time.sleep(led_delay)

    print("Button pressed, waiting for release...")

    while not button.released:
        button.update()

    print("Button clicked, start!")

    if pixel:
        pixel.fill(0xFF0000)
        time.sleep(0.5)
        pixel.fill(0x7F7F00)
        time.sleep(0.5)
        pixel.fill(0x00FF00)
        time.sleep(0.5)


def check_loop_frame_rate(freq: int, loop_start_time: float) -> float:
    # returns CPU usage in percent
    loop_delay = 1 / freq

    # Ensure loop runs at constant frequency
    t_loop = time.monotonic() - loop_start_time
    if t_loop > loop_delay:
        # print(f"Can't keep up at {freq} Hz ({t_loop} > {loop_delay})")
        pass
    elif t_loop < loop_delay:
        time.sleep(loop_delay - t_loop)

    return round(100 * t_loop / loop_delay)


def main(loop_frequency: int = 50):
    # CircuitPython throws SyntaxError for multiline f-strings - either use single line or concatenation
    print(f"\nRunning on {board.board_id} ({sys.platform}), {sys.implementation.name} " +
          f"{sys.version}/{'.'.join(map(str, sys.implementation.version))}, mpy {sys.implementation.mpy}")

    wait_for_button_to_start(button, pixel)

    cpu_usage = 0
    while True:
        t_loop_begin = time.monotonic()

        button.update()
        if button.pressed:
            print("Button pressed, exiting")
            break

        # Read distance sensors
        front, left, right = ds.front.mm, ds.left.mm, ds.right.mm

        max_dist = 500
        if pixel:
            pixel.fill(get_color_gradient(min(min(front, left, right) / max_dist, 1)))

        max_speed = 0.5
        speed_ratio = min(max((front - (max_dist / 2)) / (max_dist / 2), -1), 1)
        speed = speed_ratio * max_speed
        motors.l.speed = speed
        motors.r.speed = speed

        print(f"CPU {cpu_usage}%, range (cm): {left: >5d} // {front: ^5d} \\\\ {right: <5d}, sr {speed_ratio:.3f}")

        cpu_usage = check_loop_frame_rate(loop_frequency, t_loop_begin)

    # Main program done, disable motors
    if pixel:
        pixel.fill(0xFF0000)
    motors.l.torque_enable = False
    motors.r.torque_enable = False

    print("Waiting for button release")
    while not button.released:
        button.update()


def init() -> bool:
    init_ok = True

    try:
        motors.init()
    except Exception as e:
        print("Error initializing motors:", e)
        init_ok = False

    try:
        ds.init()
    except Exception as e:
        print("Error initializing distance sensors:", e)
        init_ok = False

    return init_ok


if init():
    while True:
        main()
else:
    print("Initialization failed, exiting")
