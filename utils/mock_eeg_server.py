import socket
import numpy as np
import time
import struct
import json
import random
import uuid # For GUID
import threading

# --- mock_eeg_server.py: Mock EEG Data Server for Development ---

# --- Configuration for the Mock Server ---
MOCK_SERVER_IP = "127.0.0.1"  # Use localhost for testing on the same machine
MOCK_SERVER_PORT = 51244
SAMPLING_FREQUENCY = 500  # Hz
NUM_CHANNELS = 8
# Change these to actual 10-20 channel names
CHANNEL_NAMES = ['Fp1', 'Fp2', 'C3', 'C4', 'Pz', 'O1', 'O2', 'Cz'] # Example 8 channels from 10-20
RESOLUTIONS = [0.0000001 for _ in range(NUM_CHANNELS)] # Example: 0.1 uV per unit

CHUNK_SIZE_SAMPLES = 50  # Number of samples per data chunk to send
SIMULATION_DURATION_SECONDS = 300 # How long the server will send data

# --- Message Type Constants (from your LivestreamReceiver) ---
MSG_TYPE_HANDSHAKE = 1
MSG_TYPE_EEG_DATA = 4
MSG_TYPE_STOP = 3

MARKER_INTERVAL_SECONDS = 3    # Desired interval for sending markers

# GUID (arbitrary, just needs to be consistent for the mock)
dummy_guid_ints = [0x01020304, 0x05060708, 0x090A0B0C, 0x0D0E0F00] # Example: simpler positive values

def generate_mock_eeg_data(num_channels, num_samples, amplitude=100, noise_level=5):
    """
    Generates synthetic EEG-like data with some sinusoidal components and noise.
    """
    time_vec = np.linspace(0, num_samples / SAMPLING_FREQUENCY, num_samples, endpoint=False)
    data = np.zeros((num_channels, num_samples))

    for i in range(num_channels):
        freq1 = 3 + i * 0.5
        freq2 = 10 + i * 0.7
        data[i, :] = (amplitude / (i+1)) * np.sin(2 * np.pi * freq1 * time_vec) + \
                     (amplitude / (i+1)/2) * np.sin(2 * np.pi * freq2 * time_vec + np.pi/2)
        data[i, :] += noise_level * np.random.randn(num_samples)
    
    return data / RESOLUTIONS[0]



connected_clients = []
client_lock = threading.Lock()

def client_handler(conn, addr):
    """Initial handshake and registration."""
    print(f"Client connected from {addr}")
    try:
        # Send handshake
        channel_names_bytes = b''.join(name.encode('utf-8') + b'\x00' for name in CHANNEL_NAMES)
        properties_payload = struct.pack('<Ld', NUM_CHANNELS, 1_000_000 / SAMPLING_FREQUENCY)
        properties_payload += b''.join(struct.pack('<d', res) for res in RESOLUTIONS)
        properties_payload += channel_names_bytes
        msgsize = 24 + len(properties_payload)
        handshake_header = struct.pack('<llllLL', *dummy_guid_ints, msgsize, MSG_TYPE_HANDSHAKE)
        conn.sendall(handshake_header + properties_payload)
        print(f"Handshake sent to {addr}")

        # Add to client list
        with client_lock:
            connected_clients.append(conn)

        # Stay idle while server sends data
        while True:
            time.sleep(1)
    except Exception as e:
        print(f"Client {addr} disconnected or errored: {e}")
    finally:
        with client_lock:
            if conn in connected_clients:
                connected_clients.remove(conn)
        conn.close()

def run_mock_eeg_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((MOCK_SERVER_IP, MOCK_SERVER_PORT))
    server_socket.listen(5)
    print(f"Mock EEG Server listening on {MOCK_SERVER_IP}:{MOCK_SERVER_PORT}")

    # Start thread to accept clients
    def accept_clients():
        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()

    threading.Thread(target=accept_clients, daemon=True).start()

    print("Broadcasting EEG data to all clients...")
    block_counter = 0
    start_time = time.time()
    last_marker_time = start_time # Stores the timestamp when the last marker was sent
    

    while (time.time() - start_time) < SIMULATION_DURATION_SECONDS:
        eeg_data_chunk = generate_mock_eeg_data(NUM_CHANNELS, CHUNK_SIZE_SAMPLES)
        current_chunk_markers = []

        current_time = time.time()
        if current_time - last_marker_time >= MARKER_INTERVAL_SECONDS:
            marker_position = random.randint(0, CHUNK_SIZE_SAMPLES - 1)
            description = random.choice(["Stimulus A", "Stimulus B"])
            current_chunk_markers.append({
                'position': marker_position,
                'points': 1,
                'channel': -1,
                'type': 'Event',
                'description': description
            })
            last_marker_time = current_time # Update the last marker time

        markers_payload = b''
        for m in current_chunk_markers:
            desc = m['type'].encode() + b'\x00' + m['description'].encode() + b'\x00'
            size = struct.calcsize('<L') + struct.calcsize('<LLl') + len(desc)
            markers_payload += struct.pack('<L', size)
            markers_payload += struct.pack('<LLl', m['position'], m['points'], m['channel'])
            markers_payload += desc

        flat_data = eeg_data_chunk.T.flatten().astype(np.float32)
        eeg_payload = struct.pack('<LLL', block_counter, CHUNK_SIZE_SAMPLES, len(current_chunk_markers))
        eeg_payload += flat_data.tobytes() + markers_payload
        msgsize = 24 + len(eeg_payload)
        eeg_header = struct.pack('<llllLL', *dummy_guid_ints, msgsize, MSG_TYPE_EEG_DATA)
        packet = eeg_header + eeg_payload

        # Send to all clients
        with client_lock:
            for conn in connected_clients[:]:  # Copy to avoid issues if we remove during loop
                try:
                    conn.sendall(packet)
                except Exception:
                    print("Removing dead client.")
                    connected_clients.remove(conn)

        block_counter += 1
        time.sleep(CHUNK_SIZE_SAMPLES / SAMPLING_FREQUENCY)

    print("Simulation done. Sending stop message...")
    stop_header = struct.pack('<llllLL', *dummy_guid_ints, 24, MSG_TYPE_STOP)
    with client_lock:
        for conn in connected_clients:
            try:
                conn.sendall(stop_header)
                conn.close()
            except:
                pass
    server_socket.close()
    print("Server shut down.")



if __name__ == "__main__":
    run_mock_eeg_server()