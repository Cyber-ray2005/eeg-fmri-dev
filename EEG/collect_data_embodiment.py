import numpy as np
import time
import socket
import json
from collections import deque
import pandas as pd
from scipy.signal import butter, filtfilt
import mne
from colorama import Fore, Style
import argparse

from utils.livestream_receiver import LivestreamReceiver, Marker
from utils.emulator import Emulator

from ERDCalculator.ERDCalculator import ERDCalculator


# --- Configuration Class ---
class EEGConfig:
    """
    Holds all configuration parameters for EEG data collection, processing, and broadcasting.
    Modified to support new embodiment exercise triggers.
    """
    def __init__(self):
        # EEG Connection Parameters
        self.EEG_SERVER_IP = "169.254.1.147"
        self.EEG_SERVER_PORT = 51244
        self.COLLECT_FROM_EMULATOR = False  # If True, use Emulator instead of real EEG server

        # Signal Processing Parameters
        self.FOCUS_CHANNEL_NAMES = ["C3", "C1", "CP3", "CP1"]  # Motor cortex channels (name-based)
        # Updated focus markers to include new embodiment exercise triggers
        self.FOCUS_MARKERS = ['S  1', 'S  2', 'S  3', 'S  4', 'S  5', 'S  6', 'S  7', 'S 20', 'S 21', 'S 22', 'S 23']
        self.BAD_CHANNELS = ['FT9', 'TP9', 'FT10', 'TP10']  # Channels to exclude from analysis
        self.LOW_CUT = 8.0 # Hz (alpha band)
        self.HIGH_CUT = 30.0 # Hz (alpha band)
        self.FILTER_ORDER = 5

        # Epoching Parameters
        self.SECONDS_BEFORE_MARKER = 2.0
        self.SECONDS_AFTER_MARKER = 2.0

        # Buffer and Streaming Parameters
        self.MAX_STREAM_DURATION_SECONDS = 120

        # Broadcasting Configuration
        self.ENABLE_BROADCASTING = True
        self.BROADCAST_IP = "127.0.0.1"
        self.BROADCAST_PORT = 50000
        self.BROADCAST_SERVER_TIMEOUT = 0.1 # Timeout for accept()

# --- EEG Receiver Class ---
class EEGReceiver:
    """
    Handles connection to the EEG data source (real server or emulator),
    and provides methods to retrieve data and disconnect.
    """
    def __init__(self, config: EEGConfig):
        self.config = config
        self.receiver = None
        self.sampling_frequency = None
        self.channel_names = None
        self.channel_count = None

    def initialize(self):
        """
        Initializes the connection to the EEG server or emulator.
        Returns True if successful, False otherwise.
        """
        if self.config.COLLECT_FROM_EMULATOR:
            self.receiver = Emulator()
        else:
            print("Initializing LivestreamReceiver...")
            self.receiver = LivestreamReceiver(address=self.config.EEG_SERVER_IP, port=self.config.EEG_SERVER_PORT, broadcast=False)

        print(f"Attempting to connect to EEG server...")
        try:
            sfreq, ch_names, n_channels, initial_data_buffer = self.receiver.initialize_connection()
            self.sampling_frequency = sfreq
            self.channel_names = ch_names
            self.channel_count = n_channels

            print("\nConnection successful and initialized!")
            print(f"Sampling Frequency: {self.sampling_frequency} Hz")
            print(f"Channel Names: {self.channel_names}")
            print(f"Number of Channels: {self.channel_count}")
            print("===================================\n")
            return True
        except ConnectionRefusedError:
            print(f"Connection refused. Ensure the EEG data provider is running at {self.config.EEG_SERVER_IP}:{self.config.EEG_SERVER_PORT}.")
            return False
        except Exception as e:
            print(f"An error occurred during EEG receiver initialization: {e}")
            return False

    def get_data(self):
        """
        Retrieves the next chunk of EEG data and any markers from the receiver.
        """
        return self.receiver.get_data()

    def disconnect(self):
        """
        Disconnects from the EEG data source if possible.
        """
        if hasattr(self.receiver, 'disconnect'):
            self.receiver.disconnect()

# --- Data Processor Class ---
class DataProcessor:
    """
    Handles signal processing, filtering, and ERD calculation for EEG epochs.
    """
    def __init__(self, config: EEGConfig, sampling_frequency, channel_count):
        self.config = config
        self.sampling_frequency = sampling_frequency
        self.channel_count = channel_count
        # Design bandpass filter
        self.b, self.a = butter(self.config.FILTER_ORDER,
                                [self.config.LOW_CUT, self.config.HIGH_CUT],
                                btype='band', fs=self.sampling_frequency)
        
        # Calculate number of samples before and after marker for epoching
        self.samples_before_marker = int(self.config.SECONDS_BEFORE_MARKER * self.sampling_frequency)
        self.samples_after_marker = int(self.config.SECONDS_AFTER_MARKER * self.sampling_frequency)
        self.epoch_total_samples = self.samples_before_marker + 1 + self.samples_after_marker

    def calculate_erd(self, epoch_data):
        """
        Calculates ERD% for a given epoch of EEG data.
        Returns the average ERD% across focus channels, or 0 if invalid.
        """
        if epoch_data.shape != (self.channel_count, self.epoch_total_samples) or np.isnan(epoch_data).all() or np.all(np.isnan(epoch_data), axis=1).any():
            print(f"⚠️ Epoch data invalid for ERD calculation. Shape: {epoch_data.shape}, NaNs: {np.isnan(epoch_data).all()}")
            return None

        filtered_epoch = filtfilt(self.b, self.a, epoch_data, axis=1)

        pre = filtered_epoch[:, :self.samples_before_marker]
        post = filtered_epoch[:, self.samples_before_marker + 1:]

        pre_power = pre ** 2
        post_power = post ** 2

        # Handle potential division by zero by using np.nanmean and filtering
        R = np.nanmean(pre_power, axis=1)
        A = np.nanmean(post_power, axis=1)

        erd_percent = np.zeros_like(R, dtype=float)
        # Only calculate for channels where R (reference power) is not zero
        non_zero_R_indices = R != 0
        erd_percent[non_zero_R_indices] = ((A[non_zero_R_indices] - R[non_zero_R_indices]) / R[non_zero_R_indices]) * 100
        # For channels where R is zero, set ERD to NaN (or 0, depending on desired behavior)
        erd_percent[R == 0] = np.nan

        erd_percent_focus = erd_percent[self.config.FOCUS_CHANNELS]
        print(Fore.RED + f"       ERD% per focus channel: {erd_percent_focus}" + Style.RESET_ALL)
        
        # Return the average ERD across focus channels if values exist, otherwise return 0
        if np.any(~np.isnan(erd_percent_focus)):
            erd_percent_focus_mean = np.nanmean(erd_percent_focus)
            print(Fore.GREEN + f"       Average ERD% across focus channels: {erd_percent_focus_mean:.2f}%" + Style.RESET_ALL)
            return abs(float(erd_percent_focus_mean))
        else:
            return 0.0  # Return 0 if all values are NaN or the list is empty

# --- ERD Broadcaster Class ---
class ERDBroadcaster:
    """
    Sets up a TCP server to broadcast ERD results to a client (e.g., for real-time feedback).
    """
    def __init__(self, config: EEGConfig):
        self.config = config
        self.server_socket = None
        self.client_connection = None

    def initialize(self):
        """
        Initializes the TCP server for broadcasting ERD data.
        """
        if not self.config.ENABLE_BROADCASTING:
            print("Broadcasting is disabled.")
            return

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.config.BROADCAST_IP, self.config.BROADCAST_PORT))
            self.server_socket.listen(1)
            self.server_socket.settimeout(self.config.BROADCAST_SERVER_TIMEOUT)
            print(f"Broadcasting server listening on {self.config.BROADCAST_IP}:{self.config.BROADCAST_PORT}...")
        except Exception as e:
            print(f"Error initializing broadcasting server: {e}")
            self.server_socket = None

    def accept_client(self):
        """
        Accepts a client connection if one is waiting.
        """
        if self.server_socket and self.client_connection is None:
            try:
                conn, addr = self.server_socket.accept()
                self.client_connection = conn
                print(f"Accepted broadcasting connection from {addr}")
            except socket.timeout:
                pass # No client tried to connect in this interval
            except Exception as e:
                print(f"Error accepting client connection: {e}")

    def broadcast_data(self, data):
        """
        Sends ERD data to the connected client as a JSON string.
        """
        if self.client_connection:
            try:
                message = json.dumps(data) + "\n"
                self.client_connection.sendall(message.encode('utf-8'))
                # print(f"Successfully broadcasted: {len(message)} bytes")
            except BrokenPipeError:
                print("Client disconnected, resetting connection.")
                self.client_connection.close()
                self.client_connection = None
            except Exception as e:
                print(f"Error broadcasting data: {e}")
                # Print the data that failed to broadcast for debugging
                print(f"Failed data: {repr(data)}")
        else:
            # print("Broadcasting not enabled or no client connected.") # Muted for less console spam
            pass

    def close(self):
        """
        Closes the client and server sockets.
        """
        if self.client_connection:
            print("Closing client broadcasting connection.")
            self.client_connection.close()
        if self.server_socket:
            print("Closing broadcasting server socket.")
            self.server_socket.close()
        self.client_connection = None
        self.server_socket = None

# --- Data Saver Class ---
class DataSaver:
    """
    Handles saving EEG data and markers to disk, and creating MNE Raw objects for further analysis.
    """
    def __init__(self, config: EEGConfig):
        self.config = config

    def save_eeg_data(self, all_eeg_data, filename=None):
        """
        Saves all collected EEG data to a .npy file with timestamp.
        Returns the concatenated EEG data array.
        """
        if filename is None:
            import time
            import os
            os.makedirs("eeg_data", exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"./eeg_data/collected_eeg_data_{timestamp}.npy"
        if all_eeg_data:
            final_eeg_data = np.concatenate(all_eeg_data, axis=1)
            print(f"\nTotal collected EEG data shape: {final_eeg_data.shape}")
            np.save(filename, final_eeg_data)
            print(f"Data saved to {filename}")
            return final_eeg_data
        else:
            print("\nNo EEG data was collected to save.")
            return None

    def save_markers(self, all_markers, filename=None):
        """
        Saves all collected markers to a CSV file with timestamp.
        """
        if filename is None:
            import time
            import os
            os.makedirs("eeg_data", exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"./eeg_data/collected_markers_{timestamp}.csv"
        if all_markers:
            markers_data = []
            for marker in all_markers:
                markers_data.append({
                    'description': marker.description,
                    'position': marker.position,
                    'channel': marker.channel
                })
            markers_df = pd.DataFrame(markers_data)
            markers_df.to_csv(filename, index=False)
            print(f"Markers saved to {filename}")
        else:
            print("No markers were collected to save.")

    def create_mne_raw(self, final_eeg_data, sampling_frequency, channel_names):
        """
        Creates an MNE Raw object from the EEG data for further analysis/visualization.
        """
        if final_eeg_data is not None and sampling_frequency and channel_names:
            ch_types = ['eeg'] * len(channel_names)
            info = mne.create_info(ch_names=channel_names, sfreq=sampling_frequency, ch_types=ch_types)
            raw_mne = mne.io.RawArray(final_eeg_data, info)
            raw_mne.set_montage("standard_1020", on_missing='warn')
            print("\nCreated MNE Raw object:")
            print(raw_mne)
            return raw_mne
        else:
            print("Cannot create MNE Raw object: Missing EEG data, sampling frequency, or channel names.")
            return None

# --- Main EEG Data Collector Class ---
class EEGDataCollector:
    """
    Orchestrates the entire EEG data collection, processing, and broadcasting pipeline.
    Modified to support new embodiment exercise triggers.
    """
    def __init__(self, file_base_name=None):
        self.config = EEGConfig()
        self.receiver = EEGReceiver(self.config)
        self.broadcaster = ERDBroadcaster(self.config)
        self.data_saver = DataSaver(self.config)
        self.data_processor = None # Initialized after connection to get sfreq, n_channels
        self.file_base_name = file_base_name

        self.all_eeg_data = []
        self.all_markers = []
        self.live_eeg_buffer = None
        self.buffer_write_idx = 0
        self.total_samples_streamed = 0
        self.pending_markers_to_process = deque()
        
        # Channel mapping for bad channel exclusion
        self.clean_channel_names = None
        self.clean_to_original_mapping = None

    def run(self):
        """
        Main loop for data collection, processing, and broadcasting.
        Handles buffer management, marker registration, and live ERD calculation.
        Modified to support new embodiment exercise triggers.
        """
        if not self.receiver.initialize():
            return # Exit if connection fails

        # Remove bad channels and create clean channel mapping
        self.clean_channel_names = [ch for ch in self.receiver.channel_names 
                                   if ch not in self.config.BAD_CHANNELS]
        
        # Create mapping from clean channels to original indices
        self.clean_to_original_mapping = {}
        clean_idx = 0
        for orig_idx, ch_name in enumerate(self.receiver.channel_names):
            if ch_name not in self.config.BAD_CHANNELS:
                self.clean_to_original_mapping[clean_idx] = orig_idx
                clean_idx += 1
        
        # Map focus channel names to clean channel indices (same as assessment classifier)
        focus_channels_clean = []
        for ch_name in self.config.FOCUS_CHANNEL_NAMES:
            if ch_name in self.clean_channel_names:
                clean_idx = self.clean_channel_names.index(ch_name)
                focus_channels_clean.append(clean_idx)
            else:
                print(f"Warning: Focus channel '{ch_name}' not found in clean channel list")
        
        # Store focus channels for later use
        self.config.FOCUS_CHANNELS = focus_channels_clean
        
        # self.data_processor = DataProcessor(self.config, self.receiver.sampling_frequency, self.receiver.channel_count)
        self.data_processor = ERDCalculator(
            self.receiver.sampling_frequency, 
            epoch_pre_stimulus_seconds=self.config.SECONDS_BEFORE_MARKER,
            epoch_post_stimulus_seconds=self.config.SECONDS_AFTER_MARKER,
            bandpass_high=self.config.HIGH_CUT,
            bandpass_low=self.config.LOW_CUT,
            channel_names=self.clean_channel_names,
            focus_channels_indices=focus_channels_clean,
            )
        self.broadcaster.initialize()

        # Calculate buffer size based on processing needs
        buffer_duration_seconds = max(10.0, (self.config.SECONDS_BEFORE_MARKER + self.config.SECONDS_AFTER_MARKER) * 1.5)
        buffer_samples = int(buffer_duration_seconds * self.receiver.sampling_frequency)
        self.live_eeg_buffer = np.full((self.receiver.channel_count, buffer_samples), np.nan)

        input("Press Enter to start data collection...")
        print("Starting data collection loop (Press Ctrl+C to stop)...")
        print("Monitoring for embodiment exercise triggers: S 20, S 21, S 22, S 23")

        start_time = time.time()
        try:
            # while (time.time() - start_time) < self.config.MAX_STREAM_DURATION_SECONDS:
            while True:
                self.broadcaster.accept_client() # Attempt to accept client connection

                data_chunk, markers = self.receiver.get_data()

                if data_chunk is not None and data_chunk.shape[1] > 0: # Ensure chunk is not empty
                    self.all_eeg_data.append(data_chunk)
                    num_samples_in_chunk = data_chunk.shape[1]
                    # Add new data to the circular buffer
                    start_idx = self.buffer_write_idx
                    end_idx = start_idx + num_samples_in_chunk
                    if end_idx <= buffer_samples:
                        self.live_eeg_buffer[:, start_idx:end_idx] = data_chunk
                    else: # Wraps around
                        part1_len = buffer_samples - start_idx
                        self.live_eeg_buffer[:, start_idx:buffer_samples] = data_chunk[:, :part1_len]
                        part2_len = num_samples_in_chunk - part1_len
                        self.live_eeg_buffer[:, :part2_len] = data_chunk[:, part1_len:]

                    self.buffer_write_idx = end_idx % buffer_samples
                    self.total_samples_streamed += num_samples_in_chunk

                    # Register incoming markers
                    if markers:
                        print(f"Received {len(markers)} markers in this chunk:")                        
                        
                        for marker_obj in markers:
                            # Marker position relative to the start of the entire stream
                            marker_stream_pos = self.total_samples_streamed - num_samples_in_chunk + marker_obj.position
                            markers[0].position = marker_stream_pos
                            self.all_markers.extend(markers)
                            if marker_obj.description in self.config.FOCUS_MARKERS:
                                self.pending_markers_to_process.append({
                                    'marker_obj': marker_obj,
                                    'stream_pos': marker_stream_pos,
                                    'description': marker_obj.description
                                })
                            print(f"  Registered Marker: '{marker_obj.description}' at stream sample {marker_stream_pos}")

                    # Process pending markers
                    self._process_pending_markers(buffer_samples)

                # Keep the loop responsive, avoid busy waiting
                time.sleep(0.001)

        except KeyboardInterrupt:
            print("\nData collection stopped by user (Ctrl+C).")
        except Exception as e:
            print(f"An unexpected error occurred during data collection: {e}")
        finally:
            self._cleanup()

    def _process_pending_markers(self, buffer_samples):
        """
        Checks if enough data is available in the buffer for each pending marker,
        extracts the corresponding epoch, and performs live ERD calculation and broadcasting.
        Modified to handle new embodiment exercise triggers.
        """
        processed_markers_this_iteration = []
        for i in range(len(self.pending_markers_to_process)):
            pending_marker = self.pending_markers_to_process[i]
            marker_stream_pos = pending_marker['stream_pos']

            oldest_sample_in_buffer_stream_pos = max(0, self.total_samples_streamed - buffer_samples)
            required_epoch_end_stream_pos = marker_stream_pos + self.data_processor.samples_after_marker

            # Check if enough data is in buffer to extract the full epoch
            if required_epoch_end_stream_pos < self.total_samples_streamed and \
               (marker_stream_pos - self.data_processor.samples_before_marker) >= oldest_sample_in_buffer_stream_pos:

                # Extract epoch data from the circular buffer
                epoch_start_stream_pos = marker_stream_pos - self.data_processor.samples_before_marker
                
                # Calculate relative index in the circular buffer
                # This needs careful handling for wrap-around.
                # The total_samples_streamed - buffer_samples represents the stream_pos of the first sample in the buffer
                

                #ADD SNIPPET
                offset_from_buffer_start = epoch_start_stream_pos - oldest_sample_in_buffer_stream_pos
                relative_epoch_start_in_buffer = (self.buffer_write_idx + int(offset_from_buffer_start)) % buffer_samples
                #END SNIPPET
                #relative_epoch_start_in_buffer = (epoch_start_stream_pos - oldest_sample_in_buffer_stream_pos + self.buffer_write_idx - self.total_samples_streamed + buffer_samples) % buffer_samples
                
                # Extract epoch data for all channels first
                full_epoch_data = np.full((self.receiver.channel_count, self.data_processor.epoch_total_samples), np.nan)

                if relative_epoch_start_in_buffer + self.data_processor.epoch_total_samples <= buffer_samples:
                    full_epoch_data = self.live_eeg_buffer[:, relative_epoch_start_in_buffer : relative_epoch_start_in_buffer + self.data_processor.epoch_total_samples]
                else: # Epoch wraps around the buffer end
                    part1_len = buffer_samples - relative_epoch_start_in_buffer
                    full_epoch_data[:, :part1_len] = self.live_eeg_buffer[:, relative_epoch_start_in_buffer : buffer_samples]
                    part2_len = self.data_processor.epoch_total_samples - part1_len
                    full_epoch_data[:, part1_len:] = self.live_eeg_buffer[:, :part2_len]
                
                # Remove bad channels from epoch data
                epoch_data = np.zeros((len(self.clean_channel_names), self.data_processor.epoch_total_samples))
                for clean_idx, orig_idx in self.clean_to_original_mapping.items():
                    epoch_data[clean_idx, :] = full_epoch_data[orig_idx, :]

                # Perform live calculations
                print(f"       Epoch extracted for '{pending_marker['description']}'. Shape: {epoch_data.shape}. Performing live calculations...")
                
                erd_results = self.data_processor.calculate_erd_moving_average(
                    epoch_data, 
                    window_size_samples=100,
                    return_mean=True, 
                    method='percentage'
                )

                # Also compute ERD using dB method
                erd_results_db = self.data_processor.calculate_erd_moving_average(
                    epoch_data,
                    window_size_samples=100,
                    return_mean=True,
                    method='db'
                )

                if erd_results is not None:
                    # Convert numpy types to Python types for JSON serialization
                    if isinstance(erd_results, tuple):
                        erd_mean, _ = erd_results
                        erd_data = erd_mean
                    else:
                        erd_data = float(erd_results) if hasattr(erd_results, 'item') else erd_results

                    # Prepare dB value similarly (default to None if unavailable)
                    erd_db_value = None
                    if erd_results_db is not None:
                        if isinstance(erd_results_db, tuple):
                            erd_db_mean, _ = erd_results_db
                            erd_db_value = erd_db_mean
                        else:
                            erd_db_value = float(erd_results_db) if hasattr(erd_results_db, 'item') else erd_results_db
                    
                    # Determine trigger type for better logging
                    trigger_type = "unknown"
                    if pending_marker['description'] in ['S 20', 'S 21']:
                        trigger_type = "grasp"
                    elif pending_marker['description'] in ['S 22', 'S 23']:
                        trigger_type = "release"
                    elif pending_marker['description'] in ['S  1', 'S  2', 'S  3', 'S  4', 'S  5', 'S  6', 'S  7']:
                        trigger_type = "training"
                    
                    data_to_send = {
                        "timestamp": time.time(),
                        "marker_description": pending_marker['description'],
                        "marker_stream_pos": int(marker_stream_pos),
                        "erd_percent": erd_data,
                        "erd_db": erd_db_value,
                        "channel_names": self.config.FOCUS_CHANNEL_NAMES,
                        "trigger_type": trigger_type
                    }
                    self.broadcaster.broadcast_data(data_to_send)
                    
                    # Log specific information for embodiment exercise triggers
                    if trigger_type in ["grasp", "release"]:
                        print(f"       Embodiment Exercise {trigger_type.upper()} - ERD%: {erd_data:.2f}%")
                else:
                    print(f"       ERD calculation for '{pending_marker['description']}' failed or resulted in None.")
                
                processed_markers_this_iteration.append(pending_marker)

        # Remove processed markers from the deque
        for pm in processed_markers_this_iteration:
            self.pending_markers_to_process.remove(pm)

        # Prune old unprocessable markers that are now too far behind the buffer
        while self.pending_markers_to_process and \
              (self.total_samples_streamed - buffer_samples) > (self.pending_markers_to_process[0]['stream_pos'] + self.data_processor.samples_after_marker):
            old_marker = self.pending_markers_to_process.popleft()
            print(f"  Pruned old unprocessable marker: '{old_marker['description']}' (stream pos: {old_marker['stream_pos']})")


    def _cleanup(self):
        """
        Disconnects from EEG source, closes broadcaster, saves data, and creates MNE Raw object.
        """
        print("\nDisconnecting and saving data...")
        self.receiver.disconnect()
        self.broadcaster.close()

        # Use custom filename if provided, otherwise use default timestamp
        import os
        os.makedirs("eeg_data", exist_ok=True)
        os.makedirs("eeg_markers", exist_ok=True)
        eeg_filename = f"./eeg_data/{self.file_base_name}.npy" if self.file_base_name else None
        markers_filename = f"./eeg_markers/{self.file_base_name}.csv" if self.file_base_name else None
        
        final_eeg_data = self.data_saver.save_eeg_data(self.all_eeg_data, eeg_filename)
        self.data_saver.save_markers(self.all_markers, markers_filename)
        self.data_saver.create_mne_raw(final_eeg_data, self.receiver.sampling_frequency, self.receiver.channel_names)
        print("Cleanup complete.")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="EEG data collection session for embodiment exercise")
    parser.add_argument("--p", required=True, type=int, help="Participant number")
    parser.add_argument("--w", required=True, type=int, help="Week number")
    args = parser.parse_args()

    file_base = f"P{args.p}_w{args.w}"
    
    # Entry point for running the EEG data collection pipeline
    collector = EEGDataCollector(file_base)
    collector.run()
