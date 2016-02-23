#!/usr/bin/python2
import logging
import cv2
import re
from datetime import datetime
from time import gmtime, strftime, sleep
from subprocess import call, Popen, check_output, CalledProcessError


# Always disabled adjustment and set it to default when any of these programs are running
PROGRAMS_DISABLED = ['mplayer', 'smplayer', 'vlc']
# Always disabled adjustment and set it to default when anything is in fullscreen
FULLSCREEN_DISABLED = True

# Displays to change brightness of
DISPLAYS = ['adl:0:0', 'adl:0:1', 'adl:0:4']
CAMERA = "/dev/video0"

# Brightness adjustments depending on the sunset time.
# First tuplet is minutes to sunset (can be negative)
# Second tuplet is brightness in the range [0.0,1.0]
ADJUST_MAX = 100
ADJUST_MIN = 0
ADJUST_MOVIE_MIN = 50


# --- Other non-essential settings ---

# How long to wait between checking if something has changed, in seconds
WAIT_TIME = 3

LOG_LOCATION = '/tmp/brightnessAdjuster-camera.log'
LOG_LEVEL = logging.INFO


# Setup logging
logging.basicConfig(format='%(asctime)s:%(levelname)s: %(message)s', filename=LOG_LOCATION, level=LOG_LEVEL, datefmt='%Y-%m-%d %H:%M:%S')

class AmbientLightChecker:
    def __init__(self):
        self.lux = 0

    def __exit__(self, exc_type, exc_value, traceback):
        if self.camera is not None:
            self.camera.release()

    def update(self):
        self.camera = cv2.VideoCapture(0)
        self.camera.set(3,320)
        self.camera.set(4,240)
        self.camera.set(5,15)
        ret, image = self.camera.read()

        grayImage = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        grayImage = cv2.resize(grayImage, (1,1))
        self.lux = int(grayImage[0][0])
        logging.debug("Camera Brightness: " + str(self.lux))
        self.camera.release()

    def getLux(self):
        return self.lux

    def getNormalizedLux(self):
        return self.lux * 100 / 256
        

class ProgramChecker:
    DISPLAY=':0.0'

    def __init__(self, programsDisable, fullscreenDisable):
        self.programsDisable = programsDisable
        self.fullscreenDisable = fullscreenDisable
        self.fullscreenWindowIds = []

    def checkForFullscreen(self):
        if self.fullscreenDisable:
            # Check old windows if they should be removed (as they aren't in fullscreen anymore
            for windowId in list(self.fullscreenWindowIds):
                if not self._isWindowFullscreen(windowId):
                    self.fullscreenWindowIds.remove(windowId)

            windowIdOutput = check_output(['xprop', '-display', self.DISPLAY, '-root', '_NET_ACTIVE_WINDOW']).decode('utf-8')
            windowId = windowIdOutput[40:-1]
            logging.debug("Window id: " + windowId)
            if self._isWindowFullscreen(windowId):
                if self.fullscreenWindowIds.count(windowId) == 0:
                    logging.info("Fullscreen window found!")
                    self.fullscreenWindowIds.append(windowId)


    def _isWindowFullscreen(self, windowId):
        if len(windowId) == 9:
            windowOutput = check_output(['xprop', '-display', self.DISPLAY, '-id', windowId]).decode('utf-8')
            if windowOutput.find('_NET_WM_STATE_FULLSCREEN') != -1:
                return True
            else:
                return False

    def isFullscreenActive(self):
        if len(self.fullscreenWindowIds) > 0:
            return True
        else:
            return False

    def shouldBeDisabled(self):
        for program in self.programsDisable:
            if (self.isProgramRunning(program)):
                return True

        # Check fullscreen
        self.checkForFullscreen()
        if self.isFullscreenActive():
            logging.debug("Fullscreen is active")
            return True

        return False

    def isProgramRunning(self, searchFor):
        output = check_output(['ps', 'aux']).decode('utf-8')
        if output.find(searchFor) != -1:
            logging.debug("Found program " + searchFor)
            return True
        else:
            return False


class BrightnessAdjuster:
    def __init__(self, adjustMin, adjustMax, adjustMovieMin):
        self.adjustMin = adjustMin
        self.adjustMax = adjustMax
        self.adjustMovieMin = adjustMovieMin
        self.movieMode = False
        self.brightness = 0
        
    def setBrightness(self, brightness):
        oldBrightness = self.brightness
        if self.movieMode:
            self.brightness = max(brightness, self.adjustMovieMin)
        else:
            self.brightness = brightness

        diffBrightness = abs(oldBrightness - self.brightness)
        if diffBrightness >= 5:
            for display in DISPLAYS:
                Popen(['ddccontrol', '-r', '0x10', '-w', str(self.brightness), display])

    def enableMovieMode(self):
        self.movieMode = True

    def disableMovieMode(self):
        self.movieMode = False


# -----------------------
# Program Logic
# -----------------------
programChecker = ProgramChecker(PROGRAMS_DISABLED, FULLSCREEN_DISABLED)
brightnessAdjuster = BrightnessAdjuster(ADJUST_MIN, ADJUST_MAX, ADJUST_MOVIE_MIN)
ambientLightChecker = AmbientLightChecker()


while True:
    try:
        ambientLightChecker.update()
        lux = ambientLightChecker.getNormalizedLux()
        if programChecker.shouldBeDisabled():
            brightnessAdjuster.enableMovieMode()
        else:
            brightnessAdjuster.disableMovieMode()
        brightnessAdjuster.setBrightness(lux)
    except CalledProcessError:
        logging.warning("Couldn't call a subprocess")
    sleep(WAIT_TIME)
