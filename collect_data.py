import numpy as np
import time
import socket
import json
from collections import deque
import pandas as pd
from scipy.signal import butter, filtfilt
import mne
from colorama import Fore, Style

from livestream_receiver import LivestreamReceiver, Marker
from emulator import Emulator


# --- Configuration Class ---
class EEGConfig:
    def __init__(self):
        # EEG Connection Parameters
        self.EEG_SERVER_IP = "169.254.1.147"
        self.EEG_SERVER_PORT = 51244
        self.COLLECT_FROM_EMULATOR = False

        # Signal Processing Parameters
        self.FOCUS_CHANNELS = [7, 39, 42, 11] # C3, C1, CP3, CP1 (0-indexed)
        self.FOCUS_MARKERS = ['S  1', 'S  2', 'S  3', 'S  4', 'S  5', 'S  6']
        self.LOW_CUT = 8.0 # Hz (alpha band)
        self.HIGH_CUT = 13.0 # Hz (alpha band)
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
    def __init__(self, config: EEGConfig):
        self.config = config
        self.receiver = None
        self.sampling_frequency = None
        self.channel_names = None
        self.channel_count = None

    def initialize(self):
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
        return self.receiver.get_data()

    def disconnect(self):
        if hasattr(self.receiver, 'disconnect'):
            self.receiver.disconnect()

# --- Data Processor Class ---
class DataProcessor:
    def __init__(self, config: EEGConfig, sampling_frequency, channel_count):
        self.config = config
        self.sampling_frequency = sampling_frequency
        self.channel_count = channel_count
        self.b, self.a = butter(self.config.FILTER_ORDER,
                                [self.config.LOW_CUT, self.config.HIGH_CUT],
                                btype='band', fs=self.sampling_frequency)
        
        self.samples_before_marker = int(self.config.SECONDS_BEFORE_MARKER * self.sampling_frequency)
        self.samples_after_marker = int(self.config.SECONDS_AFTER_MARKER * self.sampling_frequency)
        self.epoch_total_samples = self.samples_before_marker + 1 + self.samples_after_marker

    def calculate_erd(self, epoch_data):
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
    def __init__(self, config: EEGConfig):
        self.config = config
        self.server_socket = None
        self.client_connection = None

    def initialize(self):
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
        if self.client_connection:
            try:
                message = json.dumps(data) + "\n"
                self.client_connection.sendall(message.encode('utf-8'))
                # print(f"Broadcasted ERD data.") # Muted for less console spam
            except BrokenPipeError:
                print("Client disconnected, resetting connection.")
                self.client_connection.close()
                self.client_connection = None
            except Exception as e:
                print(f"Error broadcasting data: {e}")
        else:
            # print("Broadcasting not enabled or no client connected.") # Muted for less console spam
            pass

    def close(self):
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
    def __init__(self, config: EEGConfig):
        self.config = config

    def save_eeg_data(self, all_eeg_data, filename="./data/collected_eeg_data.npy"):
        if all_eeg_data:
            final_eeg_data = np.concatenate(all_eeg_data, axis=1)
            print(f"\nTotal collected EEG data shape: {final_eeg_data.shape}")
            np.save(filename, final_eeg_data)
            print(f"Data saved to {filename}")
            return final_eeg_data
        else:
            print("\nNo EEG data was collected to save.")
            return None

    def save_markers(self, all_markers, filename="./data/collected_markers.csv"):
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
    def __init__(self):
        self.config = EEGConfig()
        self.receiver = EEGReceiver(self.config)
        self.broadcaster = ERDBroadcaster(self.config)
        self.data_saver = DataSaver(self.config)
        self.data_processor = None # Initialized after connection to get sfreq, n_channels

        self.all_eeg_data = []
        self.all_markers = []
        self.live_eeg_buffer = None
        self.buffer_write_idx = 0
        self.total_samples_streamed = 0
        self.pending_markers_to_process = deque()

    def run(self):
        if not self.receiver.initialize():
            return # Exit if connection fails

        self.data_processor = DataProcessor(self.config, self.receiver.sampling_frequency, self.receiver.channel_count)
        self.broadcaster.initialize()

        # Calculate buffer size based on processing needs
        buffer_duration_seconds = max(10.0, (self.config.SECONDS_BEFORE_MARKER + self.config.SECONDS_AFTER_MARKER) * 1.5)
        buffer_samples = int(buffer_duration_seconds * self.receiver.sampling_frequency)
        self.live_eeg_buffer = np.full((self.receiver.channel_count, buffer_samples), np.nan)

        input("Press Enter to start data collection...")
        print("Starting data collection loop (Press Ctrl+C to stop)...")

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
                        self.all_markers.extend(markers)
                        for marker_obj in markers:
                            # Marker position relative to the start of the entire stream
                            marker_stream_pos = self.total_samples_streamed - num_samples_in_chunk + marker_obj.position
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
                
                relative_epoch_start_in_buffer = (epoch_start_stream_pos - oldest_sample_in_buffer_stream_pos + self.buffer_write_idx - self.total_samples_streamed + buffer_samples) % buffer_samples
                
                epoch_data = np.full((self.receiver.channel_count, self.data_processor.epoch_total_samples), np.nan)

                if relative_epoch_start_in_buffer + self.data_processor.epoch_total_samples <= buffer_samples:
                    epoch_data = self.live_eeg_buffer[:, relative_epoch_start_in_buffer : relative_epoch_start_in_buffer + self.data_processor.epoch_total_samples]
                else: # Epoch wraps around the buffer end
                    part1_len = buffer_samples - relative_epoch_start_in_buffer
                    epoch_data[:, :part1_len] = self.live_eeg_buffer[:, relative_epoch_start_in_buffer : buffer_samples]
                    part2_len = self.data_processor.epoch_total_samples - part1_len
                    epoch_data[:, part1_len:] = self.live_eeg_buffer[:, :part2_len]

                # Perform live calculations
                print(f"       Epoch extracted for '{pending_marker['description']}'. Shape: {epoch_data.shape}. Performing live calculations...")
                
                erd_results = self.data_processor.calculate_erd(epoch_data)

                if erd_results is not None:
                    data_to_send = {
                        "timestamp": time.time(),
                        "marker_description": pending_marker['description'],
                        "marker_stream_pos": marker_stream_pos,
                        "erd_percent": erd_results,
                        "channel_names": [self.receiver.channel_names[i] for i in self.config.FOCUS_CHANNELS]
                    }
                    self.broadcaster.broadcast_data(data_to_send)
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
        print("\nDisconnecting and saving data...")
        self.receiver.disconnect()
        self.broadcaster.close()

        final_eeg_data = self.data_saver.save_eeg_data(self.all_eeg_data)
        self.data_saver.save_markers(self.all_markers)
        self.data_saver.create_mne_raw(final_eeg_data, self.receiver.sampling_frequency, self.receiver.channel_names)
        print("Cleanup complete.")

if __name__ == "__main__":
    collector = EEGDataCollector()
    collector.run()