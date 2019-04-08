#!/usr/bin/env python3
"""
Candle flame simulator.
Based on code from
https://github.com/EternityForest/CandleFlickerSimulator/blob/master/flicker2.X/main.c
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import random

def Flicker(WIND_VARIABILITY = 0.02,
            WIND_GUST = 0.85,
            FLAME_AGILITY = 0.008,
            FLAME_GROWTH = 0.004,
            WIND_CALMNESS = 4,
            WIND_BASELINE = 30):
    "Quasi physics based flame flicker generator"

    flame = 0
    flameprime = 0
    wind = 0
    sensor_wind = None
    fuel = 1.0

    while True:
        if sensor_wind is None:
            if random.random() < WIND_VARIABILITY:
                # Make a gust of wind less likely with two random tests
                if random.random() > WIND_GUST:
                    wind = random.random()
            # The wind constantly settles towards its baseline value
            if wind > WIND_BASELINE:
                wind -= 1
        else:
            wind = sensor_wind

        # The flame constantly gets brighter until the wind knocks it down
        if flame < 1.0:
            flame += FLAME_GROWTH * fuel

        # Depending on the wind strength and the calmnes modifer we calcuate the odds
        # of the wind knocking down the flame by setting it to random values
        if random.random() < (wind / WIND_CALMNESS):
            flame = random.random()

        # Output is a slow follower with overshoot on flame to simulate inertia
        if flame > flameprime:
            if flameprime < fuel - FLAME_AGILITY:
                flameprime += FLAME_AGILITY
        else:
            if flameprime > FLAME_AGILITY:
                flameprime -= FLAME_AGILITY

        feedback = yield flameprime
        if feedback:
            sensor_wind = feedback.get('wind')
            fuel = feedback.get('fuel', fuel)

if __name__ == '__main__':
    import sys
    main_flicker = Flicker()
    for val in main_flicker:
        c = round(val * 80)
        sys.stdout.write("=" * c)
        sys.stdout.write(' ' * (80-c))
        sys.stdout.write('\r')
