import socket
import json
import time

SERVER_IP = "127.0.0.1"
SERVER_PORT = 50000

print(f"Attempting to connect to ERD broadcast server at {SERVER_IP}:{SERVER_PORT}...")
try:
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((SERVER_IP, SERVER_PORT))
    print("Successfully connected to the ERD broadcast server.")

    buffer = ""
    while True:
        data = client_socket.recv(4096).decode('utf-8') # Receive data in chunks
        if not data:
            print("Server disconnected.")
            break
        
        buffer += data
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            try:
                erd_data = json.loads(line)
                print(f"Received ERD data: {erd_data}")
                # You can now use erd_data['erd_percent'], erd_data['marker_description'], etc.
                # For example, update a GUI or trigger an action
                print(f"  Marker: {erd_data.get('marker_description', 'N/A')}")
                print(f"  ERD Percentages: {erd_data.get('erd_percent', 'N/A')}")
                print(f"  Channels: {erd_data.get('channel_names', 'N/A')}")

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e} - Data: {line}")
            except Exception as e:
                print(f"Error processing received data: {e}")

except ConnectionRefusedError:
    print("Connection refused. Make sure the ERD broadcasting script is running.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    if 'client_socket' in locals() and client_socket:
        client_socket.close()
        print("Client socket closed.")