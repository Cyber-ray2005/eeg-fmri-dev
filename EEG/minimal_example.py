"""
Example usage of the Supernumerary Finger Controller Library
Author: Pi Ko (pi.ko@nyu.edu)
"""
# Step 1: Import the library
import finger_controller as fc
import time

# Step 2: In the Experiment class init, calibrate the finger by setting to 0
fc.execute_finger(0)
time.sleep(2)


# Original function - full cycle (flex->unflex->reset)
fc.execute_finger(100)

time.sleep(2)

fc.flex_test(100)


time.sleep(2)

fc.unflex_test(100)


time.sleep(2)