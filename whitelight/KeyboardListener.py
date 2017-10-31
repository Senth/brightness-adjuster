import keyboard
import logging
from config import MANUAL_BRIGHTNESS
from BrightnessAdjuster import BrightnessAdjuster

logger = logging.getLogger(__name__)


class KeyboardListener:
    """Listen and capture keyboard events (hotkeys) for brightness"""

    def __init__(self, brightness_adjuster):
        self.brightness_adjuster = brightness_adjuster

    def __exit__(self, exc_type, exc_val, exc_tb):
        keyboard.clear_all_hotkeys()

    def register_hotkeys(self):
        i = 1
        for brightness in MANUAL_BRIGHTNESS:
            hotkey = 'win, F' + str(i)
            logger.debug('add hotkey: ' + hotkey + ' = ' + str(brightness))
            # keyboard.add_hotkey(hotkey, lambda brightness: self.brightness_adjuster.set_manual_brightness(brightness))
            keyboard.add_hotkey(hotkey, self.brightness_adjuster.set_manual_brightness, args=(self.brightness_adjuster, brightness))
            i += 1
