import sys
import time

import board
import digitalio
import microcontroller
# noinspection PyUnresolvedReferences
from micropython import const

import adafruit_vl53l1x
import neopixel

try:
    # This is only needed for typing
    from typing import Tuple
    from busio import I2C
except ImportError:
    pass

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
PIN_CAMERA_CABLE_4 = microcontroller.pin.GPIO12  # To ESP32-CAM GPIO12
PIN_CAMERA_CABLE_5 = microcontroller.pin.GPIO11  # Button to GND


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


def main():
    # CircuitPython throws SyntaxError for multiline f-strings - either use single line or concatenation
    print(f"\nRunning on {board.board_id} ({sys.platform}), {sys.implementation.name} " +
          f"{sys.version}/{'.'.join(map(str, sys.implementation.version))}, mpy {sys.implementation.mpy}")

    # Initialize integrated peripherals
    i2c = board.STEMMA_I2C()
    # Initialize onboard peripherals
    pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.5)
    # Initialize distance sensors
    ds_front = DistanceSensor(i2c, PIN_DISTANCE_POWER_FRONT, 0x30)
    ds_left = DistanceSensor(i2c, PIN_DISTANCE_POWER_LEFT, 0x31)
    ds_right = DistanceSensor(i2c, PIN_DISTANCE_POWER_RIGHT, 0x32)

    while True:
        # Wait for all sensors to have new data
        while not (ds_front.new_data and ds_left.new_data and ds_right.new_data):
            time.sleep(0.001)
        front, left, right = ds_front.mm, ds_left.mm, ds_right.mm

        print(f"Range (cm): {left: >5d} // {front: ^5d} \\\\ {right: <5d}")

        max_dist = 500
        pixel.fill(get_color_gradient(min(min(front, left, right) / max_dist, 1)))


main()
