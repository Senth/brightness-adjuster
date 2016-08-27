#!/usr/bin/python2
import logging
import ephem
import cv2
import re
import argparse
from datetime import datetime
from time import gmtime, strftime, sleep
from subprocess import Popen, check_output, CalledProcessError


# Always disabled adjustment and set it to default when any of these programs are running
PROGRAMS_DISABLED = ['mplayer', 'smplayer', 'vlc']
# Always disabled adjustment and set it to default when anything is in fullscreen
FULLSCREEN_DISABLED = True

# Displays to change brightness of, check with ddccontrol -p
DISPLAYS = ['adl:0:0', 'adl:0:1', 'adl:0:4']
# XScreen, check with "echo $DISPLAY" in a terminal
X_SCREEN = ':0.0'
CAMERA = "/dev/video0"
CAMERA_PROGRAMS = ['pavucontrol']

# Brightness adjustments depending on the sunset time.
BRIGHTNESS_MAX = 100
BRIGHTNESS_MIN = 5
BRIGHTNESS_MAX_WHEN_DARK_OUTSIDE = 50
BRIGHTNESS_MOVIE_MIN = 50

BRIGHTNESS_ADJUSTMENT_THRESHOLD_SUN_UP = 7
BRIGHTNESS_ADJUSTMENT_THRESHOLD_SUN_DOWN = 3

# Location information
LOCATION_LATITUDE = 55.7
LOCATION_LONGITUDE = 13.2
LOCATION_ELEVATION = 20

# How long to wait between checking if something has changed, in seconds
WAIT_TIME = 3
# How many seconds to wait after adjusting the brightness before adjusting again
WAIT_TIME_AFTER_ADJUSTMENT = 15
# How long to wait before starting the script. Can be specified by -i 0
INITIALIZE_TIME = 10

LOG_LOCATION = '/tmp/brightnessAdjuster-camera.log'
LOG_LEVEL = logging.DEBUG


# Setup logging
logging.basicConfig(format='%(asctime)s:%(levelname)s: %(message)s', filename=LOG_LOCATION, level=LOG_LEVEL, datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger().addHandler(logging.StreamHandler())

class SunsetChecker:
    def __init__(self):
        self._location = ephem.Observer()
        self._location.lat = str(LOCATION_LATITUDE)
        self._location.lon = str(LOCATION_LONGITUDE)
        self._location.elev = LOCATION_ELEVATION
        self._location.pressure=1080
        self._location.horizon='-6'
        self.currentDate = 'invalid'
        self._updateCurrentDate()
        self._updateSunsetTime()

    def update(self):
        self._updateCurrentDate()
        if not self._isSunsetTimeUpToDate():
            self._updateSunsetTime()

    def _updateCurrentDate(self):
        now = strftime("%Y-%m-%d", gmtime())
        if now != self.currentDate:
            logging.info('Current date: ' + str(now))
            self.currentDate = now
            self.midnight = datetime.utcnow()
            self.midnight.replace(hour=0, minute=0, second=0, microsecond=0)

    def _isSunsetTimeUpToDate(self):
        if self.sunsetDate == self.currentDate:
            return True
        else:
            return False

    def _updateSunsetTime(self):
        self.sunsetDate = self.currentDate
        self._location.date = self.sunsetDate + " 12:00:00"
        sunset = self._location.next_setting(ephem.Sun())
        self.sunsetTime = sunset.datetime()
        logging.info('Sunset time: ' + str(self.sunsetTime))

    # @return positive if there are minutes left, negative if the sun has set
    def getMinutesTillSunset(self):
        now = datetime.now()
        logging.debug('Now: ' + str(now))
        secondsSinceMidnightNow = (now - self.midnight).total_seconds()
        secondsSinceMidnightSunset = (self.sunsetTime - self.midnight).total_seconds()
        return (secondsSinceMidnightSunset - secondsSinceMidnightNow) / 60

    def isSunset(self):
        return self.getMinutesTillSunset() <= 0

##############################
# Checks ambient light in the room through a webcam
# self.realLux is the current brightness from the webcam.
# self.stableLux is the actual outgoing brightness. This is to filter out
# noise, i.e. brightness spikes.
##############################
class AmbientLightChecker:
    CAMERA_RES_X = 2
    CAMERA_RES_Y = 2
    LUX_STABLE_DIFF = 10

    def __init__(self):
        self.stableLux = -256
        self.realLux = -256

    def __exit__(self, exc_type, exc_value, traceback):
        if self.camera is not None and self.camera.isOpened():
            self.camera.release()

    def update(self):
        if self.cameraIsBeingUsed():
            return

        oldLux = self.realLux

        self.camera = cv2.VideoCapture(0)
        self.camera.set(5,15)
        self.camera.set(3,320)
        self.camera.set(4,240)
        ret, image = self.camera.read()

        if ret:
            self.grayImage = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            self.grayImage = cv2.resize(self.grayImage, (self.CAMERA_RES_X, self.CAMERA_RES_Y))
            self.realLux = self.calculateMax()
            logging.debug("Camera Brightness: " + str(self.realLux))
            self.camera.release()
            self.camera = None

            if abs(oldLux - self.realLux) <= self.LUX_STABLE_DIFF:
                self.stableLux = self.realLux
                logging.debug("Updated stable LUX: " + str(self.stableLux))

    def calculateMax(self):
        maxValue = 0
        for x in range(0, self.CAMERA_RES_X):
            for y in range(0, self.CAMERA_RES_Y):
                currentValue = self.grayImage[y][x]
                if currentValue > maxValue:
                    maxValue = currentValue
        return int(maxValue)

    def cameraIsBeingUsed(self):
        ps = check_output(['ps', 'x']).decode('utf-8')
        for program in CAMERA_PROGRAMS:
            matches = re.search(program, ps)
            if matches:
                print('Camera is being used by ' + program)
                return True
        return False

    def getLux(self):
        return self.stableLux

    def getNormalizedLux(self):
        return float(self.stableLux) / float(256)
        

class ProgramChecker:
    def __init__(self, programsDisable, fullscreenDisable):
        self.programsDisable = programsDisable
        self.fullscreenDisable = fullscreenDisable
        self.fullscreenWindowIds = []

    def _checkForFullscreen(self):
        if self.fullscreenDisable:
            # Check old windows if they should be removed (as they aren't in fullscreen anymore
            for windowId in list(self.fullscreenWindowIds):
                if not self._isWindowFullscreen(windowId):
                    self.fullscreenWindowIds.remove(windowId)

            windowIdOutput = check_output(['xprop', '-display', X_SCREEN, '-root', '_NET_ACTIVE_WINDOW']).decode('utf-8')
            windowId = windowIdOutput[40:-1]
            logging.debug("Window id: " + windowId)
            if self._isWindowFullscreen(windowId):
                if self.fullscreenWindowIds.count(windowId) == 0:
                    logging.info("Fullscreen window found!")
                    self.fullscreenWindowIds.append(windowId)


    def _isWindowFullscreen(self, windowId):
        if len(windowId) == 9:
            windowOutput = check_output(['xprop', '-display', X_SCREEN, '-id', windowId]).decode('utf-8')
            if windowOutput.find('_NET_WM_STATE_FULLSCREEN') != -1:
                return True
            else:
                return False

    def _isFullscreenActive(self):
        if len(self.fullscreenWindowIds) > 0:
            return True
        else:
            return False

    def shouldBeDisabled(self):
        for program in self.programsDisable:
            if (self._isProgramRunning(program)):
                return True

        # Check fullscreen
        self._checkForFullscreen()
        if self._isFullscreenActive():
            logging.debug("Fullscreen is active")
            return True

        return False

    def _isProgramRunning(self, searchFor):
        output = check_output(['ps', 'aux']).decode('utf-8')
        if output.find(searchFor) != -1:
            logging.debug("Found program " + searchFor)
            return True
        else:
            return False


class BrightnessAdjuster:
    def __init__(self):
        self.movieMode = False
        self.brightness = -100
        self.darkOutside = False
        self.brightnessMax = BRIGHTNESS_MAX

    def setDarkOutside(self, darkOutside):
        self.darkOutside = darkOutside;
        if darkOutside:
            logging.debug("It's dark outside...")
            self.brightnessMax = BRIGHTNESS_MAX_WHEN_DARK_OUTSIDE
        else:
            logging.debug("The sun is up :)")
            self.brightsessMax = BRIGHTNESS_MAX

    def setBrightness(self, lux):
        tempBrightness = int(lux * (self.brightnessMax - BRIGHTNESS_MIN))

        if self.movieMode:
            newBrightness = max(tempBrightness, BRIGHTNESS_MOVIE_MIN)
        else:
            newBrightness = tempBrightness

        diffBrightness = abs(self.brightness - newBrightness)
        if self.darkOutside:
            minDiff = BRIGHTNESS_ADJUSTMENT_THRESHOLD_SUN_DOWN
        else:
            minDiff = BRIGHTNESS_ADJUSTMENT_THRESHOLD_SUN_UP

        if diffBrightness >= minDiff:
            # Never decrease brightness in movie mode
            changeBrightness = False
            if not self.movieMode or newBrightness > self.brightness:
                self.brightness = newBrightness
                changeBrightness = True

            if changeBrightness:
                logging.info("Set brightness to " + str(self.brightness))
                for display in DISPLAYS:
                    Popen(['ddccontrol', '-r', '0x10', '-w', str(self.brightness), display])
                sleep(WAIT_TIME_AFTER_ADJUSTMENT)

    def enableMovieMode(self):
        logging.info("Movie mode enabled")
        self.movieMode = True

    def disableMovieMode(self):
        logging.info("Movie mode disabled")
        self.movieMode = False

    def isMovieMode(self):
        return self.movieMode


# -----------------------
# Program Logic
# -----------------------
def main():
    parser = argparse.ArgumentParser(description='Dynamic screen brightness.')
    parser.add_argument('-i', '--initialize-time', default=INITIALIZE_TIME, type=int)
    args = parser.parse_args()
    sleep(args.initialize_time)
    programChecker = ProgramChecker(PROGRAMS_DISABLED, FULLSCREEN_DISABLED)
    brightnessAdjuster = BrightnessAdjuster()
    ambientLightChecker = AmbientLightChecker()
    sunsetChecker = SunsetChecker()

    while True:
        try:
            ambientLightChecker.update()
            sunsetChecker.update()
            darkOutside = sunsetChecker.isSunset()
            lux = ambientLightChecker.getNormalizedLux()
            if programChecker.shouldBeDisabled() and not brightnessAdjuster.isMovieMode():
                brightnessAdjuster.enableMovieMode()
            elif not programChecker.shouldBeDisabled() and brightnessAdjuster.isMovieMode():
                brightnessAdjuster.disableMovieMode()
            brightnessAdjuster.setDarkOutside(darkOutside)
            if lux >= 0:
                brightnessAdjuster.setBrightness(lux)
        except CalledProcessError:
            logging.exception("Couldn't call a subprocess")
        sleep(WAIT_TIME)

try:
    main()
except:
    logging.exception("Main exception: ")
