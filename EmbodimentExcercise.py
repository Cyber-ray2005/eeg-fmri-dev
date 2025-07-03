
from pygame_display import PygameDisplay
from logger import TextLogger
import pygame
import random

class EmbodimentExercise:
    def __init__(self, config):
        self.config = config
        # Initialize the logger to log which character is displayed
        self.logger = TextLogger(
            log_dir="exercise_logs", 
            filename="embodiment_log.txt",
            timestamp_format="%Y-%m-%d %H:%M:%S"
        )
        # Initialize the display
        self.display = PygameDisplay(config)

    def run(self):
        """Starts and manages the embodiment exercise."""
        self.logger.log("Exercise started.")
        
        # 1. Display initial instructions
        self.display.display_message_screen(
            "Use your supernumerary robotic thumb to write each of the following characters on sand.\n\n Press any key to continue.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
        # 2. Loop through each character
        characters_to_write = random.sample(self.config.CHARACTERS_TO_WRITE, self.config.NUMBER_OF_CHARACTERS_TO_WRITE)
        for char in characters_to_write:
            # Log the character being displayed
            self.logger.log(f"Displaying character: {char}")
            
            # Display the character on screen and wait for a key press
            self.display.display_message_screen(
                char,
                wait_for_key=True,
                font=self.display.FONT_LARGE
            )
            pygame.time.wait(200) # Small delay to prevent accidental double-presses

        # 3. Display end message
        self.logger.log("Exercise finished.")
        self.display.display_message_screen(
            "Thank you for completing the exercise! \n\n Press any key to continue.",
            wait_for_key=True,
            font=self.display.FONT_LARGE
        )
        
