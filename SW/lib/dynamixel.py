# The MIT License (MIT)
#
# Copyright (c) 2020 Lucian Copeland
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
`dynamixel`
================================================================================

Circuitpython driver library for the Dynamixel series of servo motors from
Robotis.

Dynamixels are a series of smart actuators designed to form the connecting
joints on a robot or other mechanical structure. They utilize an addressed UART
bus system, allowing them to be daisy chained to one another with a minimum of
cabling. Dynamixels also contain an integrated controller for setting torque and
temperature limits, speed adjustment, continuous rotation mode, and other
features.

The AX series is supported by this library. Support for the RX and MX series is
likely but untested.

**Software and Dependencies:**

# * Adafruit's Circuitpython Releases: https://github.com/adafruit/circuitpython/releases
# * Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
# * Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register

* Author(s):

    - Lucian Copeland (hierophect)
"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/hierophect/CircuitPython_dynamixel.git"

import time

# noinspection PyUnresolvedReferences
from micropython import const

try:
    # This is only needed for typing
    from typing import Iterable, Optional
    from busio import UART
except ImportError:
    pass

# Addresses
# EEPROM
DYN_REG_MODEL_NUMBER_L = const(0x00)
DYN_REG_MODEL_NUMBER_H = const(0x01)
DYN_REG_FIRMWARE_VER = const(0x02)
DYN_REG_ID = const(0x03)
DYN_REG_BAUD = const(0x04)
DYN_REG_RETURN_DELAY = const(0x05)
DYN_REG_CW_ANGLE_LIMIT_L = const(0x06)
DYN_REG_CW_ANGLE_LIMIT_H = const(0x07)
DYN_REG_CCW_ANGLE_LIMIT_L = const(0x08)
DYN_REG_CCW_ANGLE_LIMIT_H = const(0x09)
# -- Reserved = const(0x00)
DYN_REG_LIMIT_MAX_TEMP = const(0x0B)
DYN_REG_LIMIT_MIN_VOLT = const(0x0C)
DYN_REG_LIMIT_MAX_VOLT = const(0x0D)
DYN_REG_MAX_TORQUE_L = const(0x0E)
DYN_REG_MAX_TORQUE_H = const(0x0F)
DYN_REG_STATUS_RETURN_LEVEL = const(0x10)
DYN_REG_ALARM_LED = const(0x11)
DYN_REG_ALARM_SHUTDOWN = const(0x12)
# -- Reserved = const(0x00)
DYN_REG_DOWN_CALIB_L = const(0x14)
DYN_REG_DOWN_CALIB_H = const(0x15)
DYN_REG_UP_CALIB_L = const(0x16)
DYN_REG_UP_CALIB_H = const(0x17)

# RAM = const(0x00)
DYN_REG_TORQUE_ENABLE = const(0x18)
DYN_REG_LED = const(0x19)
DYN_REG_CW_COMPLIANCE_MARGIN = const(0x1A)
DYN_REG_CCW_COMPLIANCE_MARGIN = const(0x1B)
DYN_REG_CW_COMPLIANCE_SLOPE = const(0x1C)
DYN_REG_CCW_COMPLIANCE_SLOPE = const(0x1D)
DYN_REG_GOAL_POSITION_L = const(0x1E)
DYN_REG_GOAL_POSITION_H = const(0x1F)
DYN_REG_MOVING_SPEED_L = const(0x20)
DYN_REG_MOVING_SPEED_H = const(0x21)
DYN_REG_TORQUE_LIMIT_L = const(0x22)
DYN_REG_TORQUE_LIMIT_H = const(0x23)
DYN_REG_PRESENT_POSITION_L = const(0x24)
DYN_REG_PRESENT_POSITION_H = const(0x25)
DYN_REG_PRESENT_SPEED_L = const(0x26)
DYN_REG_PRESENT_SPEED_H = const(0x27)
DYN_REG_PRESENT_LOAD_L = const(0x28)
DYN_REG_PRESENT_LOAD_H = const(0x29)
DYN_REG_PRESENT_VOLTAGE = const(0x2A)
DYN_REG_PRESENT_TEMP = const(0x2B)
DYN_REG_REGISTERED_INST = const(0x2C)
# -- Reserved = const(0x00)
DYN_REG_MOVING = const(0x2E)
DYN_REG_LOCK = const(0x2F)
DYN_REG_PUNCH_L = const(0x30)
DYN_REG_PUNCH_H = const(0x31)

DYN_ERR_NONE = const(0x00)
DYN_ERR_VOLTAGE = const(0x01)
DYN_ERR_ANGLE = const(0x02)
DYN_ERR_OVERHEAT = const(0x04)
DYN_ERR_RANGE = const(0x08)
DYN_ERR_CHECKSUM = const(0x10)
DYN_ERR_OVERLOAD = const(0x20)
DYN_ERR_INST = const(0x40)
DYN_ERR_INVALID = const(0x80)

DYN_INST_PING = const(0x01)
DYN_INST_READ = const(0x02)
DYN_INST_WRITE = const(0x03)
DYN_INST_REG_WRITE = const(0x04)
DYN_INST_ACTION = const(0x05)
DYN_INST_RESET = const(0x06)
DYN_INST_SYNC_WRITE = const(0x83)

DYN_BROADCAST_ID = const(0xFE)


# Send packet structure:
# | 0xFF | 0xFF | ID | LEN | INST | PARAM_1-PARAM_N | CHECKSUM |
# Status Packet structure
# | 0xFF | 0xFF | ID | LEN | ERROR | VALUE_1-VALUE_N | CHECKSUM |

class Dynamixel:
    def __init__(self, uart: UART, motor_id: int, ping: bool = True, log_retries: bool = False):
        self.log_retries = log_retries
        self._uart = uart
        self.last_error = DYN_ERR_INVALID
        self.id = motor_id
        # Optionally check whether motor is actually present
        if ping:
            self.ping()

    def _write(self, data: bytes, response_length: int) -> bytes:
        # Motors are connected as such:
        #  uC RX>-----------------/-- <Motor RXTX
        #  uC TX>---[ 1 kOhm ]---/
        # This enables half-duplex communication without damaging any pins (when
        # Motor TX is output, it would otherwise need to override uC TX), but has
        # a drawback that all sent data is also immediately received.

        # Write the command and discard the echoed data
        self._uart.write(data)
        rx = self._uart.read(len(data))
        # A safety check to make sure that we did not discard any other pending data
        if rx != data:
            print(f"Half-duplex UART error sent {data}, received {rx}")

        # Optionally read the response
        if not response_length:
            return b''
        time.sleep(0.001)  # Wait a bit for the response
        return self._uart.read(response_length)

    def _write_command(self, instruction: int, write_data: bytes = b'', response_len: Optional[int] = 0) -> bytes:
        # TX length is always at least 2 for instruction and checksum
        tx_len = 2 + len(write_data)
        # RX length is always at least 6 for status packet, except for broadcast when there is no response
        rx_len = 0 if (response_len is None) else 6 + response_len
        # Checksum is sum of all transmitted data, inverted and truncated to 8 bits
        checksum = (~(self.id + tx_len + instruction + sum(write_data)) + 256) % 256
        # Write command and read response
        rsp = self._write(
            bytes((255, 255, self.id, tx_len, instruction)) + write_data + bytes((checksum,)),
            rx_len
        )
        if not rx_len:
            return b''

        if (not rsp) or len(rsp) != rx_len:
            raise RuntimeError(f"Could not exec 0x{instruction:02x} on motor ID {self.id}")
        self.last_error = rsp[4]
        if self.last_error != DYN_ERR_NONE:
            raise RuntimeError(f"Exec 0x{instruction:02x} on motor ID {self.id} resulted in {self.last_error:02x}")
        return rsp

    def _command(self, instruction: int, write_data: bytes = b'', response_len: Optional[int] = 0) -> bytes:
        # Retry command once if failed (e.g. due to high baud rate and noise)
        try:
            return self._write_command(instruction, write_data, response_len)
        except RuntimeError:
            if self.log_retries:
                print(f"Retrying command 0x{instruction:02x} for Dynamixel motor ID {self.id}")
            time.sleep(0.005)
        return self._write_command(instruction, write_data, response_len)

    # -----------------------
    # Dynamixel Instructions:
    # -----------------------

    def ping(self):
        return self._command(DYN_INST_PING)

    def read_data(self, reg_addr: int, n_bytes: int):
        return self._command(DYN_INST_READ, bytes((reg_addr, n_bytes)), n_bytes)

    def write_data(self, reg_addr: int, parameters: Iterable[int]):
        return self._command(DYN_INST_WRITE, bytes((reg_addr,)) + bytes(parameters))
        # TODO: Check for error only if this is not broadcast mode

    # TODO: def reg_write(self, dyn_id, reg_addr, parameters):
    # TODO: def action(self, dyn_id):
    # TODO: def reset(self, dyn_id):
    # TODO: def sync_write(self, parameters):

    # -------------
    # API Functions
    # -------------

    def set_register(self, reg_addr: int, data: int):
        self.write_data(reg_addr, (data,))

    def set_register_dual(self, reg_addr, data):
        self.write_data(reg_addr, (data & 0xFF, data >> 8))

    def get_register(self, reg_addr):
        packet = self.read_data(reg_addr, 1)
        return packet[5]

    def get_register_dual(self, reg_addr: int):
        packet = self.read_data(reg_addr, 2)
        return packet[5] | (packet[6] << 8)

    def parse_error(self, error=0xFF):
        if error == 0xFF:
            error = self.last_error

        if error == DYN_ERR_NONE:
            print("No Errors Reported\n")
        elif error & DYN_ERR_VOLTAGE:
            print("Voltage Error\n")
        elif error & DYN_ERR_ANGLE:
            print("Angle Limit Error\n")
        elif error & DYN_ERR_OVERHEAT:
            print("Overheat Error\n")
        elif error & DYN_ERR_RANGE:
            print("Instruction Range Error\n")
        elif error & DYN_ERR_CHECKSUM:
            print("Bad Checksum Error\n")
        elif error & DYN_ERR_OVERLOAD:
            print("Over Load Limit Error\n")
        elif error & DYN_ERR_INST:
            print("Invalid Instruction Error\n")
        elif error & DYN_ERR_INVALID:
            print("No errors available at startup, or for reset or broadcast" \
                  " instructions\n")

    @property
    def torque_enable(self) -> bool:
        """Motor Torque On/Off"""
        return bool(self.get_register(DYN_REG_TORQUE_ENABLE))

    @torque_enable.setter
    def torque_enable(self, value: bool) -> None:
        """Motor Torque On/Off"""
        self.set_register(DYN_REG_TORQUE_ENABLE, int(value))

    @property
    def led(self) -> bool:
        """Status LED status"""
        return bool(self.get_register(DYN_REG_LED))

    @led.setter
    def led(self, value: bool) -> None:
        """Status LED On/Off"""
        self.set_register(DYN_REG_LED, int(value))

    @property
    def position(self) -> int:
        """
        Present Position

        The available position range is 0 to 1,023 (0x3FF) and the per-unit value is 0.29°.
        If it is set to Wheel Mode, Goal Position value is not used.
        """
        return self.get_register_dual(DYN_REG_PRESENT_POSITION_L)

    @position.setter
    def position(self, position: int) -> None:
        """
        Goal Position

        The available position range is 0 to 1,023 (0x3FF) and the per-unit value is 0.29°.
        If it is set to Wheel Mode, Goal Position value is not used.
        """
        self.set_register_dual(DYN_REG_GOAL_POSITION_L, position)

    @property
    def speed(self) -> int:
        return self.get_register_dual(DYN_REG_PRESENT_SPEED_L)

    @speed.setter
    def speed(self, speed: int) -> None:
        self.set_register_dual(DYN_REG_MOVING_SPEED_L, speed)

    @property
    def torque_limit(self) -> int:
        return self.get_register_dual(DYN_REG_TORQUE_LIMIT_L)

    @torque_limit.setter
    def torque_limit(self, torque_limit: int) -> None:
        self.set_register_dual(DYN_REG_TORQUE_LIMIT_L, torque_limit)

    @property
    def load(self) -> int:  # Read-only
        return self.get_register_dual(DYN_REG_PRESENT_LOAD_L)

    @property
    def voltage(self) -> int:  # Read-only
        return self.get_register(DYN_REG_PRESENT_VOLTAGE)

    @property
    def temperature(self) -> int:  # Read-only
        return self.get_register(DYN_REG_PRESENT_TEMP)

    @property
    def registered(self) -> int:  # Read-only
        return self.get_register(DYN_REG_REGISTERED_INST)

    @property
    def moving(self) -> int:  # Read-only
        return self.get_register(DYN_REG_MOVING)

    @property
    def punch(self) -> int:
        return self.get_register_dual(DYN_REG_PUNCH_L)

    @punch.setter
    def punch(self, minimum_drive_current: int) -> None:
        self.set_register_dual(DYN_REG_PUNCH_L, minimum_drive_current)
