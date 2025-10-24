import threading # --- NEW: Import threading for background data reception ---
import queue # --- NEW: Import queue for thread-safe data passing ---

import pygame
import random
import time
import sys
import queue
import json

from utils.trial_generator import TrialGenerator
from utils.pygame_display import PygameDisplay
from utils.logger import TrialDataLogger, ERDLogger
from utils.serial_communication import SerialCommunication
from utils.tcp_client import TCPClient # --- NEW: Import the TCP client class ---
from embodiment.EmbodimentExerciseGrasp import EmbodimentExerciseGrasp # Runs pre-experiment grasp embodiment exercise
import platform
import subprocess
import sys
import argparse

# Step 1 : Import the library
import finger_controller as fc

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
    Holds all configuration parameters for the experiment, including display, timing, trial structure,
    stimulus mapping, serial port, and TCP communication settings.
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
        self.ERD_FEEDBACK_DURATION_MS = 2000
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

        # Serial Port Configuration and Triggers
        self.SERIAL_PORT = 'COM4'
        self.BAUD_RATE = 9600
        self.REST_FINGER_IMAGE_NAME = "Rest.png"
        

        # Define trigger values (bytes)
        self.TRIGGER_BLOCK_START = 13
        self.TRIGGER_BLOCK_END = 14
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
        
        # New triggers for embodiment exercise
        self.TRIGGER_GRASP_START = 8
        self.TRIGGER_RELEASE_START = 15
        
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
        
        # Test flag for embodiment exercise - if True, all imagery is successful
        self.TEST_MODE_EMBODIMENT = False
        
        self.TCP_HOST =  '127.0.0.1'
        self.TCP_PORT = 50000  # The port used by the server
        


class Experiment:
    """
    Main experiment class that manages the experiment flow, including block and trial structure,
    hardware communication, data logging, and feedback display.
    """
    def __init__(self, file_base_name: str, config: ExperimentConfig = None):
        # Step 2 : In the Experiment class init, calibrate the finger by setting to 0
        fc.execute_finger(0) 
        self.file_base_name = file_base_name
        self.config = config if config is not None else ExperimentConfig()
        self.display = PygameDisplay(self.config)
        self.serial_comm = SerialCommunication(self.config.SERIAL_PORT, self.config.BAUD_RATE)
        self.trial_generator = TrialGenerator(self.config)
        # Initialize TCP client first
        self.tcp_client = TCPClient(self.config.TCP_HOST, self.config.TCP_PORT)
        # CSV data logger removed as per user request (empty files not needed)
        self.erd_logger = ERDLogger(filename=f"{file_base_name}.csv")  # Initialize ERD-specific logger
        self.er_data_queue = queue.Queue() # For potential future ER data reception
        self.erd_history = [] # Placeholder for ERD history
        self.received_data_queue = queue.Queue() # Queue to pass data from thread to main loop
        self.stop_listener_event = threading.Event() # Event to signal the listener thread to stop
        self.embodiment_exercise = None

    def _close_all_connections(self):
        """
        Closes all hardware and network connections (serial, TCP).
        """
        self.serial_comm.close()
        if self.tcp_client: # If you implement a TCP client, uncomment this
            self.tcp_client.close(self.stop_listener_event)

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
            if trial_condition =="sixth":
                fc.execute_finger(100)  


    def _initialize_hardware_and_display(self):
        """
        Initializes serial port, loads images, and starts TCP listener thread if possible.
        """
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
            from embodiment.EmbodimentExerciseGrasp import EmbodimentExerciseGrasp
            self.embodiment_exercise = EmbodimentExerciseGrasp(
                self.config,
                enable_logging=True,
                log_name_base=self.file_base_name,
                is_eeg_version=True,
                tcp_client=self.tcp_client,
                serial_comm=self.serial_comm,
                received_data_queue=self.received_data_queue,
                stop_listener_event=self.stop_listener_event
            )
        else:
            print("Warning: TCP connection failed. Proceeding without TCP data reception.")
            from embodiment.EmbodimentExerciseGrasp import EmbodimentExerciseGrasp
            self.embodiment_exercise = EmbodimentExerciseGrasp(
                self.config,
                enable_logging=True,
                log_name_base=self.file_base_name,
                is_eeg_version=False,
                tcp_client=None,
                serial_comm=self.serial_comm,
                received_data_queue=None,
                stop_listener_event=None
            )

    def _show_intro_screen(self):
        """
        Displays the experiment introduction screen, waiting for key press or timeout.
        """
        intro_text = "Welcome to the Motor Imagery Experiment!\n(EEG Training Version with Grasp Embodiment)\n\nPlease focus on the stimulus presented.\n\n"
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
        self._drain_server_queue()

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
                self._handle_trial_feedback(block_num, trial_index, global_trial_num, presented_condition)

        self.serial_comm.send_trigger(self.config.TRIGGER_BLOCK_END)
        self._show_block_break_screen(block_num)

    def _handle_trial_feedback(self, block_num, trial_in_block, global_trial_num, condition):
        """
        Handles feedback after each trial: logs data, displays ERD feedback, and manages breaks.
        """
        server_feedback = self._get_server_feedback()
        erd_value = self._extract_erd_value(server_feedback)
        erd_db_value = self._extract_erd_db_value(server_feedback)

        # CSV data logging removed - ERD data is logged separately

        self.erd_history.append(erd_value)
        print(f"Trial {global_trial_num}; Condition: {condition}; ERD%: {erd_value}; ERD dB: {erd_db_value}")
        # Log ERD values to dedicated logger
        self.erd_logger.log_erd(global_trial_num, condition, erd_value, erd_db_value)
        
        if condition == "sixth":
            if erd_value < 0:
                fc.execute_finger(100)
        if condition != self.config.BLANK_CONDITION_NAME:
            self.display.display_erd_feedback_bar(erd_value, duration_ms=self.config.ERD_FEEDBACK_DURATION_MS)
        self.serial_comm.send_trigger(self.config.TRIGGER_SHORT_BREAK_ONSET)
        self.display.display_blank_screen(self.config.SHORT_BREAK_DURATION_MS)

    def _get_server_feedback(self):
        """
        Retrieves the latest feedback from the TCP server (if available).
        """
        if not self.tcp_client.socket:
            return {}
        try:
            raw = self.received_data_queue.get_nowait()
            parsed = json.loads(raw) if raw else {}
            return parsed
        except queue.Empty:
            return {}
        except json.JSONDecodeError as e:
            print(f"Warning: Received non-JSON feedback. Raw data: {repr(raw)}")
            print(f"JSON decode error: {e}")
            print(f"Raw data length: {len(raw) if raw else 0}")
            return {}

    def _extract_erd_value(self, feedback):
        """
        Extracts the ERD value from the server feedback dictionary.
        Returns 0.0 if not present or invalid.
        """
        print(f"Received feedback from TCP connection: {feedback}")
        try:
            erd = float(feedback.get("erd_percent", 0.0))
            return erd
        except (ValueError, TypeError):
            print(f"Invalid ERD value: {feedback.get('erd_percent')}. Using 0.0.")
            return 0.0

    def _extract_erd_db_value(self, feedback):
        """
        Extracts the ERD dB value from the server feedback dictionary.
        Returns None if not present or invalid.
        """
        try:
            db_value = float(feedback.get("erd_db", 0.0))
            return db_value
        except (ValueError, TypeError):
            print(f"Invalid ERD dB value: {feedback.get('erd_db')}. Using 0.0.")
            return 0.0

    def _drain_server_queue(self):
        """
        Empties the received data queue, keeping only the latest server response.
        """
        latest_response = ""
        while not self.received_data_queue.empty():
            latest_response = self.received_data_queue.get_nowait()
        if latest_response:
            print(f"Latest server response: {latest_response}")

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

        # CSV data saving removed - ERD data and exercise logs are saved separately

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
        # === NEW GRASP EMBODIMENT EXERCISE PHASE ===
        # Run pre-experiment grasp embodiment exercise
        self.embodiment_exercise.run()

        for block_num in range(1, self.config.NUM_BLOCKS + 1):
            self._run_block(block_num)

        self._end_experiment()


# --- Main Experiment Loop ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EEG training session with grasp embodiment")
    parser.add_argument("--p", required=True, type=int, help="Participant number")
    parser.add_argument("--w", required=True, type=int, help="Week number")
    parser.add_argument("--test", action="store_true", help="Enable test mode for embodiment exercise (all imagery successful)")
    args = parser.parse_args()

    file_base = f"P{args.p}_w{args.w}_eeg"
    # Validate trial configuration before running
    config = ExperimentConfig()
    # Set test mode if requested
    if args.test:
        config.TEST_MODE_EMBODIMENT = True
        print("Test mode enabled: All embodiment imagery will be successful")
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
        experiment = Experiment(file_base, config)
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
            print("TRAINING EXPERIMENT WITH GRASP EMBODIMENT ENDED")
            print("="*50)
            try:
                pygame.quit()
            except:
                pass  # Pygame might already be quit
            sys.exit(0)
