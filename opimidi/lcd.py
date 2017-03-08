
import glob
import logging
import os
import time

logger = logging.getLogger("lcd")

BACKLIGHT_LED = "/sys/devices/platform/opimidi-lcd-leds/leds/backlight"
GPIO_LABEL = "pcf8574"

GPIO_LINES = {
        "RS": 0,
        "RW": 1,
        "E": 2,
        # BL (3) is handled by gpio-leds interface
        "DB4": 4,
        "DB5": 5,
        "DB6": 6,
        "DB7": 7,
        }

CLEAR_DISPLAY_CMD = 0x01

RETURN_HOME_CMD = 0x02

ENTRY_MODE_CMD = 0x04
EM_INCREMENT = 0x02
EM_SHIFT = 0x01

DISPLAY_CONTROL_CMD = 0x08
DC_BLINK_BIT = 0x01
DC_CURSOR_BIT = 0x02
DC_DISPLAY_BIT = 0x04

FUNCTION_SET_CMD = 0x20
FS_4BITS = 0x10
FS_2LINES = 0x08
FS_FONT5x10 = 0x04

SET_DDRAM_ADDR_CMD = 0x80
DDRAM_ADDR_MASK = 0x7f

class LCD:
    def __init__(self):
        self._gpio_v_files = {}
        self._increment = None
        self._shift = None
        self._backlight_v_fn = os.path.join(BACKLIGHT_LED, "brightness")
        self._find_gpio()
        self._init()
        self.lines = 2
        self.width = 16

    def _find_gpio(self):
        for gpiochip_path in glob.glob("/sys/class/gpio/gpiochip*"):
            label_fn = os.path.join(gpiochip_path, "label")
            with open(label_fn, "rt") as label_f:
                label = label_f.readline().strip()
                logger.debug("%r is %r", os.path.basename(gpiochip_path), label)
                if label == GPIO_LABEL:
                    break
        else:
            raise RuntimeError("Could not find GPIO chip {!r}".format(GPIO_LABEL))

        base_fn = os.path.join(gpiochip_path, "base")
        with open(base_fn, "rt") as base_f:
            base = int(base_f.readline().strip())

        for name, bit in GPIO_LINES.items():
            gpio_num = base + bit
            logger.debug("%s is GPIO#%i", name, gpio_num)
            bit_path = "/sys/class/gpio/gpio{}".format(gpio_num)
            if not os.path.isdir(bit_path):
                logger.debug("Exporting GPIO#%i", gpio_num)
                with open("/sys/class/gpio/export", "wt") as export_f:
                    print(gpio_num, file=export_f)
            direction_fn = os.path.join(bit_path, "direction")
            # check if direction is already ok, as we may have no permission
            # to write there
            with open(direction_fn, "rt") as direction_f:
                direction = direction_f.readline().strip()
            if direction != "out":
                logger.debug("Setting GPIO#%i direction to 'out'", gpio_num)
                with open(direction_fn, "wt") as direction_f:
                    print("out", file=direction_f)
            self._gpio_v_files[name] = os.path.join(bit_path, "value")

    def _init(self):
        self._set_bit("RW", 0)
        self._set_bit("RS", 0)
        self._set_bit("E", 0)

        # initialize 4-bit interface and function
        self._write_4bits(0x03)
        time.sleep(0.005)
        self._write_4bits(0x03)
        time.sleep(0.0002)
        self._write_4bits(0x03)
        time.sleep(0.0002)
        self._write_4bits(0x02)
        time.sleep(0.0002)

        self._write_cmd(FUNCTION_SET_CMD | FS_2LINES | FS_FONT5x10)
        self._write_cmd(CLEAR_DISPLAY_CMD)

    def _set_bit(self, name, value):
        with open(self._gpio_v_files[name], "wt") as bit_f:
            #logger.debug("      %2s: %s", name, value)
            print(value, file=bit_f)

    def _write_4bits(self, value):
        self._set_bit("E", 0)
        self._set_bit("RW", 0)
        self._set_bit("DB4", value & 0x01)
        value >>= 1
        self._set_bit("DB5", value & 0x01)
        value >>= 1
        self._set_bit("DB6", value & 0x01)
        value >>= 1
        self._set_bit("DB7", value & 0x01)
        time.sleep(0.0005)
        self._set_bit("E", 1)
        time.sleep(0.0005)
        self._set_bit("E", 0)

    def _write_cmd(self, cmd):
        logger.debug("    CMD:  0x%02x", cmd)
        self._write_4bits((cmd >> 4) & 0x0f)
        time.sleep(0.0002)
        self._write_4bits(cmd & 0x0f)
        time.sleep(0.0002)

    def _write_byte(self, data):
        logger.debug("    data: 0x%02x", data)
        self._set_bit("RS", 1)
        self._write_4bits((data >> 4) & 0x0f)
        time.sleep(0.0002)
        self._write_4bits(data & 0x0f)
        self._set_bit("RS", 0)
        time.sleep(0.0002)

    def get_write_files(self):
        return list(self._gpio_v_files.values()) + [self._backlight_v_fn]

    def write_bytes(self, string):
        if not isinstance(string, bytes):
            string = string.encode("raw_unicode_escape", "replace")
        for byte in string:
            self._write_byte(byte)

    def set_backlight(self, on=True):
        with open(self._backlight_v_fn, "wt") as backlight_v_f:
            print(255 if on else 0, file=backlight_v_f)

    def clear(self):
        self._write_cmd(CLEAR_DISPLAY_CMD)

    def set_display(self, on=True, blink=False, cursor=False):
        cmd = DISPLAY_CONTROL_CMD
        if on:
            cmd |= DC_DISPLAY_BIT
        if blink:
            cmd |= DC_BLINK_BIT
        if cursor:
            cmd |= DC_CURSOR_BIT
        self._write_cmd(cmd)

    def set_entry_mode(self, increment=True, shift=False):
        cmd = ENTRY_MODE_CMD
        if increment:
            cmd |= EM_INCREMENT
        if shift:
            cmd |= EM_SHIFT
        self._write_cmd(cmd)
        self._increment = increment
        self._shift = shift

    def return_home(self):
        self.write_cmd(RETURN_HOME_CMD)
        time.sleep(0.002)

    def set_ddram_addr(self, addr):
        cmd = SET_DDRAM_ADDR_CMD | (addr & DDRAM_ADDR_MASK)
        self._write_cmd(cmd)

    def write(self, line, column, string):
        if line not in (0, 1):
            raise ValueError("Line must be 0 or 1")
        if column < 0 or column >= 0x40:
            raise ValueError("Wrong column")
        self.set_ddram_addr(0x40 * line + column)
        if not self._increment:
            self.set_entry_mode(True, self._shift)
        self.write_bytes(string[:0x40 - column])

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    lcd = LCD()
    lcd.set_display(cursor=False, blink=False)
    lcd.set_backlight(True)
    lcd.write(0, 0, "Hello World!")
    input()
    lcd.clear()
    lcd.set_backlight(False)
