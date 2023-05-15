
## How to flash CircuitPython to a board

1. Reset ESP32-S3 to the Bootloader Mode
   * Press and hold **BOT** (*BOOT*) button (the one furthest away from the USB-C connector)
   * While holding the *BOOT* button, click the **RST** (*RESET*) button (the middle one)
   * Release the *BOOT* button

2. Execute the following command to flash the firmware (replace `<port>` with the actual port name, e.g. `--port /dev/ttyUSB0` or `--port COM3`):
   ```shell
   esptool.py --port <port> --baud 921600 write_flash --flash_mode dio --flash_freq 80m --flash_size 16MB --erase-all 0x0000 SW/lilygo-thmi-circuitpython.bin
   ```

3. Reset the chip to normal mode by pressing the *RESET* button again

4. After few seconds, the `CIRCUITPY` drive shall be available - specify its path in the `SW/circuitpy_drive.txt` file, which will be auto-generated on the first run of the `SW/build.py` script
   * Additionally, REPL is available on the same serial port as used above (115200 baud, 8N1)
