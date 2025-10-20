"""
New Embodiment Exercise for Grasp-Release Training
Handles both EEG and non-EEG versions of the grasp embodiment exercise.
"""

from utils.pygame_display import PygameDisplay
from utils.logger import TextLogger
from utils.tcp_client import TCPClient
import pygame
import random
import time
import queue
import json
import threading
from typing import Optional


class EmbodimentExerciseGrasp:
    """
    New embodiment exercise that focuses on grasp-release cycles.
    Supports both EEG and non-EEG versions with ERD feedback.
    """
    
    def __init__(self, config, enable_logging=True, log_name_base=None, is_eeg_version=False, tcp_client=None, serial_comm=None):
        self.config = config
        self.enable_logging = enable_logging
        self.is_eeg_version = is_eeg_version
        self.tcp_client = tcp_client
        self.serial_comm = serial_comm
        
        # Initialize the logger only if logging is enabled
        if self.enable_logging:
            filename = f"{log_name_base}_grasp.txt" if log_name_base else "embodiment_grasp_log.txt"
            self.logger = TextLogger(
                log_dir="exercise_logs", 
                filename=filename,
                timestamp_format="%Y-%m-%d %H:%M:%S",
                add_timestamp_to_filename=(log_name_base is None)
            )
        else:
            self.logger = None
            print("Embodiment Grasp Exercise: Logging disabled (no files will be created)")
        
        # Initialize the display
        self.display = PygameDisplay(config)
        
        # EEG-specific setup
        if self.is_eeg_version:
            self.received_data_queue = queue.Queue()
            self.stop_listener_event = threading.Event()
            if self.tcp_client and self.tcp_client.connect():
                self.tcp_listener = threading.Thread(
                    target=self.tcp_client.tcp_listener_thread,
                    name="TCPListener",
                    args=(self.received_data_queue, self.stop_listener_event),
                    daemon=True
                )
                self.tcp_listener.start()
            else:
                print("Warning: TCP connection failed. Proceeding without ERD feedback.")
                self.tcp_client = None

    def run(self):
        """Main method to run the grasp embodiment exercise."""
        if self.logger:
            self.logger.log("Grasp Embodiment Exercise started.")
        
        if self.is_eeg_version:
            # Display initial instructions
            self.display.display_message_screen(
                "Grasp Embodiment Exercise\n\nYou will perform 5 grasp-release cycles.\n\n"
                "For each cycle:\n"
                "1. Get ready in near-grasp position\n"
                "2. Perform motor imagery when prompted\n"
                "3. Move the object after grasping\n"
                "4. Perform release imagery when prompted\n\n"
                "Press any key to begin.",
                wait_for_key=True,
                font=self.display.FONT_LARGE
            )
        else:
            # Display initial instructions
            self.display.display_message_screen(
                "Grasp Embodiment Exercise\n\nYou will perform 5 grasp-release cycles.\n\n"
                "For each cycle:\n"
                "1. Get ready in near-grasp position\n"
                "2. Grab and Move the object after grasping action is done\n"
                "4. Perform release when prompted\n\n"
                "Press any key to begin.",
                wait_for_key=True,
                font=self.display.FONT_LARGE
            )
        
        # Run 5 grasp-release cycles
        successful_cycles = 0
        for cycle_num in range(1, 6):
            if self.logger:
                self.logger.log(f"Starting cycle {cycle_num}/5")
            
            # Run single grasp-release cycle
            cycle_success = self.run_grasp_release_cycle(cycle_num)
            if cycle_success:
                successful_cycles += 1
            
            # Show progress
            self.show_progress(cycle_num, 5, successful_cycles)
        
        # Show final results
        self.display.display_message_screen(
            f"Exercise Complete!\n\nSuccessful cycles: {successful_cycles}/5\n\n"
            "Press any key to continue to the main experiment.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
        if self.logger:
            self.logger.log(f"Grasp Embodiment Exercise finished. Successful cycles: {successful_cycles}/5")
        
        # Cleanup TCP connection if EEG version
        if self.is_eeg_version and self.tcp_client:
            self.stop_listener_event.set()
            if hasattr(self, 'tcp_listener'):
                self.tcp_listener.join(timeout=1.0)

    def run_grasp_release_cycle(self, cycle_num):
        """Run a single grasp-release cycle."""
        cycle_success = True
        
        # Phase 1: Grasp
        grasp_success = self.run_grasp_phase(cycle_num)
        if not grasp_success:
            cycle_success = False
        
        # Phase 2: Release
        if grasp_success:
            release_success = self.run_release_phase(cycle_num)
            if not release_success:
                cycle_success = False
        
        # TODO - reset the finger
        
        return cycle_success

    def run_grasp_phase(self, cycle_num):
        """Run the grasp phase of the cycle."""
        if self.logger:
            self.logger.log(f"Cycle {cycle_num}: Starting grasp phase")
        
        # Step 1: Ready position
        self.display.display_message_screen(
            f"Cycle {cycle_num}/5 - Grasp Phase\n\n"
            "Get ready in near-grasp position.\n\n"
            "Press any key when ready.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
        if self.is_eeg_version:
            # EEG version: Show fixation, stimulus, calculate ERD
            return self.run_grasp_phase_eeg(cycle_num)
        else:
            # Non-EEG version: Direct finger control
            return self.run_grasp_phase_non_eeg(cycle_num)

    def run_grasp_phase_eeg(self, cycle_num):
        """EEG version of grasp phase with ERD calculation."""
        # Show fixation (blank image)
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        blank_image_surface = self.display.scaled_images["blank"]
        self.display.display_image_stimulus(
            blank_image_surface, 
            1000,  # 1 second fixation
            (0, 0, blank_image_surface.get_width(), blank_image_surface.get_height())
        )
        
        # Show sixth finger stimulus for 3 seconds
        # Send only START trigger for grasp using config
        self.serial_comm.send_trigger(self.config.TRIGGER_GRASP_START)
        sixth_finger_image = self.display.scaled_images["sixth"]
        self.display.display_image_stimulus(
            sixth_finger_image,
            3000,  # 3 seconds
            (0, 0, sixth_finger_image.get_width(), sixth_finger_image.get_height())
        )
        
        # Calculate ERD
        erd_percent, erd_db = self.calculate_erd()
        
        if erd_percent is not None and erd_percent < 0:
            # Success: ERD is negative (desynchronization)
            if self.logger:
                self.logger.log(f"Cycle {cycle_num}: Grasp ERD% = {erd_percent:.2f}% | ERD dB = {erd_db if erd_db is not None else 'NA'} (SUCCESS)")
            
            # TODO: Flex robotic finger
            # fc.execute_finger(100)
            print(f"TODO: Flex robotic finger for grasp (ERD%: {erd_percent:.2f}%, dB: {erd_db if erd_db is not None else 'NA'})")

            time.sleep(1.2) # Give time for the finger to flex
            
            self.display.display_message_screen(
                "Grasp successful!\n\nMove the object now.\n\n"
                "Press any key when ready to release.",
                wait_for_key=True,
                font=self.display.FONT_LARGE
            )
            return True
        else:
            # Failure: ERD is positive or calculation failed
            if self.logger:
                self.logger.log(f"Cycle {cycle_num}: Grasp ERD% = {erd_percent if erd_percent is not None else 'NA'} (FAILED)")
            
            self.display.display_message_screen(
                f"Grasp attempt Unsuccessful (ERD%: {erd_percent if erd_percent is not None else 'NA'})\n\n"
                "Moving to next cycle...",
                duration_ms=3000,
                font=self.display.FONT_LARGE
            )
            return False

    def run_grasp_phase_non_eeg(self, cycle_num):
        """Non-EEG version of grasp phase with direct control."""
        if self.logger:
            self.logger.log(f"Cycle {cycle_num}: Executing grasp (non-EEG)")
        
        # TODO: Flex robotic finger
        # fc.execute_finger(100)
        print(f"TODO: Flex robotic finger for grasp (Cycle {cycle_num})")
        
        # time.sleep(1.2) # Give time for the finger to flex

        self.display.display_message_screen(
            "Grasp executed!\n\nMove the object now.\n\n"
            "Press any key when ready to release.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        return True

    def run_release_phase(self, cycle_num):
        """Run the release phase of the cycle."""
        if self.logger:
            self.logger.log(f"Cycle {cycle_num}: Starting release phase")
        
        if self.is_eeg_version:
            # EEG version: Show fixation, stimulus, calculate ERD
            return self.run_release_phase_eeg(cycle_num)
        else:
            # Non-EEG version: Direct finger control
            return self.run_release_phase_non_eeg(cycle_num)

    def run_release_phase_eeg(self, cycle_num):
        """EEG version of release phase with ERD calculation."""
        # Show fixation (blank image)
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        blank_image_surface = self.display.scaled_images["blank"]
        self.display.display_image_stimulus(
            blank_image_surface, 
            1000,  # 1 second fixation
            (0, 0, blank_image_surface.get_width(), blank_image_surface.get_height())
        )
        
        # Show sixth finger stimulus for 3 seconds
        # Send only START trigger for release using config
        self.serial_comm.send_trigger(self.config.TRIGGER_RELEASE_START)
        sixth_finger_image = self.display.scaled_images["sixth"]
        self.display.display_image_stimulus(
            sixth_finger_image,
            3000,  # 3 seconds
            (0, 0, sixth_finger_image.get_width(), sixth_finger_image.get_height())
        )
        
        # Calculate ERD
        erd_percent, erd_db = self.calculate_erd()
        
        if erd_percent is not None and erd_percent < 0:
            # Success: ERD is negative (desynchronization)
            if self.logger:
                self.logger.log(f"Cycle {cycle_num}: Release ERD% = {erd_percent:.2f}% | ERD dB = {erd_db if erd_db is not None else 'NA'} (SUCCESS)")
            
            # TODO: Extend robotic finger
            # fc.execute_finger(0)
            print(f"TODO: Extend robotic finger for release (ERD%: {erd_percent:.2f}%, dB: {erd_db if erd_db is not None else 'NA'})")
            return True
        else:
            # Failure: ERD is positive or calculation failed
            if self.logger:
                self.logger.log(f"Cycle {cycle_num}: Release ERD% = {erd_percent if erd_percent is not None else 'NA'} (FAILED)")
            
            # TODO: Reset finger on failure
            # fc.execute_finger(0)
            print(f"TODO: Reset finger on release failure (ERD%: {erd_percent if erd_percent is not None else 'NA'})")
            return False

    def run_release_phase_non_eeg(self, cycle_num):
        """Non-EEG version of release phase with direct control."""
        if self.logger:
            self.logger.log(f"Cycle {cycle_num}: Executing release (non-EEG)")
        
        # TODO: Extend robotic finger
        # fc.execute_finger(0)
        print(f"TODO: Extend robotic finger for release (Cycle {cycle_num})")
        # Sync timings so we can extend or sleep if extension sleep doesn't affect flow
        return True

    def calculate_erd(self):
        """Return tuple (erd_percent, erd_db) from TCP feedback; (None, None) if unavailable."""
        if not self.is_eeg_version or not self.tcp_client:
            return (None, None)
        
        try:
            raw_data = self.received_data_queue.get_nowait()
            feedback = json.loads(raw_data) if raw_data else {}
            erd_value_percent = feedback.get("erd_percent", None)
            erd_value_db = feedback.get("erd_db", None)
            erd_p = float(erd_value_percent) if erd_value_percent is not None else 0.0
            erd_db = float(erd_value_db) if erd_value_db is not None else 0.0
            return (erd_p, erd_db)
        except queue.Empty:
            return (None, None)
        except (json.JSONDecodeError, ValueError) as e:
            if self.logger:
                self.logger.log(f"ERD calculation failed: {e}")
            return (None, None)

    def show_progress(self, current, total, successful):
        """Show progress after each cycle."""
        self.display.display_message_screen(
            f"Exercise {current}/{total} completed\n\n"
            f"Successful cycles: {successful}/{current}\n\n"
            "Press any key to continue...",
            wait_for_key=True,
            font=self.display.FONT_MEDIUM
        )
