import logging
import types
from subprocess import call
from config import DISPLAYS, MANUAL_BRIGHTNESS

logger = logging.getLogger(__name__)


class BrightnessAdjuster:
    AUTO_CLAMP_BRIGHTNESS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    MIN_DIFF = 7

    def __init__(self):
        self.auto_mode = False
        self.brightness = -100
        self.auto_brightness = -100

    def set_auto_brightness(self, lux):
        if self.auto_mode:
            new_brightness = int(lux * 100)
            diff_brightness = abs(self.auto_brightness - new_brightness)

            if diff_brightness >= BrightnessAdjuster.MIN_DIFF:
                clamped_brightness = BrightnessAdjuster._get_clamped_brightness(new_brightness)

                # New brightness
                if clamped_brightness != self.brightness:
                    self.auto_brightness = new_brightness
                    self._set_brightness(clamped_brightness)

    def toggle_auto_brightness(self, on):
        self.auto_mode = on

    def set_manual_brightness(self, brightness):
        """Set the manual brightness. Automatically turns off auto brightness"""
        self.auto_mode = False
        self._set_brightness(brightness)

    def _set_brightness(self, brightness):
        # List
        if isinstance(brightness, types.ListType):
            self.brightness = brightness[1]
        # Int
        else:
            self.brightness = brightness

        logger.info('Set brightness to ' + str(brightness))
        for index, display in enumerate(DISPLAYS):
            if isinstance(brightness, types.ListType):
                display_brightness = brightness[index]
                call(['ddcutil', '-d', display, 'setvcp', '10', str(self.brightness)])
            else:
                call(['ddcutil', '-d', display, 'setvcp', '10', str(self.brightness)])

    @staticmethod
    def _get_clamped_brightness(newBrightness):
        closest_value = 100
        closest_mode = 50

        for mode in BrightnessAdjuster.AUTO_CLAMP_BRIGHTNESS:
            diff_value = abs(newBrightness - mode)
            if diff_value < closest_value:
                closest_value = diff_value
                closest_mode = mode

        return closest_mode
