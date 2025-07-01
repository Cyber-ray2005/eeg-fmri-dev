import pygame
import random
import time
import sys
import os
import queue

from trial_generator import TrialGenerator
from pygame_display import PygameDisplay
from logger import TrialDataLogger
from serial_communication import SerialCommunication
import winsound

# --- Configuration Class ---
class ExperimentConfig:
    def __init__(self):
        # Screen dimensions
        self.SCREEN_WIDTH = 1000
        self.SCREEN_HEIGHT = 700
        self.FULLSCREEN_MODE = True

        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (150, 150, 150)
        self.RED = (255, 0, 0)
        self.BLUE = (0, 0, 255)
        self.RED = (255, 0, 0)
        self.CIRCLE_COLOR = (200, 200, 200)

        # Durations (in milliseconds)
        self.INTRO_WAIT_KEY_PRESS = True
        self.INTRO_DURATION_MS = 5000
        self.INITIAL_CALIBRATION_DURATION_MS = 3000
        self.FIXATION_IN_TRIAL_DURATION_MS = 3000
        self.IMAGE_DISPLAY_DURATION_MS = 3000
        self.SHORT_BREAK_DURATION_MS = 1500

        # Trial structure
        self.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK = 15
        self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK = 15
        self.NUM_BLANK_TRIALS_PER_BLOCK = 15
        self.NUM_NORMAL_FINGERS = 5
        self.NUM_EACH_NORMAL_FINGER_PER_BLOCK = self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK // self.NUM_NORMAL_FINGERS
        self.TRIALS_PER_BLOCK = (self.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK +
                                 self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK +
                                 self.NUM_BLANK_TRIALS_PER_BLOCK)
        self.NUM_BLOCKS = 3

        # Streak control parameters
        self.MAX_CONSECUTIVE_CATEGORY_STREAK = 1

        # Stimulus Paths and Names
        self.IMAGE_FOLDER = "images"
        self.SIXTH_FINGER_IMAGE_NAME = "Hand_SixthFinger_Highlighted.png"
        self.REST_FINGER_IMAGE_NAME = "Rest.png"
        self.SIXTH_FINGER_BLUE_IMAGE_NAME = "Hand_SixthFinger_Highlighted_Blue.png"
        self.NORMAL_FINGER_IMAGE_MAP = {
            "thumb": "Hand_Index_Highlighted.png",
            "index": "Hand_Index_Highlighted.png",
            "middle": "Hand_Middle_Highlighted.png",
            "ring": "Hand_Ring_Highlighted.png",
            "pinky": "Hand_Pinky_Highlighted.png",
            "thumb_blue": "Hand_Thumb_Highlighted_Blue.png",
            "index_blue": "Hand_Index_Highlighted_Blue.png",
            "middle_blue": "Hand_Middle_Highlighted_Blue.png",
            "ring_blue": "Hand_Ring_Highlighted_Blue.png",
            "pinky_blue": "Hand_Pinky_Highlighted_Blue.png"
        }
        self.NORMAL_FINGER_TYPES = ["thumb", "index", "middle", "ring", "pinky"]
        self.BLANK_CONDITION_NAME = "blank"

        # Condition categories for streak checking
        self.CATEGORY_SIXTH = "sixth_finger_cat"
        self.CATEGORY_NORMAL = "normal_finger_cat"
        self.CATEGORY_BLANK = "blank_cat"

        # Serial Port Configuration and Triggers
        self.SERIAL_PORT = 'COM4'
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
        self.BEEP_FREQUENCY = 1000  # Frequency in Hz for the beep sound
        self.BEEP_DURATION_MS = 100  # Duration in milliseconds for the beep sound

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


# --- Main Experiment Class ---
class Experiment:
    def __init__(self):
        self.config = ExperimentConfig()
        self.display = PygameDisplay(self.config)
        self.serial_comm = SerialCommunication(self.config.SERIAL_PORT, self.config.BAUD_RATE)
        self.trial_generator = TrialGenerator(self.config)
        self.data_logger = TrialDataLogger({
            "data_folder": "experiment_logs",
            "filename_template": "{participant_id}_session_log_{timestamp}.csv",
            "fieldnames": ["participant_id", "block", "trial_num", "condition", "response_time", "timestamp"]
        })
        self.participant_id = "P" + str(random.randint(100, 999))
        self.er_data_queue = queue.Queue() # For potential future ER data reception
        self.tcp_client = None # Placeholder for TCP client

    def _close_all_connections(self):
        self.serial_comm.close()
        # if self.tcp_client: # If you implement a TCP client, uncomment this
        #     self.tcp_client.close()
    
    def run_motor_execution_trial(self, trial_condition):
        print(f"Motor Execution Trial, Condition: {trial_condition} "
              f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")

        # Display fixation cross
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        self.display.display_fixation_cross(random.choice([self.config.FIXATION_IN_TRIAL_DURATION_MS+500, self.config.FIXATION_IN_TRIAL_DURATION_MS-500]))
        winsound.Beep(self.config.BEEP_FREQUENCY, self.config.BEEP_DURATION_MS)  # Beep sound to indicate trial start
        stimulus_trigger_code = self.config.STIMULUS_TRIGGER_MAP.get(trial_condition)
        
        if stimulus_trigger_code is not None:
            current_image_surface = self.display.scaled_images[trial_condition+"_blue"]
            self.serial_comm.send_trigger(stimulus_trigger_code)
            self.display.display_image_stimulus(current_image_surface,  self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, current_image_surface.get_width(), current_image_surface.get_height()*0.75))


    def run_trial(self, trial_number_global, trial_condition):
        print(f"Global Trial: {trial_number_global}, Condition: {trial_condition} "
              f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")

        # Display fixation cross
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET) # Trigger for fixation cross
        # self.display.display_fixation_cross(self.config.FIXATION_IN_TRIAL_DURATION_MS)
        self.display.display_fixation_cross(random.choice([self.config.FIXATION_IN_TRIAL_DURATION_MS+500, self.config.FIXATION_IN_TRIAL_DURATION_MS-500]))
          

        winsound.Beep(self.config.BEEP_FREQUENCY, self.config.BEEP_DURATION_MS)  # Beep sound to indicate trial start

        stimulus_trigger_code = self.config.STIMULUS_TRIGGER_MAP.get(trial_condition)

        if trial_condition == self.config.BLANK_CONDITION_NAME:
            # self.display.display_blank_screen(self.config.IMAGE_DISPLAY_DURATION_MS)
            current_image_surface = self.display.scaled_images["rest"]
            self.serial_comm.send_trigger(stimulus_trigger_code)
            # self.display.display_image_stimulus(current_image_surface,  self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, current_image_surface.get_width(), current_image_surface.get_height()*0.75))
            self.display.display_message_screen("REST", duration_ms=self.config.IMAGE_DISPLAY_DURATION_MS, font=self.display.FONT_LARGE)
        elif trial_condition in self.display.scaled_images:
            if stimulus_trigger_code is not None:
                current_image_surface = self.display.scaled_images[trial_condition]
                self.serial_comm.send_trigger(stimulus_trigger_code)
                self.display.display_image_stimulus(current_image_surface, self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, current_image_surface.get_width(), current_image_surface.get_height()*0.75))
            else:
                print(f"Warning: No trigger defined for image condition '{trial_condition}'. Stimulus shown without trigger.")
                current_image_surface = self.display.scaled_images[trial_condition]
                self.display.display_image_stimulus(current_image_surface, self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, current_image_surface.get_width(), current_image_surface.get_height()*0.75))
        else:
            print(f"Error: Unknown trial condition or image key '{trial_condition}'.")
            self.display.display_message_screen(f"Error: Missing stimulus for {trial_condition}", 2000, font=self.display.FONT_SMALL, bg_color=self.config.RED)

        if trial_number_global % 5 == 0:
            self.display.ask_yes_no_question("Did you perform the motor imagery?")
            
        
        return trial_condition

    def run_experiment(self):
        self.serial_comm.initialize()
        self.display.load_stimulus_images()

        intro_text = "Welcome to the Motor Imagery Experiment!\n\n"
        if self.config.INTRO_WAIT_KEY_PRESS:
            intro_text += "Press any key to begin."
            self.display.display_message_screen(intro_text, wait_for_key=True, font=self.display.FONT_LARGE)
        else:
            intro_text += f"The experiment will begin in {self.config.INTRO_DURATION_MS/1000:.0f} seconds."
            self.display.display_message_screen(intro_text, duration_ms=self.config.INTRO_DURATION_MS, font=self.display.FONT_LARGE)

        # self.serial_comm.send_trigger(self.config.TRIGGER_EXPERIMENT_START)
        self.display.display_message_screen("Motor Execution Trials", duration_ms=2000, font=self.display.FONT_LARGE)
        instruction = "In the next slides, you will see a hand illustration \n with one of the fingers highlighted #BLUE:BLUE#.\n\n Flex and extend the encircled finger. \n\n Press any key to continue."
        self.display.display_message_screen(instruction, wait_for_key=True, font=self.display.FONT_LARGE)
        motor_execution_trails = self.config.NORMAL_FINGER_TYPES
        random.shuffle(motor_execution_trails)
        
        for trial_index, condition in enumerate(motor_execution_trails, 1):
            presented_condition = self.run_motor_execution_trial(condition)
            self.display.display_blank_screen(self.config.SHORT_BREAK_DURATION_MS)

        
        self.display.display_message_screen("Motor Imagery Trials", duration_ms=2000, font=self.display.FONT_LARGE)
        instruction = " In the next slides , you will see a hand illustration \n with one of teh fingers encircled #RED:RED#. \n\n Imagine, kinesthetically, flexing and extending the encircled finger.  \n\n Press any key to continue."
        self.display.display_message_screen(instruction, wait_for_key=True, font=self.display.FONT_LARGE)
        for block_num in range(1, self.config.NUM_BLOCKS + 1):
            # self.serial_comm.send_trigger(self.config.TRIGGER_BLOCK_START)
            self.display.display_loading_screen("Generating trials for Block...", font=self.display.FONT_MEDIUM, bg_color=self.config.BLACK, text_color=self.config.WHITE)
            current_block_trial_conditions = self.trial_generator.generate_trial_list_for_block()

            if len(current_block_trial_conditions) != self.config.TRIALS_PER_BLOCK:
                print(f"CRITICAL Error: Trial list length mismatch.")
                self.display.display_message_screen("CRITICAL Error: Trial configuration issue.", 5000, bg_color=self.config.RED)
                self._close_all_connections()
                self.display.quit_pygame_and_exit()
                self.display.display_message_screen("Motor Execution Trials", duration_ms=2000, font=self.display.FONT_LARGE)
        

            for trial_num_in_block, condition in enumerate(current_block_trial_conditions, 1):
                for event in pygame.event.get():
                    if event.type == pygame.QUIT: self._close_all_connections(); self.display.quit_pygame_and_exit()
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: self._close_all_connections(); self.display.quit_pygame_and_exit()

                trial_global_num = (block_num - 1) * self.config.TRIALS_PER_BLOCK + trial_num_in_block
                presented_condition = self.run_trial(trial_global_num, condition)

                trial_data = {
                    "participant_id": self.participant_id,
                    "block": block_num,
                    "trial_in_block": trial_num_in_block,
                    "global_trial_num": trial_global_num,
                    "condition": presented_condition,
                    "category": self.trial_generator.get_condition_category(presented_condition),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.data_logger.add_trial_data(trial_data)

                # self.serial_comm.send_trigger(self.config.TRIGGER_SHORT_BREAK_ONSET)
                self.display.display_blank_screen(self.config.SHORT_BREAK_DURATION_MS)

            # self.serial_comm.send_trigger(self.config.TRIGGER_BLOCK_END)
            # In a real scenario, block_end_server_response would come from a server.
            # For now, we'll use a placeholder or empty string.
            block_end_server_response = "" # Placeholder for server response

            if block_num < self.config.NUM_BLOCKS:
                long_break_message = f"End of Block {block_num}.\n\nTake a break.\n\nPress any key to continue to the next block."
                self.display.display_message_screen(long_break_message, wait_for_key=True, font=self.display.FONT_MEDIUM, server_response=block_end_server_response)
            else:
                self.display.display_message_screen("All Blocks Completed!", duration_ms=3000, font=self.display.FONT_MEDIUM, server_response=block_end_server_response)

        # self.serial_comm.send_trigger(self.config.TRIGGER_EXPERIMENT_END)
        self.display.display_message_screen("Experiment Finished!\n\nThank you for your participation.", duration_ms=5000, wait_for_key=True, font=self.display.FONT_LARGE)

        saved_file = self.data_logger.save_data(self.participant_id)
        if saved_file:
            self.display.display_message_screen(f"Data saved to:\n{saved_file}", duration_ms=4000, font=self.display.FONT_SMALL)
        else:
            self.display.display_message_screen(f"Error: Could not save data!", duration_ms=3000, font=self.display.FONT_SMALL, bg_color=self.config.RED)

        self._close_all_connections()
        self.display.quit_pygame_and_exit()


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