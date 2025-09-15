import os
import csv
import time
from typing import Optional

# --- logger.py: Data and Event Logging Utilities ---

class TrialDataLogger:
    """
    Collects and saves structured trial-by-trial data to CSV files.
    Configurable fieldnames and filenames. Used for experiment data logging.
    """
    def __init__(self, config):
        self.config = config
        self.all_trial_data = []

    def add_trial_data(self, data):
        self.all_trial_data.append(data)

    def save_data(self, participant_id):
        if not self.all_trial_data:
            print("No trial data to save.")
            return None

        # Get folder and filename format from config
        data_folder = self.config.get("data_folder", "data")
        filename_template = self.config.get(
            "filename_template",
            "{participant_id}_motor_imagery_data_{timestamp}.csv"
        )

        # Prepare directory
        os.makedirs(data_folder, exist_ok=True)

        # Generate timestamp and filename
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        filename = filename_template.format(participant_id=participant_id, timestamp=timestamp_str)
        filepath = os.path.join(data_folder, filename)

        # Write CSV
        try:
            fieldnames = self.config.get(
                "fieldnames",
                ["participant_id", "block", "trial_in_block", "global_trial_num", "condition", "category", "timestamp"]
            )
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.all_trial_data)
            print(f"Data saved to {filepath}")
            return filepath
        except IOError as e:
            print(f"Error: Could not save data to {filepath}. Error: {e}")
            return None



class TextLogger:
    """
    A simple class to log unstructured text messages to a file.

    This logger appends messages as new lines to a specified log file.
    The filename automatically includes a timestamp to ensure uniqueness per session.
    It can also be configured to prepend a timestamp to each message.

    Args:
        log_dir (str): The directory where the log file will be stored.
                       Defaults to "logs".
        filename (str): The base name for the log file (e.g., "app.log").
                        A timestamp will be inserted before the extension.
                        Defaults to "log.txt".
        timestamp_format (str, optional): The format for the timestamp inside the log,
                                          using standard `time.strftime` directives.
                                          If None, no timestamp is added to messages.
                                          Example: "%Y-%m-%d %H:%M:%S"
    """
    def __init__(self, log_dir: str = "logs", filename: str = "log.txt", timestamp_format: Optional[str] = None):
        # Create the log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Generate a timestamp string for the filename
        file_timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Split the original filename into its name and extension
        name, ext = os.path.splitext(filename)
        
        # Create the new filename with the timestamp included
        timestamped_filename = f"{name}_{file_timestamp}{ext}"
        
        self.filepath: str = os.path.join(log_dir, timestamped_filename)
        self.timestamp_format: Optional[str] = timestamp_format
        
        print(f"Logger initialized. Logging to: {self.filepath}")

    def log(self, message: str):
        """
        Writes a message to the log file.

        The message is appended to the file on a new line. If a timestamp
        format was specified during initialization, the current time will be
        prepended to the message.

        Args:
            message (str): The text message to log.
        """
        try:
            # 'a' mode ensures that we append to the file if it exists,
            # and create it if it doesn't.
            with open(self.filepath, 'a', encoding='utf-8') as f:
                log_entry = ""
                if self.timestamp_format:
                    message_timestamp = time.strftime(self.timestamp_format)
                    log_entry += f"[{message_timestamp}] "
                
                log_entry += message
                f.write(log_entry + '\n')
        except IOError as e:
            print(f"Error: Could not write to log file {self.filepath}. Details: {e}")


class ERDLogger:
    """
    A specialized logger for ERD values during training sessions.
    Logs trial number, condition, and calculated ERD values to timestamped CSV files.
    """
    def __init__(self, log_dir: str = "erd_logs"):
        # Create the log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Generate timestamp for filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"erd_values_{timestamp}.csv"
        self.filepath = os.path.join(log_dir, filename)
        
        # Initialize CSV with headers
        try:
            with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'trial_number', 'condition', 'erd_value'])
            print(f"ERD Logger initialized. Logging to: {self.filepath}")
        except IOError as e:
            print(f"Error: Could not initialize ERD log file {self.filepath}. Details: {e}")
            self.filepath = None

    def log_erd(self, trial_number: int, condition: str, erd_value: float):
        """
        Logs ERD data for a trial.
        
        Args:
            trial_number (int): The trial number
            condition (str): The condition/stimulus type
            erd_value (float): The calculated ERD value
        """
        if not self.filepath:
            return  # Skip if initialization failed
            
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self.filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, trial_number, condition, erd_value])
        except IOError as e:
            print(f"Error: Could not write ERD data to {self.filepath}. Details: {e}")

