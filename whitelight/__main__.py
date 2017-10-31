import argparse
import logging
import sys
from subprocess import CalledProcessError
from time import sleep

from config import INITIALIZE_TIME
from RedshiftAdjuster import RedshiftAdjuster
from SunsetChecker import SunsetChecker
from BrightnessAdjuster import BrightnessAdjuster
from KeyboardListener import KeyboardListener

logger = logging.getLogger(__name__)

WAIT_TIME = 500


# -----------------------
# Program Logic
# -----------------------
def main():
    parser = argparse.ArgumentParser(description='Dynamic screen brightness.')
    parser.add_argument('-i', '--initialize-time', default=INITIALIZE_TIME, type=int)
    args = parser.parse_args()
    sleep(args.initialize_time)
    brightness_adjuster = BrightnessAdjuster()
    redshift_adjuster = RedshiftAdjuster()
    sunset_checker = SunsetChecker()
    keyboard_listener = KeyboardListener(brightness_adjuster)
    keyboard_listener.register_hotkeys()

    while True:
        try:
            sunset_checker.update()
            redshift_adjuster.set_redshift(sunset_checker.get_minutes_since_sunset())
        except CalledProcessError:
            logger.exception("Couldn't call a subprocess")
        sleep(WAIT_TIME)


# try:
main()
# except:
#     logger.exception("Main exception: " + str(sys.exc_info()))