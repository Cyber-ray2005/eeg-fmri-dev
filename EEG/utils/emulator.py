import time
import numpy as np
import mne

from utils.livestream_receiver import Marker

# --- emulator.py: EEG Data Emulation Utility ---

data_dir = "./data/rawdata/mit/"

class Emulator:
    """
    Simulates a live EEG data stream by reading from pre-recorded BrainVision files.
    Provides data chunks and event markers in the same format as a real EEG server.
    Used for development and testing without hardware.
    """
    def __init__(self, fileName="MIT33"):
        self.vhdr_file = f"{data_dir}{fileName}.vhdr"
        self.eeg_file = f"{data_dir}{fileName}.eeg"
        self.channel_count = 0
        self.sampling_frequency = 0
        self.sampling_interval_us = 0
        self.channel_names = []
        self.latency = 0.0016
        self.chunk_size = None
        self.current_index = 0
        self.raw_data = None
        self.buffer_size = None
        self.info = None

    def initialize_connection(self):
        self.raw_data = mne.io.read_raw_brainvision(self.vhdr_file, preload=True)
        self.sampling_frequency = int(self.raw_data.info["sfreq"])
        self.sampling_interval_us = (1 / self.sampling_frequency) * 1e6
        self.chunk_size = int(self.sampling_frequency / 50)
        self.buffer_size = int(self.sampling_frequency * 2)
        self.channel_names = self.raw_data.ch_names
        self.channel_count = len(self.channel_names)
        self.info = mne.create_info(
            ch_names=self.channel_names,
            sfreq=self.sampling_frequency,
            ch_types="eeg"
        )
        print(f"Running EEG Emulator with {self.channel_count} channels at {self.sampling_frequency} Hz")
        print(f"Chunk size is set to: {self.chunk_size} per channel.")
        return self.sampling_frequency, self.channel_names, self.channel_count,  np.zeros((self.channel_count,0))

    def get_data(self):
        """
        Gets a chunk of data and converts any markers in that chunk
        into custom Marker objects.
        """
        time.sleep(self.latency)
        total_samples = self.raw_data.n_times

        chunk_start_sample = self.current_index
        chunk_end_sample = min(chunk_start_sample + self.chunk_size, total_samples)
        
        data_chunk = self.raw_data.get_data(start=chunk_start_sample, stop=chunk_end_sample)

        start_time_sec = chunk_start_sample / self.sampling_frequency
        end_time_sec = chunk_end_sample / self.sampling_frequency

        # This list will hold your custom Marker objects
        markers_in_chunk = []
        for ann in self.raw_data.annotations:
            if start_time_sec <= ann['onset'] < end_time_sec:
                # === CONVERSION LOGIC START ===
                
                # 1. Create an instance of your custom Marker class
                marker_obj = Marker()

                # 2. Calculate position relative to the start of the CHUNK
                marker_absolute_position = ann['onset'] * self.sampling_frequency
                marker_obj.position = int(marker_absolute_position - chunk_start_sample)

                # 3. Calculate duration in points (samples)
                marker_obj.points = int(ann['duration'] * self.sampling_frequency)

                # 4. Set channel (always -1 for MNE annotations)
                marker_obj.channel = -1

                # 5. Parse the description string to get type and description
                full_description = ann['description']
                if '/' in full_description:
                    parts = full_description.split('/', 1)
                    marker_obj.type = parts[0].strip()
                    marker_obj.description = parts[1].strip()
                else:
                    # If there's no slash, use a default type
                    marker_obj.type = "Event"
                    marker_obj.description = full_description
                
                markers_in_chunk.append(marker_obj)
                # print(f"Marker found: {marker_obj.type} at position {marker_absolute_position}, duration {marker_obj.points}, description: {marker_obj.description}")
                # === CONVERSION LOGIC END ===

        self.current_index = chunk_end_sample

        return data_chunk, markers_in_chunk

    def use_classification(self, prediction):
        if prediction == 0:
            print("Rest")
        elif prediction == 1:
            print("Flex")
        else:
            print("Extend")

    def disconnect(self):
        self.current_index = 0
        print("Disconnected from EEG emulator")