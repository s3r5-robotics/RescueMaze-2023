import time

# noinspection PyPackageRequirements
import board
import busio
import digitalio
import displayio
import microcontroller
import paralleldisplay
# noinspection PyUnresolvedReferences
from micropython import const

import adafruit_vl53l1x
import dynamixel
import neopixel
from adafruit_debouncer import Button
from adafruit_display_shapes.rect import Rect
from adafruit_st7789 import ST7789

try:
    # This is only needed for typing
    from typing import Type
except ImportError:
    pass

try:
    # noinspection PyUnresolvedReferences
    i2c = busio.I2C(board.GROVE1_PIN4, board.GROVE1_PIN3, frequency=400000)
except RuntimeError as e:
    print("Error while initializing I2C:", e)
    i2c = None


class Motor(dynamixel.Dynamixel):
    # https://emanual.robotis.com/docs/en/dxl/ax/ax-12a/

    def __init__(self, uart: busio.UART, motor_id: int, reverse_direction: bool = False):
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


class Motors:
    l: Motor
    r: Motor
    # Aliases for l/r
    left: Motor
    right: Motor

    def __new__(cls: Type['Motors']) -> 'Motors':
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
        # noinspection PyUnresolvedReferences
        return cls._instance

    @classmethod
    def init(cls):
        # noinspection PyUnresolvedReferences
        uart = busio.UART(tx=board.GROVE3_PIN3, rx=board.GROVE3_PIN4, baudrate=1000000, timeout=0.1)

        cls.l = Motor(uart, 6, reverse_direction=True)
        cls.r = Motor(uart, 4)

        cls.left = cls.l
        cls.right = cls.r


class DistanceSensor(adafruit_vl53l1x.VL53L1X):
    def __init__(self, i2c_: busio.I2C, power_switch: digitalio.DigitalInOut, desired_address: int) -> None:
        # Power ON the sensor by setting the pin to HIGH state
        power_switch.value = True
        # Wait a while for power to stabilise (from the datasheet: Boot duration is 1.2ms max)
        time.sleep(0.01)
        # Try to initialize parent class with the default address
        super().__init__(i2c_)
        # Change the sensor address from default to desired
        self.set_address(desired_address)

        # None can be returned if the measurement is not ready yet - guard against that
        self.out_of_range_cm: int = const(500)
        self._last_distance: int = self.out_of_range_cm
        self._new_data: bool = False
        # Configure the sensor
        self.distance_mode = 1  # 1=short (up to 136cm), 2=long (up to 360cm)
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


class DistanceSensors:
    l: DistanceSensor
    f: DistanceSensor
    r: DistanceSensor
    # Aliases for l/f/r
    left: DistanceSensor
    front: DistanceSensor
    right: DistanceSensor

    def __new__(cls: Type['DistanceSensors']) -> 'DistanceSensors':
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
        # noinspection PyUnresolvedReferences
        return cls._instance

    @classmethod
    def init(cls):
        # noinspection PyUnresolvedReferences
        power_pins = (board.SD_MOSI, board.SD_CLK, board.SD_MISO)

        # First, initialize all power pins to OFF state to prevent pull-ups from powering other sensors
        power_pins = [digitalio.DigitalInOut(pin) for pin in power_pins]
        for pin in power_pins:
            pin.switch_to_output(value=False)
        time.sleep(0.001)

        cls.l = DistanceSensor(i2c, power_pins[0], 0x30)
        cls.f = DistanceSensor(i2c, power_pins[1], 0x31)
        cls.r = DistanceSensor(i2c, power_pins[2], 0x32)

        cls.left = cls.l
        cls.front = cls.f
        cls.right = cls.r


def get_gpio(of_pin: microcontroller.Pin) -> str:
    # noinspections PyUnresolvedReferences
    pins = microcontroller.pin
    return next(p for p in dir(pins) if getattr(pins, p) == of_pin)


def i2c_scan(i2c_: board.I2C = i2c) -> None:
    while not i2c_.try_lock():
        time.sleep(0.001)
    try:
        print("I2C addresses found:", [hex(device_address) for device_address in i2c_.scan()])
    finally:
        i2c_.unlock()


def init_display() -> displayio.Display:
    # Send one pulse to set max. brightness
    bl = digitalio.DigitalInOut(board.LCD_BL)
    bl.switch_to_output(value=False)
    bl.value = True

    # Use built-in display initialized during board initialization, if available
    if hasattr(board, "DISPLAY"):
        return board.DISPLAY

    # The parallel bus and pins are then in use by the display until displayio.release_displays() is called
    # even after a reload. (It does this so CircuitPython can use the display after your code is done.) So,
    # the first  time you initialize a display bus in code.py you should call displayio.release_displays()
    # first, otherwise it will error after the first code.py run.
    displayio.release_displays()

    # noinspection PyArgumentList,PyUnresolvedReferences
    bus = paralleldisplay.ParallelBus(
        data_pins=board.LCD_DATA, command=board.LCD_DC_RS, chip_select=board.LCD_CS, write=board.LCD_WR_PCLK
    )

    return ST7789(bus, width=240, height=240, rowstart=80)


def display_test():
    dsp = init_display()

    # Make the display context
    splash = displayio.Group()
    dsp.show(splash)

    # Make a background color fill
    color_bitmap = displayio.Bitmap(dsp.width, dsp.height, 1)
    color_palette = displayio.Palette(1)
    color_palette[0] = 0x000010
    bg_sprite = displayio.TileGrid(color_bitmap, x=0, y=0, pixel_shader=color_palette)
    splash.append(bg_sprite)

    # Draw shapes
    rect = Rect(80, 20, 41, 41, fill=0x00FF00)
    splash.append(rect)


_button_pin = digitalio.DigitalInOut(board.BUTTON_BOT)
_button_pin.switch_to_input(digitalio.Pull.UP)

button = Button(_button_pin)
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.5) if hasattr(board, "NEOPIXEL") else None
motors = Motors()
distance_sensors = DistanceSensors()
