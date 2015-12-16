#!/usr/bin/python
import ephem
import logging
from datetime import datetime
from time import gmtime, strftime, sleep
from subprocess import call, check_output


# Adjust brightness when any of the programs below are active or always enabled is true
ALWAYS_ENABLED = True
PROGRAMS_ENABLED = ['eclipse', 'android-studio']

# Always disabled adjustment and set it to default when any of these programs are running
PROGRAMS_DISABLED = ['mplayer', 'smplayer', 'vlc']
# Always disabled adjustment and set it to default when anything is in fullscreen
FULLSCREEN_DISABLED = True

# Displays to change brightness of
DISPLAYS = ['DFP1', 'DFP2', 'DFP5']

# Brightness adjustments depending on the sunset time.
# First tuplet is minutes to sunset (can be negative)
# Second tuplet is brightness in the range [0.0,1.0]
ADJUST_FROM = (60, 1.0)
ADJUST_TO = (-60, 0.75)

# Location information
LOCATION_LATITUDE = 55.7
LOCATION_LONGITUDE = 13.2
LOCATION_ELEVATION = 20


# --- Other non-essential settings ---

# How long to wait between checking if something has changed
WAIT_TIME = 1

LOG_LOCATION = '/tmp/brightnessAdjuster.log'
LOG_LEVEL = logging.INFO


# Setup logging
logging.basicConfig(format='%(asctime)s:%(levelname)s: %(message)s', filename=LOG_LOCATION, level=LOG_LEVEL, datefmt='%Y-%m-%d %H:%M:%S')


class SunsetChecker:
    def __init__(self):
        self._location = ephem.Observer()
        self._location.lat = str(LOCATION_LATITUDE)
        self._location.lon = str(LOCATION_LONGITUDE)
        self._location.elev = LOCATION_ELEVATION
        self._location.pressure=1080
        self._location.horizon='-6'
        self.currentDate = 'invalid'
        self.updateCurrentDate()
        self.updateSunsetTime()

    def update(self):
        self.updateCurrentDate()
        if not self.isSunsetTimeUpToDate():
            self.updateSunset()

    def updateCurrentDate(self):
        now = strftime("%Y-%m-%d", gmtime())
        if now != self.currentDate:
            self.currentDate = now
            self.midnight = datetime.utcnow()
            self.midnight.replace(hour=0, minute=0, second=0, microsecond=0)

    def isSunsetTimeUpToDate(self):
        if self.sunsetDate == self.currentDate:
            return True
        else:
            return False

    def updateSunsetTime(self):
        self.sunsetDate = self.currentDate
        self._location.date = self.sunsetDate + " 12:00:00"
        sunset = self._location.next_setting(ephem.Sun())
        self.sunsetTime = sunset.datetime()

    # @return positive if there are minutes left, negative if the sun has set
    def getMinutesTillSunset(self):
        now = datetime.utcnow()
        secondsSinceMidnightNow = (now - self.midnight).total_seconds()
        secondsSinceMidnightSunset = (self.sunsetTime - self.midnight).total_seconds()
        return (secondsSinceMidnightSunset - secondsSinceMidnightNow) / 60


class ProgramChecker:
    DISPLAY=':0.0'

    def __init__(self, programsActive, programsDisable, fullscreenDisable):
        self.programsActive = programsActive
        self.programsDisable = programsDisable
        self.fullscreenDisable = fullscreenDisable
        self.fullscreenWindowIds = []

    def isEnableProgramRunning(self):
        if ALWAYS_ENABLED:
            return True

        for program in self.programsActive:
            if (self.isProgramRunning(program)):
                return True
        return False

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

    def isDisableProgramRunnnig(self):
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
    BRIGHTNESS_ADJUSTMENT_PER_10MS = 0.01
    BRIGHTNESS_SLEEP_TIME = 0.01

    def __init__(self, adjustFrom, adjustTo):
        self.adjustFrom = adjustFrom
        self.adjustTo = adjustTo
        adjustTotalTime = adjustFrom[0] - adjustTo[0]
        adjustTotalDiff = adjustFrom[1] - adjustTo[1]
        self.adjustPerMinute = float(adjustTotalDiff) / float(adjustTotalTime)
        self.currentBrightness = adjustFrom[1] - self.BRIGHTNESS_ADJUSTMENT_PER_10MS

    def adjustBrightness(self, minutesToSunset):
        logging.debug("Minutes to sunset: " + str(minutesToSunset))
        if (self.isAdjusting(minutesToSunset)):
            clampedTime = max(minutesToSunset, self.adjustTo[0])
            diffTime = self.adjustFrom[0] - clampedTime
            brightness = self.adjustFrom[1] - (float(diffTime) * self.adjustPerMinute)
            self.setBrightnessFade(brightness)

    def isAdjusting(self, minutesToSunset):
        return self.adjustFrom[0] > minutesToSunset

    def setBrightnessFade(self, brightness):
        adjustingBrightness = self.currentBrightness
        self.currentBrightness = brightness

        # Increase brightness
        if (adjustingBrightness < brightness):
            while adjustingBrightness < brightness:
                self.setBrightness(adjustingBrightness)
                adjustingBrightness += self.BRIGHTNESS_ADJUSTMENT_PER_10MS
                sleep(self.BRIGHTNESS_SLEEP_TIME)

        # Decrease brightness
        else:
            while adjustingBrightness > brightness:
                self.setBrightness(adjustingBrightness)
                adjustingBrightness -= self.BRIGHTNESS_ADJUSTMENT_PER_10MS
                sleep(self.BRIGHTNESS_SLEEP_TIME)

        self.setBrightness(brightness)
        logging.info("Brightness: " + str(brightness))

    def setBrightness(self, brightness):
        self.currentBrightness = brightness
        for display in DISPLAYS:
            call(['xrandr', '--output', display, '--brightness', str(brightness)])

    def disable(self):
        logging.debug("Disable adjuster")
        self.setBrightnessFade(self.adjustFrom[1])

    def isActive(self):
        if self.adjustFrom[1] == self.currentBrightness:
            return False
        else:
            return True
            

# -----------------------
# Program Logic
# -----------------------
programChecker = ProgramChecker(PROGRAMS_ENABLED, PROGRAMS_DISABLED, FULLSCREEN_DISABLED)
brightnessAdjuster = BrightnessAdjuster(ADJUST_FROM, ADJUST_TO)
sunsetChecker = SunsetChecker()


while True:
    # Check if we should disable the brightness correction
    if brightnessAdjuster.isActive():
        logging.debug("Brightness has been adjusted")
        # Disabled running
        if programChecker.isDisableProgramRunnnig():
            brightnessAdjuster.disable()
        # No enabled running, disable
        elif not programChecker.isEnableProgramRunning():
            brightnessAdjuster.disable()
        # Enabled program running, adjust brightness
        else:
            sunsetChecker.update()
            brightnessAdjuster.adjustBrightness(sunsetChecker.getMinutesTillSunset())

    # Check if we should enable brightness correction
    else:
        logging.debug("Brightness at default")
        if programChecker.isEnableProgramRunning() and not programChecker.isDisableProgramRunnnig():
            sunsetChecker.update()
            brightnessAdjuster.adjustBrightness(sunsetChecker.getMinutesTillSunset())
    
    sleep(WAIT_TIME)
