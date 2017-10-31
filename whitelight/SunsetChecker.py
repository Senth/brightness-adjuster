import ephem
import logging
from time import gmtime, strftime
from datetime import datetime
from config import LOCATION_ELEVATION, LOCATION_LATITUDE, LOCATION_LONGITUDE

logger = logging.getLogger(__name__)


class SunsetChecker:
    """Check if the sun has set"""
    def __init__(self):
        self._location = ephem.Observer()
        self._location.lat = str(LOCATION_LATITUDE)
        self._location.lon = str(LOCATION_LONGITUDE)
        self._location.elev = LOCATION_ELEVATION
        self._location.pressure = 1080
        self._location.horizon = '-6'
        self.current_date = 'invalid'
        self._update_current_date()
        self._update_sunset_time()

    def update(self):
        self._update_current_date()
        if not self._is_sunset_time_updated():
            self._update_sunset_time()

    def _update_current_date(self):
        now = strftime("%Y-%m-%d", gmtime())
        if now != self.current_date:
            logger.info('Current date: ' + str(now))
            self.current_date = now
            self.midnight = datetime.utcnow()
            self.midnight.replace(hour=0, minute=0, second=0, microsecond=0)

    def _is_sunset_time_updated(self):
        if self.sunsetDate == self.current_date:
            return True
        else:
            return False

    def _update_sunset_time(self):
        self.sunsetDate = self.current_date
        self._location.date = self.sunsetDate + " 12:00:00"
        sunset = self._location.next_setting(ephem.Sun())
        self.sunsetTime = sunset.datetime()
        logger.info('Sunset time: ' + str(self.sunsetTime))

    def get_minutes_since_sunset(self):
        """@return negative if there are minutes left, positive if the sun has set."""
        now = datetime.now()
        logger.debug('Now: ' + str(now))
        seconds_since_midnight_now = (now - self.midnight).total_seconds()
        seconds_since_midnight_sunset = (self.sunsetTime - self.midnight).total_seconds()
        return (seconds_since_midnight_sunset - seconds_since_midnight_now) / -60

    def is_sunset(self):
        return self.get_minutes_since_sunset() <= 0
