import logging
from time import sleep
from config import REDSHIFT_TEMPERATURE_DAY, REDSHIFT_TEMPERATURE_NIGHT, REDSHIFT_TRANSITION_TIME
from subprocess import Popen

logging.getLogger(__name__)


class RedshiftAdjuster:
    # How fast the color is changed in seconds.
    ADJUST_SPEED = 7000
    ADJUST_INTERVALS = 10 # ms
    ADJUST_INTERVAL_SLEEP = float(ADJUST_INTERVALS) / 1000
    ADJUST_PER_INTERVAL = ADJUST_SPEED * ADJUST_INTERVAL_SLEEP
    DAY_NIGHT_DIFF_TEMPERATURE = REDSHIFT_TEMPERATURE_DAY - REDSHIFT_TEMPERATURE_NIGHT

    def __init__(self):
        self.enabled = True
        self.redshift_temperature = REDSHIFT_TEMPERATURE_DAY - 500
        self.screen_temperature = REDSHIFT_TEMPERATURE_DAY - 500

    def update_redshift(self, time_since_sunset):
        if self.enabled:
            logging.info("Minutes since sunset: " + str(time_since_sunset))
            # Sun is still up
            if time_since_sunset < 0:
                logging.info("Day redshift")
                new_temperature = REDSHIFT_TEMPERATURE_DAY
            # Sun has set, transitioning
            elif time_since_sunset < REDSHIFT_TRANSITION_TIME:
                logging.info("Transitioning to night shift")
                diff_fraction = (REDSHIFT_TRANSITION_TIME - time_since_sunset) / REDSHIFT_TRANSITION_TIME
                diff_temperature = diff_fraction * RedshiftAdjuster.DAY_NIGHT_DIFF_TEMPERATURE
                new_temperature = REDSHIFT_TEMPERATURE_NIGHT + diff_temperature
            # Done transitioning
            else:
                logging.info("Night redshift")
                new_temperature = REDSHIFT_TEMPERATURE_NIGHT

            self.redshift_temperature = new_temperature
            self._set_redshift_slowly(new_temperature)

    def _set_redshift_slowly(self, new_temperature):
        logging.info('Redshift slowly: ' + str(new_temperature))
        if new_temperature != self.screen_temperature:
            diff_temperature = new_temperature - self.screen_temperature
            intervals = int(abs(diff_temperature) / RedshiftAdjuster.ADJUST_PER_INTERVAL)
            if diff_temperature < 0:
                interval_adjustment = -RedshiftAdjuster.ADJUST_PER_INTERVAL
            else:
                interval_adjustment = RedshiftAdjuster.ADJUST_PER_INTERVAL

            for i in range(1, intervals+1):
                self._set_redshift(self.screen_temperature + interval_adjustment)
                sleep(RedshiftAdjuster.ADJUST_INTERVAL_SLEEP)

            self._set_redshift(new_temperature)

    def _set_redshift(self, temperature):
        self.screen_temperature = temperature
        Popen(['redshift', '-O', str(temperature)])

    def disable(self):
        self.enabled = False
        self._set_redshift_slowly(REDSHIFT_TEMPERATURE_DAY)

    def enable(self):
        self.enabled = True
        self._set_redshift_slowly(self.redshift_temperature)