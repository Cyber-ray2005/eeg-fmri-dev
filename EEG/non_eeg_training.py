import pygame
import random
import time
import sys
import json

from utils.trial_generator import TrialGenerator
from utils.pygame_display import PygameDisplay
from utils.logger import TrialDataLogger
from embodiment.EmbodimentExcercise import EmbodimentExercise
import platform
import subprocess
import sys
import finger_controller as fc
import argparse


class MockSerialCommunication:
    """
    Mock serial communication class for non-EEG training.
    Provides the same interface as SerialCommunication but doesn't send actual triggers.
    """
    def __init__(self, port, baud_rate):
        self.port = port
        self.baud_rate = baud_rate
        print(f"Mock Serial: Initialized for port {port} (no actual EEG recording)")
    
    def initialize(self):
        print("Mock Serial: Initialized successfully (no EEG triggers will be sent)")
    
    def send_trigger(self, trigger_code):
        print(f"Mock Serial: Would send trigger {trigger_code} (EEG recording disabled)")
    
    def close(self):
        print("Mock Serial: Closed (no actual connection to close)")





def cross_platform_beep(frequency=1000, duration_ms=100):
    """
    Cross-platform beep function.
    
    Args:
        frequency: Frequency in Hz (default: 1000)
        duration_ms: Duration in milliseconds (default: 100)
    """
    try:
        if platform.system() == "Windows":
            import winsound
            winsound.Beep(frequency, duration_ms)
        elif platform.system() == "Darwin":  # macOS
            # Use system beep on macOS
            subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"], check=False)
        elif platform.system() == "Linux":
            # Use system beep on Linux
            subprocess.run(["paplay", "/usr/share/sounds/alsa/Front_Right.wav"], check=False)
        else:
            # Fallback: print to console
            print(f"BEEP! ({frequency}Hz, {duration_ms}ms)")
    except Exception as e:
        # Fallback if audio doesn't work
        print(f"BEEP! ({frequency}Hz, {duration_ms}ms) - Audio error: {e}")


# --- Experiment Parameters ---
class ExperimentConfig:
    """
    Holds all configuration parameters for the non-EEG training experiment, including display, timing, 
    trial structure, and stimulus mapping. TCP communication and ERD feedback removed for training mode.
    """
    def __init__(self):
        # Screen dimensions
        self.SCREEN_WIDTH = 1000
        self.SCREEN_HEIGHT = 700
        self.FULLSCREEN_MODE = True

        # Colors (RGB tuples)
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (150, 150, 150)
        self.RED = (255, 0, 0)
        self.BLUE = (0, 0, 255)
        self.CIRCLE_COLOR = (200, 200, 200)

        # Durations (in milliseconds)
        self.INTRO_WAIT_KEY_PRESS = True
        self.INTRO_DURATION_MS = 5000
        self.INITIAL_CALIBRATION_DURATION_MS = 3000
        self.FIXATION_IN_TRIAL_DURATION_MS = 3000
        self.IMAGE_DISPLAY_DURATION_MS = 3000
        self.SHORT_BREAK_DURATION_MS = 1500
        self.LONG_BREAK_DURATION_MS = 60* 1000  # 60 seconds

        # Trial structure
        self.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK = 5
        self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK = 5
        self.NUM_BLANK_TRIALS_PER_BLOCK = 5
        self.NUM_NORMAL_FINGERS = 5
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
        self.SIXTH_FINGER_IMAGE_NAME_BLUE = "Hand_SixthFinger_Highlighted.png"
        self.NORMAL_FINGER_IMAGE_MAP = {
            "thumb": "Hand_Thumb_Highlighted.png",
            "index": "Hand_Index_Highlighted.png",
            "middle": "Hand_Middle_Highlighted.png",
            "ring": "Hand_Ring_Highlighted.png",
            "pinky": "Hand_Pinky_Highlighted.png",
            "thumb_blue": "Hand_Thumb_Highlighted.png",
            "index_blue": "Hand_Index_Highlighted.png",
            "middle_blue": "Hand_Middle_Highlighted.png",
            "ring_blue": "Hand_Ring_Highlighted.png",
            "pinky_blue": "Hand_Pinky_Highlighted.png"
        }
        self.NORMAL_FINGER_TYPES = ["thumb", "index", "middle", "ring", "pinky"]
        self.BLANK_CONDITION_NAME = "blank"

        # Condition categories for streak checking
        self.CATEGORY_SIXTH = "sixth_finger_cat"
        self.CATEGORY_NORMAL = "normal_finger_cat"
        self.CATEGORY_BLANK = "blank_cat"

        # Serial Port Configuration and Triggers (Mock only - no actual EEG recording)
        self.SERIAL_PORT = 'COM4'  # Not used in non-EEG version
        self.BAUD_RATE = 9600      # Not used in non-EEG version
        self.REST_FINGER_IMAGE_NAME = "Rest.png"
        

        # Define trigger values (bytes) - For reference only, not sent in non-EEG version
        self.TRIGGER_BLOCK_START = 14
        self.TRIGGER_BLOCK_END = 13
        self.TRIGGER_FIXATION_ONSET = 10
        self.TRIGGER_SIXTH_FINGER_ONSET = 6
        self.TRIGGER_THUMB_ONSET = 1
        self.TRIGGER_INDEX_ONSET = 2
        self.TRIGGER_MIDDLE_ONSET = 3
        self.TRIGGER_RING_ONSET = 4
        self.TRIGGER_PINKY_ONSET = 5
        self.TRIGGER_SIXTH_FINGER_ONSET_BLUE = 96
        self.TRIGGER_THUMB_ONSET_BLUE = 16
        self.TRIGGER_INDEX_ONSET_BLUE = 32
        self.TRIGGER_MIDDLE_ONSET_BLUE = 48
        self.TRIGGER_RING_ONSET_BLUE = 64
        self.TRIGGER_PINKY_ONSET_BLUE = 80
        self.TRIGGER_CONTROL_STIMULUS_ONSET = 7
        self.TRIGGER_SHORT_BREAK_ONSET = 9
        self.YES_TRIGGER = 11
        self.NO_TRIGGER = 12
        
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
            self.BLANK_CONDITION_NAME: self.TRIGGER_CONTROL_STIMULUS_ONSET,
            "sixth_blue": self.TRIGGER_SIXTH_FINGER_ONSET_BLUE,
            "thumb_blue": self.TRIGGER_THUMB_ONSET_BLUE,
            "index_blue": self.TRIGGER_INDEX_ONSET_BLUE,
            "middle_blue": self.TRIGGER_MIDDLE_ONSET_BLUE,
            "ring_blue": self.TRIGGER_RING_ONSET_BLUE,
            "pinky_blue": self.TRIGGER_PINKY_ONSET_BLUE,
        }
        
        # List of words that could be used for writing tasks (for embodiment exercise)
        self.CHARACTERS_TO_WRITE = ["Tab", "Door", "Book", "Tree", "Box", "Chat", "Ball", "Bird", "Fish", "Star",
                "Rain", "Snow", "Wind", "Fire", "Rock", "Sand", "Lake", "Road", "Path", "Leaf",
                "Bark", "Ring", "King", "Cape", "Card", "Coin", "Note", "Fork", "Spot", "Dish",
                "Cup", "Mug", "Lamp", "Bulb", "Rope", "Nail", "Tape", "Bell", "Drum", "Flag",
                "Wall", "Gate", "Door", "Vent", "Roof", "Tile", "Wire", "Plug", "Jack", "Knob",
                "Soap", "Tow", "Comb", "Sink", "Hose", "Tube", "Vent", "Boot", "Shoe", "Sock",
                "Vest", "Coat", "Belt", "Scar", "Hat", "Glow", "Book", "Pen", "Ink", "Note",
                "Desk", "Page", "Clip", "File", "Card", "Rule", "Math", "Test", "Quiz", "Plan",
                "Grid", "Code", "List", "Form", "Name", "Word", "Text", "Line", "Data", "Fact",
                "Idea", "Goal", "Time", "Work", "Play", "Game", "Move", "Step", "Jump", "Walk"]
        # Number of characters to write in writing task
        self.NUMBER_OF_CHARACTERS_TO_WRITE = 5
        
        # TCP communication removed for non-EEG training
        


class Experiment:
    """
    Main experiment class that manages the experiment flow, including block and trial structure,
    hardware communication, data logging, and feedback display.
    """
    def __init__(self, file_base_name: str):
        # calibrate the finger by setting it to 0
        fc.execute_finger(0)
        self.config = ExperimentConfig()
        self.display = PygameDisplay(self.config)
        self.serial_comm = MockSerialCommunication(self.config.SERIAL_PORT, self.config.BAUD_RATE)
        self.trial_generator = TrialGenerator(self.config)
        # Initialize embodiment exercise (pre-experiment calibration/training)
        self.embodiment_exercise = EmbodimentExercise(self.config, enable_logging=True, log_name_base=file_base_name)
        self.data_logger = TrialDataLogger({
            "data_folder": "non_eeg_training",
            "fixed_filename": f"{file_base_name}.csv",
            "fieldnames": ["block", "trial_in_block", "global_trial_num", "condition", "category", "trial_type", "timestamp"]
        })
        # ERD-related components removed for non-EEG training

    def _close_all_connections(self):
        """
        Closes all hardware connections (serial only for non-EEG training).
        """
        self.serial_comm.close()
        # TCP connections removed for non-EEG training

    def run_trial(self, trial_number_global, trial_condition):
        """
        Runs a single imagery trial: shows fixation, stimulus, and collects response.
        Sends triggers and displays appropriate images/messages.
        """
        print(f"Global Trial: {trial_number_global}, Condition: {trial_condition} "
              f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")

        # Display blank image instead of fixation cross
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET) # Trigger for fixation onset
        # Original fixation cross code (commented out):
        # self.display.display_fixation_cross(random.choice([self.config.FIXATION_IN_TRIAL_DURATION_MS+500, self.config.FIXATION_IN_TRIAL_DURATION_MS-500]))
        
        # New blank image display:
        fixation_duration = random.choice([self.config.FIXATION_IN_TRIAL_DURATION_MS+500, self.config.FIXATION_IN_TRIAL_DURATION_MS-500])
        blank_image_surface = self.display.scaled_images["blank"]
        self.display.display_image_stimulus(
            blank_image_surface, 
            fixation_duration, 
            (0, 0, blank_image_surface.get_width(), blank_image_surface.get_height())
        )

        # Play beep to indicate stimulus onset
        cross_platform_beep(self.config.BEEP_FREQUENCY, self.config.BEEP_DURATION_MS)
        stimulus_trigger_code = self.config.STIMULUS_TRIGGER_MAP.get(trial_condition)

        if trial_condition == self.config.BLANK_CONDITION_NAME:
            # Blank (rest) trial: show rest message
            self.serial_comm.send_trigger(stimulus_trigger_code)
            # self.display.display_message_screen("REST", duration_ms=self.config.IMAGE_DISPLAY_DURATION_MS, font=self.display.FONT_LARGE, bg_color=self.config.GRAY)
            current_image_surface = self.display.scaled_images[trial_condition]
            self.display.display_image_stimulus(
                    current_image_surface, 
                    self.config.IMAGE_DISPLAY_DURATION_MS, 
                    (0, 0, current_image_surface.get_width(), current_image_surface.get_height())
                )
        elif trial_condition in self.display.scaled_images:
            # Show the appropriate finger image
            if stimulus_trigger_code is not None:
                current_image_surface = self.display.scaled_images[trial_condition]
                self.serial_comm.send_trigger(stimulus_trigger_code)
                self.display.display_image_stimulus(current_image_surface, self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, current_image_surface.get_width(), current_image_surface.get_height()))

            else:
                print(f"Warning: No trigger defined for image condition '{trial_condition}'. Stimulus shown without trigger.")
                current_image_surface = self.display.scaled_images[trial_condition]
                self.display.display_image_stimulus(current_image_surface, self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, current_image_surface.get_width(), current_image_surface.get_height()))

        else:
            print(f"Error: Unknown trial condition or image key '{trial_condition}'.")
            self.display.display_message_screen(f"Error: Missing stimulus for {trial_condition}", 2000, font=self.display.FONT_SMALL, bg_color=self.config.RED)

        # Ask for motor imagery confirmation every 5 trials
        if trial_number_global % 5 == 0:
            yes = self.display.ask_yes_no_question("Did you perform motor imagery?")
            if yes:
                self.serial_comm.send_trigger(self.config.YES_TRIGGER)
            else:
                self.serial_comm.send_trigger(self.config.NO_TRIGGER)
               
        return trial_condition
    
    def run_motor_execution_trial(self, trial_number_global, trial_condition):
        """
        Runs a single motor execution trial (with blue-highlighted finger images).
        """
        print(f"Motor Execution Trial: {trial_number_global}, Condition: {trial_condition} "
              f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")

        # Display blank image instead of fixation cross
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        # Original fixation cross code (commented out):
        # self.display.display_fixation_cross(random.choice([self.config.FIXATION_IN_TRIAL_DURATION_MS+500, self.config.FIXATION_IN_TRIAL_DURATION_MS-500]))
        
        # New blank image display:
        fixation_duration = random.choice([self.config.FIXATION_IN_TRIAL_DURATION_MS+500, self.config.FIXATION_IN_TRIAL_DURATION_MS-500])
        blank_image_surface = self.display.scaled_images["blank"]
        self.display.display_image_stimulus(
            blank_image_surface, 
            fixation_duration, 
            (0, 0, blank_image_surface.get_width(), blank_image_surface.get_height())
        )
        
        cross_platform_beep(self.config.BEEP_FREQUENCY, self.config.BEEP_DURATION_MS)
        
        stimulus_trigger_code = self.config.STIMULUS_TRIGGER_MAP.get(trial_condition+"_blue")
        
        if stimulus_trigger_code is not None:
            current_image_surface = self.display.scaled_images[trial_condition+"_blue"]
            self.serial_comm.send_trigger(stimulus_trigger_code)
            self.display.display_image_stimulus(current_image_surface,  self.config.IMAGE_DISPLAY_DURATION_MS, (0, 0, current_image_surface.get_width(), current_image_surface.get_height()))
            if trial_condition == "sixth":
                fc.execute_finger(100)
        return trial_condition

    def _initialize_hardware_and_display(self):
        """
        Initializes serial port and loads images for non-EEG training.
        """
        self.serial_comm.initialize()
        self.display.load_stimulus_images()
        print("Non-EEG training mode: No TCP connections needed.")

    def _show_intro_screen(self):
        """
        Displays the experiment introduction screen, waiting for key press or timeout.
        """
        intro_text = "Welcome to the Motor Imagery Experiment!\n(Non-EEG Training Version)\n\nPlease focus on the stimulus presented.\n\n"
        if self.config.INTRO_WAIT_KEY_PRESS:
            intro_text += "Press any key to begin."
            self.display.display_message_screen(intro_text, wait_for_key=True, font=self.display.FONT_LARGE)
        else:
            intro_text += f"The experiment will begin in {self.config.INTRO_DURATION_MS // 1000} seconds."
            self.display.display_message_screen(intro_text, duration_ms=self.config.INTRO_DURATION_MS, font=self.display.FONT_LARGE)

    def _run_block(self, block_num):
        """
        Runs a single block of the experiment, including both motor execution and imagery trials.
        Handles trial randomization, feedback, and breaks.
        """
        self.serial_comm.send_trigger(self.config.TRIGGER_BLOCK_START)
        # No server queue to drain in non-EEG training

        # self.display.display_loading_screen("Generating trials for Block...", font=self.display.FONT_MEDIUM)
        for iteration in range(3):
            trial_conditions = self.trial_generator.generate_trial_list_for_block()

            if len(trial_conditions) != self.config.TRIALS_PER_BLOCK:
                self._handle_critical_error("Trial list length mismatch.")
                return
            
            # Motor execution phase
            self.display.display_message_screen("#blue:MOTOR EXECUTION# Trials", duration_ms=2000, font=self.display.FONT_LARGE)
            instruction = "#blue:MOTOR EXECUTION#\n\nIn the next slides, you will see a hand illustration \n with one of the fingers highlighted less gray(whiter).\n\n Flex and extend the highlighted finger. \n\n Press any key to continue."
            self.display.display_message_screen(instruction, wait_for_key=True, font=self.display.FONT_LARGE)
            
            motor_execution_trails = self.config.NORMAL_FINGER_TYPES + ["sixth"]
            random.shuffle(motor_execution_trails)
            
            for trial_index, condition in enumerate(motor_execution_trails, 1):
                self._check_exit_keys()
                # Calculate global motor execution trial number: (block-1)*6*3 + (iteration-1)*6 + trial_index
                global_trial_num = (block_num - 1) * 6 * 3 + iteration * 6 + trial_index
                print(f"Running Motor Execution Trial {global_trial_num} for condition: {condition}")
                presented_condition = self.run_motor_execution_trial(global_trial_num, condition)
                
                # Log motor execution trial data
                self.data_logger.add_trial_data({
                    "block": block_num,
                    "trial_in_block": trial_index,
                    "global_trial_num": global_trial_num,
                    "condition": presented_condition,
                    "category": self.trial_generator.get_condition_category(presented_condition),
                    "trial_type": "motor_execution",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
                self.display.display_blank_screen(self.config.SHORT_BREAK_DURATION_MS)

            # Motor imagery phase
            self.display.display_message_screen("#red:MOTOR IMAGERY# Trials", duration_ms=2000, font=self.display.FONT_LARGE)
            instruction = "#red:MOTOR IMAGERY#\n\nIn the next slides, you will see a hand illustration\nwith one of the fingers highlighted less gray(whiter).\n\nImagine, kinesthetically, flexing and extending the higlighted finger.\nPlease try to avoid any movement throughout the exercise.\n\nPress any key to continue."
            self.display.display_message_screen(instruction, wait_for_key=True, font=self.display.FONT_LARGE)

            for trial_index, condition in enumerate(trial_conditions, 1):
                self._check_exit_keys()
                # Calculate global trial number: (block-1)*TRIALS_PER_BLOCK*3 + (iteration-1)*TRIALS_PER_BLOCK + trial_index
                global_trial_num = (block_num - 1) * self.config.TRIALS_PER_BLOCK * 3 + iteration * self.config.TRIALS_PER_BLOCK + trial_index
                presented_condition = self.run_trial(global_trial_num, condition)
                
                # Log trial data (no feedback breaks for natural flow)
                self.data_logger.add_trial_data({
                    "block": block_num,
                    "trial_in_block": trial_index,
                    "global_trial_num": global_trial_num,
                    "condition": presented_condition,
                    "category": self.trial_generator.get_condition_category(presented_condition),
                    "trial_type": "motor_imagery",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
                print(f"Trial {global_trial_num} completed: {presented_condition} (Non-EEG training)")
                # No artificial breaks - let trials flow naturally

        self.serial_comm.send_trigger(self.config.TRIGGER_BLOCK_END)
        self._show_block_break_screen(block_num)

    # All ERD-related methods removed for non-EEG training
    # Trial feedback is now handled inline within the trial loop

    def _check_exit_keys(self):
        """
        Checks for quit or escape key events to allow graceful exit.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                self._close_all_connections()
                self.display.quit_pygame_and_exit()

    def _show_block_break_screen(self, block_num):
        """
        Displays a break/timer screen between blocks, or a completion message at the end.
        """
        if block_num < self.config.NUM_BLOCKS:
            msg = f"End of Block {block_num}.\n\nTake a break."
            self.display.display_timer_with_message(msg, self.config.LONG_BREAK_DURATION_MS)
            msg = "Press any key to continue to the next block."
            self.display.display_message_screen(msg, wait_for_key=True, font=self.display.FONT_MEDIUM)
        else:
            self.display.display_message_screen("All Blocks Completed!", duration_ms=3000, font=self.display.FONT_MEDIUM)

    def _end_experiment(self):
        """
        Displays the end-of-experiment message and saves data.
        """
        self.display.display_message_screen("Experiment Finished!\n\nThank you for your participation.", duration_ms=5000, wait_for_key=True, font=self.display.FONT_LARGE)

        saved_file = self.data_logger.save_data(None)
        if saved_file:
            self.display.display_message_screen(f"Data saved to:\n{saved_file}", duration_ms=4000, font=self.display.FONT_SMALL)
        else:
            self.display.display_message_screen("Training completed!\n(No trial data to save)", duration_ms=3000, font=self.display.FONT_SMALL)

        self._close_all_connections()
        self.display.quit_pygame_and_exit()

    def _handle_critical_error(self, message):
        """
        Handles critical errors by displaying a message and exiting the experiment.
        """
        print(f"CRITICAL Error: {message}")
        self.display.display_message_screen(f"CRITICAL Error: {message}", 5000, bg_color=self.config.RED)
        self._close_all_connections()
        self.display.quit_pygame_and_exit()

    def run_experiment(self):
        """
        Main experiment loop: initializes hardware, runs all blocks, and ends experiment.
        """
        self._initialize_hardware_and_display()
        self._show_intro_screen()
        # === EMBODIMENT EXERCISE PHASE ===
        # Run pre-experiment embodiment exercise to establish sixth finger representation
        self.embodiment_exercise.run()

        for block_num in range(1, self.config.NUM_BLOCKS + 1):
            self._run_block(block_num)

        self._end_experiment()


# --- Main Experiment Loop ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Non-EEG training session")
    parser.add_argument("--p", required=True, type=int, help="Participant number")
    parser.add_argument("--w", required=True, type=int, help="Week number")
    parser.add_argument("--s", required=True, type=int, help="Session number")
    args = parser.parse_args()

    file_base = f"P{args.p}_w{args.w}_s{args.s}"
    # Validate trial configuration before running
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
        experiment = Experiment(file_base)
        try:
            experiment.run_experiment()
        except SystemExit:
            print("Experiment exited.")
        except Exception as e:
            print(f"An unexpected error occurred during the experiment: {e}")
        finally:
            # Ensure resources are closed even if an unexpected error occurs before the graceful shutdown
            experiment._close_all_connections()
            # Ensure pygame is properly terminated to prevent hanging processes
            print("\n" + "="*50)
            print("NON-EEG TRAINING EXPERIMENT ENDED")
            print("="*50)
            try:
                pygame.quit()
            except:
                pass  # Pygame might already be quit
            sys.exit(0)
