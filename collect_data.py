import numpy as np
import time
import socket # Import for basic socket operations
import json # For sending structured data like ERD results

# Import your actual LivestreamReceiver and Marker classes
from livestream_receiver import LivestreamReceiver, Marker
from emulator import Emulator
# from broadcasting import TCP_Server # You might not need this if implementing directly

import mne
import pandas as pd
from collections import deque # Useful for managing pending markers

from colorama import Fore, Style

from scipy.signal import butter, filtfilt


focus_channels = [7, 39, 42, 11] # C3, C1, CP3, CP1
focus_markers = ['S  9', 'S 10', 'S 11'] # Markers of interest for ERD calculation

low_cut = 8.0   # Hz
high_cut = 13.0 # Hz
filter_order = 5 # Filter order




# 1. Configure Connection Parameters
# Replace with the actual IP and port of your EEG data provider
eeg_server_ip = "169.254.1.147" #"127.0.0.1" <<< CHANGE THIS TO MOCK SERVER IP
eeg_server_port = 51244


# --- Broadcasting Configuration ---
enable_broadcasting = True # Set to True to enable broadcasting
broadcast_ip = "127.0.0.1" # IP address for the broadcasting server (usually localhost)
broadcast_port = 50000     # Port for the broadcasting server


collect_from_emulator = True
receiver = None
if collect_from_emulator:
    receiver = Emulator()
    receiver.initialize_connection()
else:
    print("Initializing LivestreamReceiver...")
    receiver = LivestreamReceiver(address=eeg_server_ip, port=eeg_server_port, broadcast=False) # Keep broadcast=False here, as we'll manage our own TCP_Server

all_eeg_data = []
all_markers = []
sampling_frequency = None
channel_names = None
channel_count = None

# --- Initialize Broadcasting Server ---
broadcast_server_socket = None
client_connection = None
try:
    if enable_broadcasting:
        broadcast_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        broadcast_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        broadcast_server_socket.bind((broadcast_ip, broadcast_port))
        broadcast_server_socket.listen(1) # Listen for one client connection
        broadcast_server_socket.settimeout(0.1) # Set a timeout for accept to keep main loop responsive
        print(f"Broadcasting server listening on {broadcast_ip}:{broadcast_port}...")

    # 3. Initialize the Connection
    print(f"Attempting to connect to {eeg_server_ip}:{eeg_server_port}...")
    sfreq, ch_names, n_channels, initial_data_buffer = receiver.initialize_connection()

    sampling_frequency = sfreq
    channel_names = ch_names
    channel_count = n_channels

    print("\nConnection successful and initialized!")
    print(f"Sampling Frequency: {sampling_frequency} Hz")
    print(f"Channel Names: {channel_names}")
    print(f"Number of Channels: {channel_count}")
    print("===================================\n")
    
    b, a = butter(filter_order, [low_cut, high_cut], btype='band', fs=sampling_frequency)
    

    seconds_before = 2.0
    seconds_after = 2.0
    buffer_duration_seconds = max(10.0, (seconds_before + seconds_after) * 1.5)
    buffer_samples = int(buffer_duration_seconds * sampling_frequency)
    samples_before_marker = int(seconds_before * sampling_frequency)
    samples_after_marker = int(seconds_after * sampling_frequency)
    epoch_total_samples = samples_before_marker + 1 + samples_after_marker

    live_eeg_buffer = np.full((n_channels, buffer_samples), np.nan)
    buffer_write_idx = 0
    total_samples_streamed = 0
    pending_markers_to_process = deque()
    
    input("Press Enter to start data collection...")

    print("Starting data collection loop (Press Ctrl+C to stop)...")
    max_duration_seconds = 120
    start_time = time.time()

    while (time.time() - start_time) < max_duration_seconds:
        # Accept client connection if enabled and not already connected
        if enable_broadcasting and client_connection is None:
            try:
                conn, addr = broadcast_server_socket.accept()
                client_connection = conn
                print(f"Accepted broadcasting connection from {addr}")
            except socket.timeout:
                pass # No client tried to connect in this interval
            except BlockingIOError:
                pass # No pending connections if socket is non-blocking (which it isn't here)
            except Exception as e:
                print(f"Error accepting client connection: {e}")

        data_chunk, markers = receiver.get_data()
        # print(markers)  # Debugging line to see markers received

        # print(f"Received data chunk with {len(markers)} markers and shape: {data_chunk.shape if data_chunk is not None else 'None'}")

        if data_chunk is not None:
            all_eeg_data.append(data_chunk)
            num_samples_in_chunk = data_chunk.shape[1]

            # --- 1. Add new data to the circular buffer ---
            start_idx = buffer_write_idx
            end_idx = start_idx + num_samples_in_chunk
            if end_idx <= buffer_samples:
                live_eeg_buffer[:, start_idx:end_idx] = data_chunk
            else:
                part1_len = buffer_samples - start_idx
                live_eeg_buffer[:, start_idx:buffer_samples] = data_chunk[:, :part1_len]
                part2_len = num_samples_in_chunk - part1_len
                live_eeg_buffer[:, :part2_len] = data_chunk[:, part1_len:]

            buffer_write_idx = end_idx % buffer_samples
            total_samples_streamed += num_samples_in_chunk

            # --- 2. Register incoming markers ---
            if markers:
                print(f"Received {len(markers)} markers in this chunk:")
                all_markers.extend(markers)
                for marker_obj in markers:
                    marker_stream_pos = total_samples_streamed + marker_obj.position
                    if marker_obj.description in focus_markers:
                        pending_markers_to_process.append({
                            'marker_obj': marker_obj,
                            'stream_pos': marker_stream_pos,
                            'description': marker_obj.description
                        })
                    print(f"  Registered Marker: '{marker_obj.description}' at stream sample {marker_stream_pos}")

            # --- 3. Process pending markers ---
            processed_markers_this_iteration = []
            for i in range(len(pending_markers_to_process)):
                pending_marker = pending_markers_to_process[i]
                
                marker_obj = pending_marker['marker_obj']
                marker_stream_pos = pending_marker['stream_pos']

                oldest_sample_in_buffer_stream_pos = max(0, total_samples_streamed - buffer_samples)
                required_epoch_end_stream_pos = marker_stream_pos + samples_after_marker

                if required_epoch_end_stream_pos < total_samples_streamed and \
                        (marker_stream_pos - samples_before_marker) >= oldest_sample_in_buffer_stream_pos:

                    # print(f"    Attempting to process epoch for marker: '{pending_marker['description']}'")

                    # --- 4. Extract epoch data from the circular buffer ---
                    epoch_data = np.full((n_channels, epoch_total_samples), np.nan)

                    # Calculate the start index in the buffer for the epoch
                    # This accounts for the circular nature of the buffer
                    epoch_start_stream_pos = marker_stream_pos - samples_before_marker
                    relative_epoch_start_in_buffer = (epoch_start_stream_pos - oldest_sample_in_buffer_stream_pos + buffer_write_idx) % buffer_samples

                    # Extract data from the circular buffer directly
                    if relative_epoch_start_in_buffer + epoch_total_samples <= buffer_samples:
                        epoch_data = live_eeg_buffer[:, relative_epoch_start_in_buffer : relative_epoch_start_in_buffer + epoch_total_samples]
                    else: # Epoch wraps around the buffer end
                        part1_len = buffer_samples - relative_epoch_start_in_buffer
                        epoch_data[:, :part1_len] = live_eeg_buffer[:, relative_epoch_start_in_buffer : buffer_samples]
                        part2_len = epoch_total_samples - part1_len
                        epoch_data[:, part1_len:] = live_eeg_buffer[:, :part2_len]

                    # --- 5. PERFORM YOUR LIVE CALCULATIONS ON 'epoch_data' ---
                    if not np.isnan(epoch_data).all():
                        print(f"      Epoch extracted for '{pending_marker['description']}'. Shape: {epoch_data.shape}. Performing live calculations...")

                        if (
                            epoch_data.shape == (n_channels, epoch_total_samples) and
                            not np.isnan(epoch_data).all() and
                            not np.all(np.isnan(epoch_data), axis=1).any()
                        ):
                            
                            filtered_epoch = filtfilt(b, a, epoch_data, axis=1)
                            
                            pre = filtered_epoch[:, :samples_before_marker]
                            post = filtered_epoch[:, samples_before_marker+1:]

                            pre_power = pre ** 2
                            post_power = post ** 2

                            R = np.nanmean(pre_power, axis=1)
                            A = np.nanmean(post_power, axis=1)

                            erd_percent = np.zeros_like(R, dtype=float)
                            non_zero_R_indices = R != 0
                            erd_percent[non_zero_R_indices] = ((A[non_zero_R_indices] - R[non_zero_R_indices]) / R[non_zero_R_indices]) * 100
                            erd_percent[R == 0] = np.nan
                            
                            erd_percent_focus = erd_percent[focus_channels]

                            print(Fore.RED +f"        ERD% per channel: {erd_percent_focus}"+ Style.RESET_ALL)

                            # --- Calculate and display average ERD visual indicator ---
                            # avg_erd_focus = np.nanmean(erd_percent_focus)
                            # if not np.isnan(avg_erd_focus):
                            #     print(f"        Average ERD across focus channels: {avg_erd_focus:.2f}%")
                            #     # Create a visual indicator based on negative magnitude
                            #     if avg_erd_focus < 0:
                            #         magnitude = min(int(abs(avg_erd_focus) / 5), 20)  # Scale to a max of 20 characters
                            #         indicator = Fore.BLUE + '#' * magnitude + Style.RESET_ALL
                            #         print(f"        ERD Visual: {indicator}")
                            #     else:
                            #         print("        ERD Visual: No significant ERD (positive or near zero)")
                            # else:
                            #     print("        ERD Visual: Not enough data to calculate average ERD.")

                            # --- 6. BROADCAST THE ERD PERCENTAGE ---
                            if enable_broadcasting and client_connection:
                                try:
                                    # Create a dictionary for the data to send
                                    # Include marker info for context
                                    data_to_send = {
                                        "timestamp": time.time(),
                                        "marker_description": pending_marker['description'],
                                        "marker_stream_pos": marker_stream_pos,
                                        "erd_percent": str(abs(np.nanmean(erd_percent_focus))), # Convert numpy array to list for JSON
                                        "channel_names": channel_names
                                    }
                                    message = json.dumps(data_to_send) + "\n" # Add newline as a message delimiter
                                    client_connection.sendall(message.encode('utf-8'))
                                    print(f"        Broadcasted ERD% for '{pending_marker['description']}'")
                                except BrokenPipeError:
                                    print("Client disconnected, resetting connection.")
                                    client_connection.close()
                                    client_connection = None
                                except Exception as e:
                                    print(f"Error broadcasting data: {e}")
                            else:
                                print("        Broadcasting not enabled or no client connected.")

                        else:
                            print(f"⚠️ Epoch extraction failed or is incomplete.")

                    else:
                        print(f"    Epoch for '{pending_marker['description']}' contained only NaNs or failed extraction.")

                    processed_markers_this_iteration.append(pending_marker)

            for pm in processed_markers_this_iteration:
                pending_markers_to_process.remove(pm)

            while pending_markers_to_process and \
                    (total_samples_streamed - buffer_samples) > (pending_markers_to_process[0]['stream_pos'] + samples_after_marker):
                old_marker = pending_markers_to_process.popleft()
                print(f"  Pruned old unprocessable marker: '{old_marker['description']}'")

except KeyboardInterrupt:
    print("\nData collection stopped by user (Ctrl+C).")
except RuntimeError as e:
    print(f"A runtime error occurred: {e}")
except ConnectionRefusedError:
    print(f"Connection refused. Ensure the EEG data provider is running at {eeg_server_ip}:{eeg_server_port}.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    print("Disconnecting from the server...")
    if hasattr(receiver, 'socket'):
        receiver.disconnect()

    if enable_broadcasting:
        if client_connection:
            print("Closing client broadcasting connection.")
            client_connection.close()
        if broadcast_server_socket:
            print("Closing broadcasting server socket.")
            broadcast_server_socket.close()

    if all_eeg_data:
        final_eeg_data = np.concatenate(all_eeg_data, axis=1)
        print(f"\nTotal collected EEG data shape: {final_eeg_data.shape}")
        np.save("collected_eeg_data.npy", final_eeg_data)
        print("Data saved to collected_eeg_data.npy (example)")

        if all_markers:
            markers_data = []
            for marker in all_markers:
                markers_data.append({
                    'description': marker.description,
                    'position': marker.position,
                    'channel': marker.channel
                })
            markers_df = pd.DataFrame(markers_data)
            markers_df.to_csv("collected_markers.csv", index=False)
            print("Markers saved to collected_markers.csv")
        else:
            print("No markers were collected.")

        if sampling_frequency and channel_names:
            ch_types = ['eeg'] * len(channel_names)
            info = mne.create_info(ch_names=channel_names, sfreq=sampling_frequency, ch_types=ch_types)
            raw_mne = mne.io.RawArray(final_eeg_data, info)
            raw_mne.set_montage("standard_1020", on_missing='warn')
            print("\nCreated MNE Raw object:")
            print(raw_mne)
    else:
        print("\nNo EEG data was collected.")