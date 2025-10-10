
from utils.pygame_display import PygameDisplay
from utils.logger import TextLogger
from typing import Optional
import pygame
import random

class EmbodimentExercise:
    def __init__(self, config, enable_logging=True, log_name_base: Optional[str] = None):
        self.config = config
        self.enable_logging = enable_logging
        
        # Initialize the logger only if logging is enabled
        if self.enable_logging:
            filename = f"{log_name_base}.txt" if log_name_base else "embodiment_log.txt"
            self.logger = TextLogger(
                log_dir="exercise_logs", 
                filename=filename,
                timestamp_format="%Y-%m-%d %H:%M:%S",
                add_timestamp_to_filename=(log_name_base is None)
            )
        else:
            self.logger = None
            print("Embodiment Exercise: Logging disabled (no files will be created)")
        
        # Initialize the display
        self.display = PygameDisplay(config)

    def run(self):
        """Starts and manages the embodiment exercise."""
        if self.logger:
            self.logger.log("Exercise started.")
        
        # 1. Display initial instructions
        self.display.display_message_screen(
            "Use your supernumerary robotic thumb to write\neach of the following characters on the board presented.\n\nPress any key to continue.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
        # 2. Loop through each character
        characters_to_write = random.sample(self.config.CHARACTERS_TO_WRITE, self.config.NUMBER_OF_CHARACTERS_TO_WRITE)
        for char in characters_to_write:
            # Log the character being displayed (only if logging is enabled)
            if self.logger:
                self.logger.log(f"Displaying character: {char}")
            
            # Display the character on screen and wait for a key press
            self.display.display_message_screen(
                char,
                wait_for_key=True,
                font=self.display.FONT_LARGE
            )
            pygame.time.wait(200) # Small delay to prevent accidental double-presses

        # 3. Display end message
        if self.logger:
            self.logger.log("Exercise finished.")
        self.display.display_message_screen(
            "Thank you for completing the exercise! \n\n Press any key to continue.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
