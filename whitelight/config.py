# Location information
LOCATION_LATITUDE = 55.7
LOCATION_LONGITUDE = 13.2
LOCATION_ELEVATION = 20 # meters over the sea

# Redshift temperature settings (in Kelvin)
REDSHIFT_TEMPERATURE_DAY = 6500
REDSHIFT_TEMPERATURE_NIGHT = 2800
# How many minutes it takes to shift to full night color (from sunset)
REDSHIFT_TRANSITION_TIME = 120

# Displays and X
DISPLAYS = ['3', '2', '1']
X_SCREEN = ':0.0'
# Manual brightness of your displays, hotkeys will start at META+F1
# Set a single value if you want the same brightness on all screens
# Or a list (same size as DISPLAY) for individual brightness on the screens
MANUAL_BRIGHTNESS = [
        0,
        [0, 15, 0],
        15,
        25,
        35,
        50,
        75,
    ]