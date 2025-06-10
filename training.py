import threading # --- NEW: Import threading for background data reception ---
import queue # --- NEW: Import queue for thread-safe data passing ---

import pygame
import random
import time
import sys
import os
import queue
import json

from trial_generator import TrialGenerator
from pygame_display import PygameDisplay
from logger import TrialDataLogger
from serial_communication import SerialCommunication
from tcp_client import TCPClient # --- NEW: Import the TCP client class ---

# --- Experiment Parameters ---
class ExperimentConfig:
    def __init__(self):
        # Screen dimensions
        self.SCREEN_WIDTH = 1000
        self.SCREEN_HEIGHT = 700
        self.FULLSCREEN_MODE = False

        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (150, 150, 150)
        self.RED = (255, 0, 0)
        self.CIRCLE_COLOR = (200, 200, 200)

        # Durations (in milliseconds)
        self.INTRO_WAIT_KEY_PRESS = True
        self.INTRO_DURATION_MS = 5000
        self.INITIAL_CALIBRATION_DURATION_MS = 3000
        self.FIXATION_IN_TRIAL_DURATION_MS = 3000
        self.IMAGE_DISPLAY_DURATION_MS = 2000
        self.ERD_FEEDBACK_DURATION_MS = 2000
        self.SHORT_BREAK_DURATION_MS = 1500

        # Trial structure
        self.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK = 3
        self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK = 3
        self.NUM_BLANK_TRIALS_PER_BLOCK = 3
        self.NUM_NORMAL_FINGERS = 3
        self.NUM_EACH_NORMAL_FINGER_PER_BLOCK = self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK // self.NUM_NORMAL_FINGERS
        self.TRIALS_PER_BLOCK = (self.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK +
                                 self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK +
                                 self.NUM_BLANK_TRIALS_PER_BLOCK)
        self.NUM_BLOCKS = 3
        self.NUM_MOTOR_EXECUTION_TRIALS_PER_BLOCK = 6  # Placeholder for future use

        # Streak control parameters
        self.MAX_CONSECUTIVE_CATEGORY_STREAK = 1

        # Stimulus Paths and Names
        self.IMAGE_FOLDER = "images"
        self.SIXTH_FINGER_IMAGE_NAME = "Hand_SixthFinger_Highlighted.png"
        self.NORMAL_FINGER_IMAGE_MAP = {
            "thumb": "Hand_Thumb_Highlighted.png",
            "index": "Hand_Index_Highlighted.png",
            "middle": "Hand_Middle_Highlighted.png",
            "ring": "Hand_Ring_Highlighted.png",
            "pinky": "Hand_Pinky_Highlighted.png"
        }
        self.NORMAL_FINGER_TYPES = list(self.NORMAL_FINGER_IMAGE_MAP.keys())
        self.BLANK_CONDITION_NAME = "blank"

        # Condition categories for streak checking
        self.CATEGORY_SIXTH = "sixth_finger_cat"
        self.CATEGORY_NORMAL = "normal_finger_cat"
        self.CATEGORY_BLANK = "blank_cat"

        # Serial Port Configuration and Triggers
        self.SERIAL_PORT = 'COM15'
        self.BAUD_RATE = 9600

        # Define trigger values (bytes)
        self.TRIGGER_EXPERIMENT_START = 100
        self.TRIGGER_EXPERIMENT_END = 101
        self.TRIGGER_BLOCK_START = 11
        self.TRIGGER_BLOCK_END = 12
        self.TRIGGER_FIXATION_ONSET = 10
        self.TRIGGER_SIXTH_FINGER_ONSET = 6
        self.TRIGGER_THUMB_ONSET = 1
        self.TRIGGER_INDEX_ONSET = 2
        self.TRIGGER_MIDDLE_ONSET = 3
        self.TRIGGER_RING_ONSET = 4
        self.TRIGGER_PINKY_ONSET = 5
        self.TRIGGER_CONTROL_STIMULUS_ONSET = 7
        self.TRIGGER_SHORT_BREAK_ONSET = 20

        # Mapping from trial condition names to stimulus trigger codes
        self.STIMULUS_TRIGGER_MAP = {
            "sixth": self.TRIGGER_SIXTH_FINGER_ONSET,
            "thumb": self.TRIGGER_THUMB_ONSET,
            "index": self.TRIGGER_INDEX_ONSET,
            "middle": self.TRIGGER_MIDDLE_ONSET,
            "ring": self.TRIGGER_RING_ONSET,
            "pinky": self.TRIGGER_PINKY_ONSET,
            self.BLANK_CONDITION_NAME: self.TRIGGER_CONTROL_STIMULUS_ONSET
        }
        
        self.TCP_HOST =  '127.0.0.1'
        self.TCP_PORT = 50000  # The port used by the server
        


class Experiment:
    def __init__(self):
        self.config = ExperimentConfig()
        self.display = PygameDisplay(self.config)
        self.serial_comm = SerialCommunication(self.config.SERIAL_PORT, self.config.BAUD_RATE)
        self.trial_generator = TrialGenerator(self.config)
        self.data_logger = TrialDataLogger({
            "data_folder": "data",
            "filename_template": "{participant_id}_session_log_{timestamp}.csv",
            "fieldnames": ["participant_id", "block", "trial_num", "condition", "response_time", "timestamp", "server_feedback"]
        })
        self.participant_id = "P" + str(random.randint(100, 999))
        self.er_data_queue = queue.Queue() # For potential future ER data reception
        self.tcp_client = TCPClient(self.config.TCP_HOST, self.config.TCP_PORT)
        self.erd_history = [] # Placeholder for ERD history
        self.received_data_queue = queue.Queue() # Queue to pass data from thread to main loop
        self.stop_listener_event = threading.Event() # Event to signal the listener thread to stop

    def _close_all_connections(self):
        self.serial_comm.close()
        if self.tcp_client: # If you implement a TCP client, uncomment this
            self.tcp_client.close(self.stop_listener_event)

    def run_trial(self, trial_number_global, trial_condition):
        print(f"Global Trial: {trial_number_global}, Condition: {trial_condition} "
              f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")

        # Display fixation cross
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET) # Trigger for fixation cross
        self.display.display_fixation_cross(self.config.FIXATION_IN_TRIAL_DURATION_MS)

        stimulus_trigger_code = self.config.STIMULUS_TRIGGER_MAP.get(trial_condition)

        if trial_condition == self.config.BLANK_CONDITION_NAME:
            self.display.display_control_stimulus(self.config.IMAGE_DISPLAY_DURATION_MS)
            self.serial_comm.send_trigger(stimulus_trigger_code)
        elif trial_condition in self.display.scaled_images:
            if stimulus_trigger_code is not None:
                current_image_surface = self.display.scaled_images[trial_condition]
                self.display.display_image_stimulus(current_image_surface, self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, 500, 600))
                self.serial_comm.send_trigger(stimulus_trigger_code)
            else:
                print(f"Warning: No trigger defined for image condition '{trial_condition}'. Stimulus shown without trigger.")
                current_image_surface = self.display.scaled_images[trial_condition]
                self.display.display_image_stimulus(current_image_surface, self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, 500, 600))
        else:
            print(f"Error: Unknown trial condition or image key '{trial_condition}'.")
            self.display.display_message_screen(f"Error: Missing stimulus for {trial_condition}", 2000, font=self.display.FONT_SMALL, bg_color=self.config.RED)

        return trial_condition
    
    def run_motor_execution_trial(self, trial_number_global, trial_condition):
        print(f"Motor Execution Trial: {trial_number_global}, Condition: {trial_condition} "
              f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")

        # Display fixation cross
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        self.display.display_fixation_cross(self.config.FIXATION_IN_TRIAL_DURATION_MS)
        
        stimulus_trigger_code = self.config.STIMULUS_TRIGGER_MAP.get(trial_condition)
        
        if stimulus_trigger_code is not None:
            current_image_surface = self.display.scaled_images[trial_condition]
            self.display.display_image_stimulus(current_image_surface, self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, 500, 600))
            self.serial_comm.send_trigger(stimulus_trigger_code)

    def _initialize_hardware_and_display(self):
        self.serial_comm.initialize()
        self.display.load_stimulus_images()

        if self.tcp_client.connect():
            self.tcp_listener = threading.Thread(
                target=self.tcp_client.tcp_listener_thread,
                name="TCPListener",
                args=(self.received_data_queue, self.stop_listener_event),
                daemon=True
            )
            self.tcp_listener.start()
        else:
            print("Warning: TCP connection failed. Proceeding without TCP data reception.")

    def _show_intro_screen(self):
        intro_text = "Welcome to the Motor Imagery Experiment!\n\nPlease focus on the stimulus presented.\n\n"
        if self.config.INTRO_WAIT_KEY_PRESS:
            intro_text += "Press any key to begin."
            self.display.display_message_screen(intro_text, wait_for_key=True, font=self.display.FONT_MEDIUM)
        else:
            intro_text += f"The experiment will begin in {self.config.INTRO_DURATION_MS // 1000} seconds."
            self.display.display_message_screen(intro_text, duration_ms=self.config.INTRO_DURATION_MS, font=self.display.FONT_MEDIUM)

    def _run_block(self, block_num):
        self.serial_comm.send_trigger(self.config.TRIGGER_BLOCK_START)
        self._drain_server_queue()

        self.display.display_loading_screen("Generating trials for Block...", font=self.display.FONT_MEDIUM)
        trial_conditions = self.trial_generator.generate_trial_list_for_block()

        if len(trial_conditions) != self.config.TRIALS_PER_BLOCK:
            self._handle_critical_error("Trial list length mismatch.")
            return
        
        self.display.display_message_screen("Motor Execution Trials", duration_ms=2000, font=self.display.FONT_LARGE)
        
        motor_execution_trails = self.config.NORMAL_FINGER_TYPES + ["sixth"]
        random.shuffle(motor_execution_trails)
        
        for trial_index, condition in enumerate(motor_execution_trails, 1):
            self._check_exit_keys()
            global_trial_num = (block_num - 1) * self.config.NUM_MOTOR_EXECUTION_TRIALS_PER_BLOCK + trial_index
            print(f"Running Motor Execution Trial {global_trial_num} for condition: {condition}")
            presented_condition = self.run_motor_execution_trial(global_trial_num, condition)
            self.display.display_blank_screen(self.config.SHORT_BREAK_DURATION_MS)

        
        self.display.display_message_screen("Motor Imagery Trials", duration_ms=2000, font=self.display.FONT_LARGE)
        

        for trial_index, condition in enumerate(trial_conditions, 1):
            self._check_exit_keys()
            global_trial_num = (block_num - 1) * self.config.TRIALS_PER_BLOCK + trial_index
            presented_condition = self.run_trial(global_trial_num, condition)
            self._handle_trial_feedback(block_num, trial_index, global_trial_num, presented_condition)

        self.serial_comm.send_trigger(self.config.TRIGGER_BLOCK_END)
        self._show_block_break_screen(block_num)

    def _handle_trial_feedback(self, block_num, trial_in_block, global_trial_num, condition):
        server_feedback = self._get_server_feedback()
        erd_value = self._extract_erd_value(server_feedback)

        self.data_logger.add_trial_data({
            "participant_id": self.participant_id,
            "block": block_num,
            "trial_in_block": trial_in_block,
            "global_trial_num": global_trial_num,
            "condition": condition,
            "category": self.trial_generator.get_condition_category(condition),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "server_feedback": json.dumps(server_feedback)
        })

        self.erd_history.append(erd_value)
        if condition != self.config.BLANK_CONDITION_NAME:
            self.display.display_erd_feedback_bar(erd_value, duration_ms=self.config.ERD_FEEDBACK_DURATION_MS)
        self.serial_comm.send_trigger(self.config.TRIGGER_SHORT_BREAK_ONSET)
        self.display.display_blank_screen(self.config.SHORT_BREAK_DURATION_MS)

    def _get_server_feedback(self):
        if not self.tcp_client.socket:
            return {}
        try:
            raw = self.received_data_queue.get_nowait()
            return json.loads(raw) if raw else {}
        except queue.Empty:
            return {}
        except json.JSONDecodeError:
            print("Warning: Received non-JSON feedback.")
            return {}

    def _extract_erd_value(self, feedback):
        try:
            erd = float(feedback.get("erd_percent", 0.0))
            print(f"Received ERD value: {erd}")
            return erd
        except (ValueError, TypeError):
            print(f"Invalid ERD value: {feedback.get('erd_percent')}. Using 0.0.")
            return 0.0

    def _drain_server_queue(self):
        latest_response = ""
        while not self.received_data_queue.empty():
            latest_response = self.received_data_queue.get_nowait()
        if latest_response:
            print(f"Latest server response: {latest_response}")

    def _check_exit_keys(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                self._close_all_connections()
                self.display.quit_pygame_and_exit()

    def _show_block_break_screen(self, block_num):
        if block_num < self.config.NUM_BLOCKS:
            msg = f"End of Block {block_num}.\n\nTake a break.\n\nPress any key to continue to the next block."
            self.display.display_message_screen(msg, wait_for_key=True, font=self.display.FONT_MEDIUM)
        else:
            self.display.display_message_screen("All Blocks Completed!", duration_ms=3000, font=self.display.FONT_MEDIUM)

    def _end_experiment(self):
        self.serial_comm.send_trigger(self.config.TRIGGER_EXPERIMENT_END)
        self.display.display_message_screen("Experiment Finished!\n\nThank you for your participation.", duration_ms=5000, wait_for_key=True, font=self.display.FONT_LARGE)

        saved_file = self.data_logger.save_data(self.participant_id)
        if saved_file:
            self.display.display_message_screen(f"Data saved to:\n{saved_file}", duration_ms=4000, font=self.display.FONT_SMALL)
        else:
            self.display.display_message_screen("Error: Could not save data!", duration_ms=3000, font=self.display.FONT_SMALL, bg_color=self.config.RED)

        self._close_all_connections()
        self.display.quit_pygame_and_exit()

    def _handle_critical_error(self, message):
        print(f"CRITICAL Error: {message}")
        self.display.display_message_screen(f"CRITICAL Error: {message}", 5000, bg_color=self.config.RED)
        self._close_all_connections()
        self.display.quit_pygame_and_exit()

    def run_experiment(self):
        self._initialize_hardware_and_display()
        self._show_intro_screen()
        self.serial_comm.send_trigger(self.config.TRIGGER_EXPERIMENT_START)

        for block_num in range(1, self.config.NUM_BLOCKS + 1):
            self._run_block(block_num)

        self._end_experiment()


# --- Main Experiment Loop ---

if __name__ == "__main__":
    config = ExperimentConfig()
    expected_total_trials = (config.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK +
                             (config.NUM_EACH_NORMAL_FINGER_PER_BLOCK * config.NUM_NORMAL_FINGERS) +
                             config.NUM_BLANK_TRIALS_PER_BLOCK)

    if expected_total_trials != config.TRIALS_PER_BLOCK:
        print(f"Error: Mismatch in total trial count. Expected: {expected_total_trials}, Got: {config.TRIALS_PER_BLOCK}")
        sys.exit()
    if config.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK != config.NUM_EACH_NORMAL_FINGER_PER_BLOCK * config.NUM_NORMAL_FINGERS:
        print(f"Error: Mismatch in normal finger trial counts.")
        sys.exit()
    else:
        experiment = Experiment()
        try:
            experiment.run_experiment()
        except SystemExit:
            print("Experiment exited.")
        except Exception as e:
            print(f"An unexpected error occurred during the experiment: {e}")
        finally:
            # Ensure resources are closed even if an unexpected error occurs before the graceful shutdown
            experiment._close_all_connections()