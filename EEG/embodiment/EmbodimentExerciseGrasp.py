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
import finger_controller as fc


class EmbodimentExerciseGrasp:
    """
    New embodiment exercise that focuses on grasp-release cycles.
    Supports both EEG and non-EEG versions with ERD feedback.
    """
    
    def __init__(self, config, enable_logging=True, log_name_base=None, is_eeg_version=False, tcp_client=None, serial_comm=None, received_data_queue=None, stop_listener_event=None):
        self.config = config
        self.enable_logging = enable_logging
        self.is_eeg_version = is_eeg_version
        self.tcp_client = tcp_client
        self.serial_comm = serial_comm

        self.received_data_queue = received_data_queue
        self.stop_listener_event = stop_listener_event
        
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
        try:
            self.display.load_stimulus_images()
        except:
            raise
        
        # EEG-specific setup
        if self.is_eeg_version:
            if not self.tcp_client:
                print("Warning: No TCP Client provided. Proceeding without ERD feedback")
                self.is_eeg_version = False
            elif not self.received_data_queue:
                print("Warning: No TCP Data Queue provided. Proceeding without ERD feedback")
                self.tcp_client = None
                self.is_eeg_version = False

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
        # Show imagery preparation notice
        self.display.display_message_screen(
            "Get ready to perform motor imagery\nwhen the sixth finger stimulus appears.\n\n"
            "Press any key when ready.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
        # Show fixation (blank image) for 2.5 seconds
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        blank_image_surface = self.display.scaled_images["blank"]
        self.display.display_image_stimulus(
            blank_image_surface, 
            2500,  # 2.5 seconds fixation
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
        
        # Check for test mode override
        if hasattr(self.config, 'TEST_MODE_EMBODIMENT') and self.config.TEST_MODE_EMBODIMENT:
            success = True
            erd_db_display = erd_db if erd_db is not None else 0.0
        else:
            success = erd_percent is not None and erd_percent < 0
            erd_db_display = erd_db if erd_db is not None else 0.0
        
        if success:
            # Success: ERD is negative (desynchronization) or test mode
            if self.logger:
                self.logger.log(f"Cycle {cycle_num}: Grasp ERD% = {erd_percent:.2f}% | ERD dB = {erd_db_display:.2f} (SUCCESS)")
            
            # Flex robotic finger
            fc.flex_test(100)
            
            # Show success display with ERD dB value
            self.display.display_message_screen(
                f"#green:Grasp Successful!#\n\nERD dB: {erd_db_display:.2f}\n\n"
                "Move the object now.\n\n"
                "Press any key when ready to release.",
                wait_for_key=True,
                font=self.display.FONT_LARGE
            )
            return True
        else:
            # Failure: ERD is positive or calculation failed
            if self.logger:
                self.logger.log(f"Cycle {cycle_num}: Grasp ERD% = {erd_percent if erd_percent is not None else 'NA'} | ERD dB = {erd_db_display:.2f} (FAILED)")
            
            # Show failure display with ERD dB value
            self.display.display_message_screen(
                f"#red:Grasp Unsuccessful#\n\nERD dB: {erd_db_display:.2f}\n\n"
                "Moving to next cycle...",
                duration_ms=2000,
                font=self.display.FONT_LARGE
            )
            return False

    def run_grasp_phase_non_eeg(self, cycle_num):
        """Non-EEG version of grasp phase with direct control."""
        if self.logger:
            self.logger.log(f"Cycle {cycle_num}: Executing grasp (non-EEG)")
        
        # Show imagery preparation notice
        self.display.display_message_screen(
            "Get ready to perform grasp action.\n\n"
            "Press any key when ready.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
        # Execute grasp
        fc.flex_test(100)
        
        # Show success display
        self.display.display_message_screen(
            "#green:Grasp Executed!#\n\n"
            "Move the object now.\n\n"
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
        # Show imagery preparation notice
        self.display.display_message_screen(
            "Get ready to perform motor imagery\nwhen the sixth finger stimulus appears.\n\n"
            "Press any key when ready.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
        # Show fixation (blank image) for 2.5 seconds
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        blank_image_surface = self.display.scaled_images["blank"]
        self.display.display_image_stimulus(
            blank_image_surface, 
            2500,  # 2.5 seconds fixation
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
        
        # Check for test mode override
        if hasattr(self.config, 'TEST_MODE_EMBODIMENT') and self.config.TEST_MODE_EMBODIMENT:
            success = True
            erd_db_display = erd_db if erd_db is not None else 0.0
        else:
            success = erd_percent is not None and erd_percent < 0
            erd_db_display = erd_db if erd_db is not None else 0.0
        
        if success:
            # Success: ERD is negative (desynchronization) or test mode
            if self.logger:
                self.logger.log(f"Cycle {cycle_num}: Release ERD% = {erd_percent:.2f}% | ERD dB = {erd_db_display:.2f} (SUCCESS)")
            
            # Extend robotic finger
            fc.unflex_test(100)
            
            # Show success display with ERD dB value
            self.display.display_message_screen(
                f"#green:Release Successful!#\n\nERD dB: {erd_db_display:.2f}\n\n"
                "Cycle completed!",
                duration_ms=2000,
                font=self.display.FONT_LARGE
            )
            return True
        else:
            # Failure: ERD is positive or calculation failed
            if self.logger:
                self.logger.log(f"Cycle {cycle_num}: Release ERD% = {erd_percent if erd_percent is not None else 'NA'} | ERD dB = {erd_db_display:.2f} (FAILED)")
            
            # Show failure display with ERD dB value
            self.display.display_message_screen(
                f"#red:Release Unsuccessful#\n\nERD dB: {erd_db_display:.2f}\n\n"
                "Moving to next cycle...",
                duration_ms=2000,
                font=self.display.FONT_LARGE
            )
            # Reset finger on failure
            fc.unflex_test(100)
            return False

    def run_release_phase_non_eeg(self, cycle_num):
        """Non-EEG version of release phase with direct control."""
        if self.logger:
            self.logger.log(f"Cycle {cycle_num}: Executing release (non-EEG)")
        
        # Show imagery preparation notice
        self.display.display_message_screen(
            "Get ready to perform release action.\n\n"
            "Press any key when ready.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
        # Execute release
        fc.unflex_test(100)
        
        # Show success display
        self.display.display_message_screen(
            "#green:Release Executed!#\n\n"
            "Cycle completed!",
            duration_ms=2000,
            font=self.display.FONT_LARGE
        )
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
