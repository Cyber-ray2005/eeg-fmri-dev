"""
Example usage of the Supernumerary Finger Controller Library
Author: Pi Ko (pi.ko@nyu.edu)
"""
# Step 1 : Import the library
import finger_controller as fc
import time

# Step 2 : In the Experiment class init, calibrate the finger by setting to 0
fc.execute_finger(0) 
time.sleep(5)
# Step 3 : Call the line below anytime with any value between 0 (open) to 100 (full flex)
fc.execute_finger(100)  
time.sleep(5)