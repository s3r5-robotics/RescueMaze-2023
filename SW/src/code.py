import sys
import time

import board
import busio
import digitalio
import microcontroller
# noinspection PyUnresolvedReferences
from micropython import const

import adafruit_vl53l1x
import dynamixel
import neopixel
from adafruit_debouncer import Button

try:
    # This is only needed for typing
    from typing import Tuple
    from busio import I2C, UART
except ImportError:
    pass

# https://cdn-learn.adafruit.com/assets/assets/000/110/811/original/adafruit_products_Adafruit_Feather_ESP32-S3_Pinout.png?1649958374
PIN_DYNA_UART_RX = microcontroller.pin.GPIO38  # UART RX, Dyna RXTX
PIN_DYNA_UART_TX = microcontroller.pin.GPIO39  # UART TX, via 1kOhm to Dyna RXTX
PIN_DISTANCE_POWER_FRONT = microcontroller.pin.GPIO18
PIN_DISTANCE_POWER_LEFT = microcontroller.pin.GPIO17
PIN_DISTANCE_POWER_RIGHT = microcontroller.pin.GPIO16
PIN_DISTANCE_INT_FRONT = microcontroller.pin.GPIO15
PIN_DISTANCE_INT_LEFT = microcontroller.pin.GPIO14
PIN_DISTANCE_INT_RIGHT = microcontroller.pin.GPIO8
# PIN_CAMERA_CABLE_1 (blue colored wire) is GND
# PIN_CAMERA_CABLE_2 is +5V
PIN_CAMERA_CABLE_3 = microcontroller.pin.GPIO13  # To ESP32-CAM GPIO13
PIN_CAMERA_CABLE_4 = microcontroller.pin.GPIO12  # To ESP32-CAM GPIO15
PIN_CAMERA_CABLE_5 = microcontroller.pin.GPIO11  # To ESP32-CAM GPIO14
PIN_BUTTON = microcontroller.pin.GPIO10  # Button to GND


class DistanceSensor(adafruit_vl53l1x.VL53L1X):
    def __init__(self, i2c: I2C, power_switch: microcontroller.Pin, desired_address: int) -> None:
        # Power ON the sensor by setting the pin to HIGH state
        digitalio.DigitalInOut(power_switch).switch_to_output(value=True)
        # Wait a while for power to stabilise (from the datasheet: Boot duration is 1.2ms max)
        time.sleep(0.01)
        # Try to initialize parent class with the default address
        try:
            super().__init__(i2c)
        except ValueError:  # ValueError: No I2C device at address: 0x29
            try:
                super().__init__(i2c, address=desired_address)
            except ValueError:
                raise ValueError(f"No VL53L1X sensor found at default or 0x{desired_address} address")
        else:
            # Change the sensor address from default to desired
            self.set_address(desired_address)

        # None can be returned if the measurement is not ready yet - guard against that
        self.out_of_range_cm: int = const(500)
        self._last_distance: int = self.out_of_range_cm
        self._new_data: bool = False
        # Configure the sensor
        self.start_ranging()

    @property
    def new_data(self) -> bool:
        # The new data flag is only set here and cleared when the distance is read using the mm property
        if not self._new_data:
            self._new_data = self.data_ready
        return self._new_data

    @property
    def mm(self) -> int:
        d = self.distance
        if d is None:
            if self._new_data:
                # The data shall be available, but the reported distance is None.
                # Most probably the measurement is out of range.
                d = self.out_of_range_cm
            else:
                # The data is not ready yet, return the last known distance
                d = self._last_distance
        else:
            self._last_distance = d
        self._new_data = False
        return round(d * 10)


class DynamixelMotor(dynamixel.Dynamixel):
    # https://emanual.robotis.com/docs/en/dxl/ax/ax-12w/

    def __init__(self, uart: UART, motor_id: int, reverse_direction: bool = False):
        super().__init__(uart, motor_id)
        self.reverse_direction = reverse_direction
        self.speed = 0
        self.torque_enable = True

    @dynamixel.Dynamixel.speed.setter
    def speed(self, speed: float) -> None:
        # https://emanual.robotis.com/docs/en/dxl/ax/ax-12w/#moving-speed
        # TODO: Try to regulate speed
        if self.reverse_direction:
            speed = -speed
        if speed < 0:
            raw_speed = min(1.0, -speed) * 1023
        else:
            raw_speed = min(1.0, speed) * 1023 + 1024
        self.set_register_dual(dynamixel.DYN_REG_MOVING_SPEED_L, int(raw_speed))


def get_gpio(of_pin: microcontroller.Pin) -> str:
    # noinspections PyUnresolvedReferences
    pins = microcontroller.pin
    return next(p for p in dir(pins) if getattr(pins, p) == of_pin)


def i2c_scan(i2c: I2C) -> None:
    while not i2c.try_lock():
        time.sleep(0.001)
    try:
        print("I2C addresses found:", [hex(device_address) for device_address in i2c.scan()])
    finally:
        i2c.unlock()


def get_color_gradient(amplitude: float) -> Tuple[int, int, int]:
    # 0 ... red ... green ... blue ... 1
    if amplitude < 0.5:
        return int(0xFF * (0.5 - amplitude) * 2), int(0xFF * amplitude * 2), 0x00
    else:
        return 0x00, int(0xFF * (1 - amplitude) * 2), int(0xFF * amplitude * 2)


def wait_for_button_to_start(button: Button, pixel: neopixel.NeoPixel,
                             led_delay: float = 0.01, led_brightness: int = 0x20) -> None:
    print("Waiting for button press")
    while not button.pressed:
        button.update()
        pixel.fill((led_brightness, 0, 0))
        time.sleep(led_delay)
        pixel.fill((0, led_brightness, 0))
        time.sleep(led_delay)
        pixel.fill((0, 0, led_brightness))
        time.sleep(led_delay)
    print("Button pressed, start!")

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
        print(f"Can't keep up at {freq} Hz ({t_loop} > {loop_delay})")
    elif t_loop < loop_delay:
        time.sleep(loop_delay - t_loop)

    return round(100 * t_loop / loop_delay)


def main(loop_frequency: int = 50):
    # CircuitPython throws SyntaxError for multiline f-strings - either use single line or concatenation
    print(f"\nRunning on {board.board_id} ({sys.platform}), {sys.implementation.name} " +
          f"{sys.version}/{'.'.join(map(str, sys.implementation.version))}, mpy {sys.implementation.mpy}")

    # Initialize integrated peripherals
    i2c = board.STEMMA_I2C()
    dyna_uart = busio.UART(PIN_DYNA_UART_TX, PIN_DYNA_UART_RX, baudrate=1000000, timeout=0.1)
    # Initialize onboard peripherals
    pin = digitalio.DigitalInOut(PIN_BUTTON)
    pin.switch_to_input(digitalio.Pull.UP)
    button = Button(pin)
    pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.5)
    # Initialize distance sensors
    ds_front = DistanceSensor(i2c, PIN_DISTANCE_POWER_FRONT, 0x30)
    ds_left = DistanceSensor(i2c, PIN_DISTANCE_POWER_LEFT, 0x31)
    ds_right = DistanceSensor(i2c, PIN_DISTANCE_POWER_RIGHT, 0x32)
    # Motors
    ml = DynamixelMotor(dyna_uart, 6, reverse_direction=True)
    mr = DynamixelMotor(dyna_uart, 4)

    wait_for_button_to_start(button, pixel)

    cpu_usage = 0
    while True:
        t_loop_begin = time.monotonic()

        button.update()
        if button.pressed:
            print("Button pressed, exiting")
            break

        # Read distance sensors
        front, left, right = ds_front.mm, ds_left.mm, ds_right.mm

        max_dist = 500
        pixel.fill(get_color_gradient(min(min(front, left, right) / max_dist, 1)))

        max_speed = 0.3
        speed_ratio = min(max((front - (max_dist / 2)) / (max_dist / 2), -1), 1)
        speed = speed_ratio * max_speed
        ml.speed = speed
        mr.speed = speed

        print(f"CPU {cpu_usage}%, range (cm): {left: >5d} // {front: ^5d} \\\\ {right: <5d}, sr {speed_ratio:.3f}")

        cpu_usage = check_loop_frame_rate(loop_frequency, t_loop_begin)

    # Main program done, disable motors
    pixel.fill(0xFF0000)
    ml.torque_enable = False
    mr.torque_enable = False


main()
