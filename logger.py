import os
import csv
import time

class TrialDataLogger:
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
