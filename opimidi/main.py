
import logging

from .lcd import LCD

def main():
    logging.basicConfig(level=logging.DEBUG)
    lcd = LCD()
    lcd.set_display(cursor=False, blink=False)
    lcd.set_backlight(True)
    lcd.write(0, 0, "Hello World!")
    input()
    lcd.clear()
    lcd.set_backlight(False)
