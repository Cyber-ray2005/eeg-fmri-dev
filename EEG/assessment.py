# Import necessary libraries for the experiment
import pygame          # For creating the GUI and handling user input
import random          # For randomizing trial conditions and timing variations
import time            # For timestamping and timing operations
import sys             # For system-level operations like exit
import os              # For environment variable access
import queue           # For potential future data queuing (currently unused)

# Import custom utility modules for experiment functionality
from utils.trial_generator import TrialGenerator              # Generates randomized trial sequences
from utils.pygame_display import PygameDisplay               # Handles all visual display operations
from utils.logger import TrialDataLogger                     # Logs experimental data to CSV files
from utils.serial_communication import SerialCommunication   # Sends EEG triggers via serial port
from utils.logger import TextLogger                          # Logs text-based experimental events
from dotenv import load_dotenv                               # Loads environment variables from .env file
import platform                                              # For cross-platform compatibility
import subprocess                                            # For system audio commands


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


# --- Configuration Class ---
class ExperimentConfig:
    """
    Configuration class that contains all experimental parameters and settings.
    This centralizes all configurable values for easy modification and maintenance.
    """
    def __init__(self):
        # === DISPLAY CONFIGURATION ===
        # Screen dimensions for the experiment window
        self.SCREEN_WIDTH = 1000
        self.SCREEN_HEIGHT = 700
        self.FULLSCREEN_MODE = False  # Set to True for fullscreen mode

        # === COLOR DEFINITIONS ===
        # RGB color tuples for various UI elements
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (150, 150, 150)
        self.RED = (255, 0, 0)
        self.BLUE = (0, 0, 255)
        self.RED = (255, 0, 0)  # Note: This is a duplicate, may need cleanup
        self.CIRCLE_COLOR = (200, 200, 200)

        # === TIMING CONFIGURATION (all in milliseconds) ===
        # Control whether intro waits for key press or auto-advances
        self.INTRO_WAIT_KEY_PRESS = True
        # Duration of intro screen if not waiting for key press
        self.INTRO_DURATION_MS = 5000
        # Initial calibration period at experiment start
        self.INITIAL_CALIBRATION_DURATION_MS = 3000
        # Duration of fixation cross before each trial stimulus
        self.FIXATION_IN_TRIAL_DURATION_MS = 3000
        # Duration that each stimulus image is displayed
        self.IMAGE_DISPLAY_DURATION_MS = 3000
        # Short break between individual trials
        self.SHORT_BREAK_DURATION_MS = 1500
        # Long break between experimental blocks (1 minute)
        self.LONG_BREAK_DURATION_MS = 60000

        # === TRIAL STRUCTURE CONFIGURATION ===
        # Number of sixth finger trials per block
        self.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK = 15
        # Total number of normal finger trials per block (distributed across 5 fingers)
        self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK = 15
        # Number of blank/rest trials per block
        self.NUM_BLANK_TRIALS_PER_BLOCK = 15
        # Number of normal fingers (thumb, index, middle, ring, pinky)
        self.NUM_NORMAL_FINGERS = 5
        # Trials per normal finger (calculated to distribute total evenly)
        self.NUM_EACH_NORMAL_FINGER_PER_BLOCK = self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK // self.NUM_NORMAL_FINGERS
        # Total trials per block (sum of all trial types)
        self.TRIALS_PER_BLOCK = (self.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK +
                                 self.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK +
                                 self.NUM_BLANK_TRIALS_PER_BLOCK)
        # Total number of experimental blocks
        self.NUM_BLOCKS = 3

        # === RANDOMIZATION CONSTRAINTS ===
        # Maximum number of consecutive trials of the same category (prevents patterns)
        self.MAX_CONSECUTIVE_CATEGORY_STREAK = 1

        # === STIMULUS IMAGE CONFIGURATION ===
        # Folder containing all stimulus images
        self.IMAGE_FOLDER = "images"
        # Image file names for different stimulus types
        self.SIXTH_FINGER_IMAGE_NAME = "Hand_SixthFinger_Highlighted.png"
        self.REST_FINGER_IMAGE_NAME = "Rest.png"
        self.SIXTH_FINGER_IMAGE_NAME_BLUE = "Hand_SixthFinger_Highlighted_Blue.png"
        
        # Mapping of finger types to their corresponding image files
        # Regular (red) highlighting for motor imagery trials
        # Blue highlighting for motor execution trials
        self.NORMAL_FINGER_IMAGE_MAP = {
            "thumb": "Hand_Index_Highlighted.png",      # Note: This seems to be incorrect mapping
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
        
        # List of all normal finger types used in the experiment
        self.NORMAL_FINGER_TYPES = ["thumb", "index", "middle", "ring", "pinky"]
        # Name for the blank/rest condition
        self.BLANK_CONDITION_NAME = "blank"

        # === TRIAL CATEGORIZATION ===
        # Category names used for streak control and trial balancing
        self.CATEGORY_SIXTH = "sixth_finger_cat"
        self.CATEGORY_NORMAL = "normal_finger_cat"
        self.CATEGORY_BLANK = "blank_cat"

        # === SERIAL COMMUNICATION CONFIGURATION ===
        # Serial port settings for EEG trigger transmission
        self.SERIAL_PORT = os.environ.get("COM_PORT", "COM4")  # Uses environment variable or default
        self.BAUD_RATE = 9600  # Standard baud rate for EEG systems

        # === EEG TRIGGER CODES ===
        # Define trigger values (bytes) sent to EEG system for event marking
        # Experiment control triggers
        self.TRIGGER_EXPERIMENT_START = 100
        self.TRIGGER_EXPERIMENT_END = 101
        self.TRIGGER_BLOCK_START = 11
        self.TRIGGER_BLOCK_END = 12
        self.TRIGGER_FIXATION_ONSET = 10
        
        # Motor imagery stimulus triggers (red highlighting)
        self.TRIGGER_SIXTH_FINGER_ONSET = 6
        self.TRIGGER_THUMB_ONSET = 1
        self.TRIGGER_INDEX_ONSET = 2
        self.TRIGGER_MIDDLE_ONSET = 3
        self.TRIGGER_RING_ONSET = 4
        self.TRIGGER_PINKY_ONSET = 5
        
        # Motor execution stimulus triggers (blue highlighting)
        self.TRIGGER_SIXTH_FINGER_ONSET_BLUE = 96
        self.TRIGGER_THUMB_ONSET_BLUE = 16
        self.TRIGGER_INDEX_ONSET_BLUE = 32
        self.TRIGGER_MIDDLE_ONSET_BLUE = 48
        self.TRIGGER_RING_ONSET_BLUE = 64
        self.TRIGGER_PINKY_ONSET_BLUE = 80
        
        # Other triggers
        self.TRIGGER_CONTROL_STIMULUS_ONSET = 7  # For blank/rest trials
        self.TRIGGER_SHORT_BREAK_ONSET = 20
        
        # === AUDIO FEEDBACK CONFIGURATION ===
        # Settings for beep sounds that indicate trial start
        self.BEEP_FREQUENCY = 1000  # Frequency in Hz
        self.BEEP_DURATION_MS = 100  # Duration in milliseconds
        
        # === PARTICIPANT RESPONSE TRIGGERS ===
        # Triggers for yes/no questionnaire responses
        self.YES_TRIGGER = 11
        self.NO_TRIGGER = 12
        
        # === PLACEHOLDER FOR FUTURE FEATURES ===
        # List of words that could be used for writing tasks (currently unused)
        self.CHARACTERS_TO_WRITE=["Table",
        "Chair",
        "Door",
        "Window",
        "Book",
        "Pencil",
        "Street",
        "Cloud",
        "Water",
        "Tree",
        "Stone",
        "Box",
        "Glass"]
        # Number of characters to write in writing task (currently unused)
        self.NUMBER_OF_CHARACTERS_TO_WRITE = 5

        # === TRIGGER MAPPING ===
        # Dictionary mapping trial condition names to their corresponding EEG trigger codes
        # This allows easy lookup of trigger values during trial execution
        self.STIMULUS_TRIGGER_MAP = {
            # Motor imagery triggers (red highlighting)
            "sixth": self.TRIGGER_SIXTH_FINGER_ONSET,
            "thumb": self.TRIGGER_THUMB_ONSET,
            "index": self.TRIGGER_INDEX_ONSET,
            "middle": self.TRIGGER_MIDDLE_ONSET,
            "ring": self.TRIGGER_RING_ONSET,
            "pinky": self.TRIGGER_PINKY_ONSET,
            self.BLANK_CONDITION_NAME: self.TRIGGER_CONTROL_STIMULUS_ONSET,
            # Motor execution triggers (blue highlighting)
            "sixth_blue": self.TRIGGER_SIXTH_FINGER_ONSET_BLUE,
            "thumb_blue": self.TRIGGER_THUMB_ONSET_BLUE,
            "index_blue": self.TRIGGER_INDEX_ONSET_BLUE,
            "middle_blue": self.TRIGGER_MIDDLE_ONSET_BLUE,
            "ring_blue": self.TRIGGER_RING_ONSET_BLUE,
            "pinky_blue": self.TRIGGER_PINKY_ONSET_BLUE,
        }

# --- Main Experiment Class ---
class Experiment:
    """
    Main experiment class that orchestrates the entire motor imagery experiment.
    Handles experiment flow, trial execution, data logging, and hardware communication.
    """
    def __init__(self):
        """
        Initialize the experiment with all necessary components and configurations.
        Sets up display, communication, data logging, and generates participant ID.
        """
        # Load configuration settings
        self.config = ExperimentConfig()
        
        # Initialize display system for presenting stimuli and instructions
        self.display = PygameDisplay(self.config)
        
        # Initialize serial communication for EEG trigger transmission
        self.serial_comm = SerialCommunication(self.config.SERIAL_PORT, self.config.BAUD_RATE)
        
        # Initialize trial generator for creating randomized trial sequences
        self.trial_generator = TrialGenerator(self.config)
        
        # Initialize data logger for saving experimental data to CSV files
        self.data_logger = TrialDataLogger({
            "data_folder": "experiment_logs",
            "filename_template": "{participant_id}_session_log_{timestamp}.csv",
            "fieldnames": ["participant_id", "block", "trial_num", "condition", "response_time", "timestamp"]
        })
        
        # Initialize text logger for logging experimental events
        self.logger = TextLogger()
        
        # Generate unique participant ID (3-digit random number with 'P' prefix)
        self.participant_id = "P" + str(random.randint(100, 999))
        
        # Initialize placeholder for future features
        self.er_data_queue = queue.Queue()  # For potential future ER data reception
        self.tcp_client = None  # Placeholder for TCP client communication

    def _close_all_connections(self):
        """
        Safely close all hardware connections and communication channels.
        Called during experiment cleanup to prevent resource leaks.
        """
        # Close serial communication port
        self.serial_comm.close()
        # Future: Close TCP client if implemented
        # if self.tcp_client:
        #     self.tcp_client.close()
    
    def run_motor_execution_trial(self, trial_condition):
        """
        Execute a single motor execution trial where participant physically moves their finger.
        
        Motor execution trials use blue-highlighted stimuli and require actual finger movement
        rather than just motor imagery. These trials help establish baseline motor patterns.
        
        Args:
            trial_condition (str): The finger condition to present (e.g., 'thumb', 'index', 'sixth')
        """
        # Log trial information for debugging and record-keeping
        print(f"Motor Execution Trial, Condition: {trial_condition} "
              f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")
        
        self.logger.log(f"Motor Execution Trial, Condition: {trial_condition} "
                        f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")
        
        # Display fixation cross to prepare participant for stimulus
        # Send EEG trigger to mark fixation onset
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        # Display fixation with slight timing variation to prevent anticipation
        fixation_duration = random.choice([
            self.config.FIXATION_IN_TRIAL_DURATION_MS + 500, 
            self.config.FIXATION_IN_TRIAL_DURATION_MS - 500
        ])
        self.display.display_fixation_cross(fixation_duration)
        
        # Play beep sound to indicate trial start
        cross_platform_beep(self.config.BEEP_FREQUENCY, self.config.BEEP_DURATION_MS)
        
        # Get the appropriate trigger code for blue (motor execution) version
        stimulus_trigger_code = self.config.STIMULUS_TRIGGER_MAP.get(trial_condition + "_blue")
        
        # Display the stimulus if trigger code exists
        if stimulus_trigger_code is not None:
            # Get the blue-highlighted version of the stimulus image
            current_image_surface = self.display.scaled_images[trial_condition + "_blue"]
            # Send EEG trigger to mark stimulus onset
            self.serial_comm.send_trigger(stimulus_trigger_code)
            # Display the stimulus image with specified duration and cropping
            self.display.display_image_stimulus(
                current_image_surface, 
                self.config.IMAGE_DISPLAY_DURATION_MS, 
                (0, 0, current_image_surface.get_width(), current_image_surface.get_height() * 0.75)
            )


    def run_trial(self, trial_number_global, trial_condition):
        """
        Execute a single motor imagery trial where participant imagines finger movement.
        
        Motor imagery trials use red-highlighted stimuli and require participants to
        mentally simulate finger movements without actual physical movement.
        
        Args:
            trial_number_global (int): Global trial number across all blocks
            trial_condition (str): The condition to present ('thumb', 'index', 'sixth', 'blank', etc.)
            
        Returns:
            str: The trial condition that was presented
        """
        # Log trial information for debugging and record-keeping
        print(f"Global Trial: {trial_number_global}, Condition: {trial_condition} "
              f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")
        self.logger.log(f"Global Trial: {trial_number_global}, Condition: {trial_condition} "
                        f"(Category: {self.trial_generator.get_condition_category(trial_condition)})")
        
        # === FIXATION PHASE ===
        # Display fixation cross to prepare participant for stimulus
        self.serial_comm.send_trigger(self.config.TRIGGER_FIXATION_ONSET)
        # Add slight timing variation to prevent anticipation effects
        fixation_duration = random.choice([
            self.config.FIXATION_IN_TRIAL_DURATION_MS + 500, 
            self.config.FIXATION_IN_TRIAL_DURATION_MS - 500
        ])
        self.display.display_fixation_cross(fixation_duration)

        # Play audio cue to indicate trial start
        cross_platform_beep(self.config.BEEP_FREQUENCY, self.config.BEEP_DURATION_MS)

        # === STIMULUS PHASE ===
        # Get the appropriate EEG trigger code for this condition
        stimulus_trigger_code = self.config.STIMULUS_TRIGGER_MAP.get(trial_condition)

        # Handle different trial types
        if trial_condition == self.config.BLANK_CONDITION_NAME:
            # BLANK/REST TRIAL: Display "REST" text instead of finger image
            self.serial_comm.send_trigger(stimulus_trigger_code)
            self.display.display_message_screen(
                "REST", 
                duration_ms=self.config.IMAGE_DISPLAY_DURATION_MS, 
                font=self.display.FONT_LARGE, 
                bg_color=self.config.GRAY
            )
        elif trial_condition in self.display.scaled_images:
            # FINGER IMAGERY TRIAL: Display finger image stimulus
            if stimulus_trigger_code is not None:
                # Get the stimulus image for this condition
                current_image_surface = self.display.scaled_images[trial_condition]
                # Send EEG trigger to mark stimulus onset
                self.serial_comm.send_trigger(stimulus_trigger_code)
                # Display the stimulus with cropping to show 75% of height
                self.display.display_image_stimulus(
                    current_image_surface, 
                    self.config.IMAGE_DISPLAY_DURATION_MS, 
                    (0, 0, current_image_surface.get_width(), current_image_surface.get_height() * 0.75)
                )
            else:
                # Warning: stimulus exists but no trigger defined
                print(f"Warning: No trigger defined for image condition '{trial_condition}'. Stimulus shown without trigger.")
                current_image_surface = self.display.scaled_images[trial_condition]
                self.display.display_image_stimulus(
                    current_image_surface, 
                    self.config.IMAGE_DISPLAY_DURATION_MS, 
                    (0, 0, current_image_surface.get_width(), current_image_surface.get_height() * 0.75)
                )
        else:
            # ERROR: Unknown trial condition
            print(f"Error: Unknown trial condition or image key '{trial_condition}'.")
            self.display.display_message_screen(
                f"Error: Missing stimulus for {trial_condition}", 
                2000, 
                font=self.display.FONT_SMALL, 
                bg_color=self.config.RED
            )

        # === PERIODIC QUESTIONNAIRE ===
        # Every 5th trial, ask participant about motor imagery performance
        if trial_number_global % 5 == 0:
            yes = self.display.ask_yes_no_question("Did you perform motor imagery?")
            # Send appropriate trigger based on response
            if yes:
                self.serial_comm.send_trigger(self.config.YES_TRIGGER)
            else:
                self.serial_comm.send_trigger(self.config.NO_TRIGGER)
            # Log the response for analysis
            self.logger.log(f"Participant response: {'Yes' if yes else 'No'} for trial {trial_number_global}")
                        
        return trial_condition

    def run_experiment(self):
        """
        Main experiment execution method that orchestrates the entire experimental session.
        
        The experiment consists of:
        1. Initialization and setup
        2. Motor execution trials (actual finger movements)
        3. Motor imagery trials (imagined finger movements) across multiple blocks
        4. Data saving and cleanup
        """
        # === INITIALIZATION PHASE ===
        # Initialize hardware connections and load stimulus images
        self.serial_comm.initialize()
        self.display.load_stimulus_images()
        
        # === INTRODUCTION SCREEN ===
        # Display welcome message and wait for participant to begin
        intro_text = "Welcome to the Motor Imagery Experiment!\n\n"
        if self.config.INTRO_WAIT_KEY_PRESS:
            intro_text += "Press any key to begin."
            self.display.display_message_screen(intro_text, wait_for_key=True, font=self.display.FONT_LARGE)
        else:
            intro_text += f"The experiment will begin in {self.config.INTRO_DURATION_MS/1000:.0f} seconds."
            self.display.display_message_screen(intro_text, duration_ms=self.config.INTRO_DURATION_MS, font=self.display.FONT_LARGE)
        
        # Mark experiment start in EEG data
        self.serial_comm.send_trigger(self.config.TRIGGER_EXPERIMENT_START)
        
        # === MOTOR EXECUTION PHASE ===
        # Brief motor execution trials to establish baseline motor patterns
        self.display.display_message_screen("Motor Execution Trials", duration_ms=2000, font=self.display.FONT_LARGE)
        
        # Display instructions for motor execution phase
        instruction = ("In the next slides, you will see a hand illustration \n"
                      "with one of the fingers highlighted in #BLUE:BLUE#.\n\n"
                      "Flex and extend the encircled finger. \n\n"
                      "Press any key to continue.")
        self.display.display_message_screen(instruction, wait_for_key=True, font=self.display.FONT_LARGE)
        
        # Create randomized list of motor execution trials (all finger types including sixth)
        motor_execution_trails = self.config.NORMAL_FINGER_TYPES + ["sixth"]
        random.shuffle(motor_execution_trails)
        
        # Execute each motor execution trial
        for trial_index, condition in enumerate(motor_execution_trails, 1):
            presented_condition = self.run_motor_execution_trial(condition)
            # Short break between motor execution trials
            self.display.display_blank_screen(self.config.SHORT_BREAK_DURATION_MS)

        # === MOTOR IMAGERY PHASE ===
        # Main experimental phase with multiple blocks of motor imagery trials
        self.display.display_message_screen("Motor Imagery Trials", duration_ms=2000, font=self.display.FONT_LARGE)
        
        # Display instructions for motor imagery phase
        instruction = ("In the next slides, you will see a hand illustration \n"
                      "with one of the fingers encircled in #RED:RED#. \n\n"
                      "Imagine, kinesthetically, flexing and extending the encircled finger. \n"
                      "Please try to avoid any movement throughout the exercise. \n\n"
                      "Press any key to continue.")
        self.display.display_message_screen(instruction, wait_for_key=True, font=self.display.FONT_LARGE)
        
        # === MAIN EXPERIMENTAL BLOCKS ===
        # Execute the specified number of experimental blocks
        for block_num in range(1, self.config.NUM_BLOCKS + 1):
            # Mark block start in EEG data
            self.serial_comm.send_trigger(self.config.TRIGGER_BLOCK_START)
            
            # Generate randomized trial sequence for this block
            self.display.display_loading_screen(
                "Generating trials for Block...", 
                font=self.display.FONT_MEDIUM, 
                bg_color=self.config.BLACK, 
                text_color=self.config.WHITE
            )
            current_block_trial_conditions = self.trial_generator.generate_trial_list_for_block()

            # === TRIAL VALIDATION ===
            # Verify that the generated trial list has the correct number of trials
            if len(current_block_trial_conditions) != self.config.TRIALS_PER_BLOCK:
                print(f"CRITICAL Error: Trial list length mismatch.")
                self.display.display_message_screen(
                    "CRITICAL Error: Trial configuration issue.", 
                    5000, 
                    bg_color=self.config.RED
                )
                self._close_all_connections()
                self.display.quit_pygame_and_exit()

            # === EXECUTE TRIALS IN CURRENT BLOCK ===
            # Run each trial in the current block
            for trial_num_in_block, condition in enumerate(current_block_trial_conditions, 1):
                # Check for quit events (window close or escape key)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT: 
                        self._close_all_connections()
                        self.display.quit_pygame_and_exit()
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: 
                        self._close_all_connections()
                        self.display.quit_pygame_and_exit()

                # Calculate global trial number across all blocks
                trial_global_num = (block_num - 1) * self.config.TRIALS_PER_BLOCK + trial_num_in_block
                
                # Execute the trial and get the presented condition
                presented_condition = self.run_trial(trial_global_num, condition)

                # === DATA LOGGING ===
                # Create trial data record with all relevant information
                trial_data = {
                    "participant_id": self.participant_id,
                    "block": block_num,
                    "trial_in_block": trial_num_in_block,
                    "global_trial_num": trial_global_num,
                    "condition": presented_condition,
                    "category": self.trial_generator.get_condition_category(presented_condition),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                # Add trial data to logger for later saving
                self.data_logger.add_trial_data(trial_data)

                # Inter-trial interval (short break between trials)
                self.display.display_blank_screen(self.config.SHORT_BREAK_DURATION_MS)
                
            # === INTER-BLOCK BREAK ===
            # Handle break between blocks or end-of-experiment messaging
            block_end_server_response = ""  # Placeholder for future server integration

            if block_num < self.config.NUM_BLOCKS:
                # Long break between blocks (except after the last block)
                msg = f"End of Block {block_num}.\n\nTake a break."
                self.display.display_timer_with_message(msg, self.config.LONG_BREAK_DURATION_MS)
                msg = "Press any key to continue to the next block."
                self.display.display_message_screen(msg, wait_for_key=True, font=self.display.FONT_MEDIUM)
            else:
                # End of experiment message
                self.display.display_message_screen(
                    "All Blocks Completed!", 
                    duration_ms=3000, 
                    font=self.display.FONT_MEDIUM, 
                    server_response=block_end_server_response
                )

            
        # === EXPERIMENT COMPLETION ===
        # Mark experiment end in EEG data (commented out, likely for debugging)
        # self.serial_comm.send_trigger(self.config.TRIGGER_EXPERIMENT_END)
        
        # Display final thank you message
        self.display.display_message_screen(
            "Experiment Finished!\n\nThank you for your participation.", 
            duration_ms=5000, 
            wait_for_key=True, 
            font=self.display.FONT_LARGE
        )

        # === DATA SAVING ===
        # Save all collected experimental data to CSV file
        saved_file = self.data_logger.save_data(self.participant_id)
        if saved_file:
            # Success: Show file location to experimenter
            self.display.display_message_screen(
                f"Data saved to:\n{saved_file}", 
                duration_ms=4000, 
                font=self.display.FONT_SMALL
            )
        else:
            # Error: Alert experimenter that data was not saved
            self.display.display_message_screen(
                f"Error: Could not save data!", 
                duration_ms=3000, 
                font=self.display.FONT_SMALL, 
                bg_color=self.config.RED
            )

        # === CLEANUP ===
        # Close all hardware connections and exit gracefully
        self._close_all_connections()
        self.display.quit_pygame_and_exit()


# === MAIN EXECUTION BLOCK ===
if __name__ == "__main__":
    """
    Main execution block that validates configuration and starts the experiment.
    
    This block performs several validation checks before starting the experiment
    to ensure that trial counts are configured correctly and prevent runtime errors.
    """
    # Load environment variables from .env file (e.g., COM port settings)
    load_dotenv() 
    
    # Create configuration instance for validation
    config = ExperimentConfig()
    
    # === TRIAL COUNT VALIDATION ===
    # Calculate expected total trials based on individual trial type counts
    expected_total_trials = (config.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK +
                             (config.NUM_EACH_NORMAL_FINGER_PER_BLOCK * config.NUM_NORMAL_FINGERS) +
                             config.NUM_BLANK_TRIALS_PER_BLOCK)

    # Validate that calculated total matches configured total
    if expected_total_trials != config.TRIALS_PER_BLOCK:
        print(f"Error: Mismatch in total trial count. Expected: {expected_total_trials}, Got: {config.TRIALS_PER_BLOCK}")
        sys.exit()
        
    # Validate that normal finger trial distribution is correct
    if config.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK != config.NUM_EACH_NORMAL_FINGER_PER_BLOCK * config.NUM_NORMAL_FINGERS:
        print(f"Error: Mismatch in normal finger trial counts.")
        sys.exit()
    else:
        # === EXPERIMENT EXECUTION ===
        # Configuration is valid, start the experiment
        experiment = Experiment()
        try:
            # Run the main experiment
            experiment.run_experiment()
        except SystemExit:
            # Handle graceful exit (e.g., user pressed escape)
            print("Experiment exited.")
        except Exception as e:
            # Handle unexpected errors during experiment
            print(f"An unexpected error occurred during the experiment: {e}")
        finally:
            # === CLEANUP ===
            # Ensure all hardware connections are closed even if errors occur
            # This prevents resource leaks and hardware conflicts
            experiment._close_all_connections()
