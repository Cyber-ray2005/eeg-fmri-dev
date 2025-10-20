"""
Minimal Working Example - Supernumerary Finger Controller v3.1
5 lines demonstrating all core functionality with 100% operations
Note: All commands auto-reset after 1 second (firmware-controlled)

Author: Pi Ko (pi.ko@nyu.edu)
"""

import finger_controller as fc, time
fc.initialize(reset_delay=2.5)                        # Calibration: auto-discover and connect to device  
fc.flex_to(100); time.sleep(4)                       # Flex to 100%, auto-resets after 1s (wait 4s total)
fc.unflex_from(100); time.sleep(4)                   # Unflex sequence, auto-resets after 1s (wait 4s total)  
fc.execute_finger(100); time.sleep(4)                # Full cycle: flex->unflex->reset at 100% (wait 4s)