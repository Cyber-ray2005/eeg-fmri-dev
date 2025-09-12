import socket # --- NEW: Import socket for TCP communication ---
import time

# --- tcp_client.py: TCP Client Utility for ERD Feedback ---
class TCPClient:
    """
    Implements a TCP client for connecting to the ERD broadcaster.
    Supports background listening (in a thread), data queueing, and clean shutdown.
    Used by experiment scripts to receive live ERD feedback.
    """
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(0.1)  # Set a small timeout for non-blocking receive
            print(f"Connected to TCP server at {self.host}:{self.port}")
            return True
        except ConnectionRefusedError:
            print(f"Connection refused. Ensure the TCP server is running at {self.host}:{self.port}.")
        except self.socket.timeout:
            print(f"Connection timed out when trying to connect to {self.host}:{self.port}.")
        except Exception as e:
            print(f"An error occurred while connecting to TCP server: {e}")
        self.socket = None
        return False
    
    def tcp_listener_thread(self, data_queue, stop_event):
        """
        Function to be run in a separate thread to listen for incoming TCP data.
        Puts received data into a thread-safe queue.
        Handles message framing by buffering data and splitting on newlines.
        """
        byte_buffer = b""  # Buffer for incomplete bytes
        max_buffer_size = 10240  # 10KB max buffer to prevent memory issues
        
        while not stop_event.is_set():
            if self.socket:
                try:
                    data = self.socket.recv(1024)
                    if data:
                        # Add bytes to buffer
                        byte_buffer += data
                        
                        # Prevent buffer from growing too large
                        if len(byte_buffer) > max_buffer_size:
                            print(f"Warning: TCP buffer exceeded {max_buffer_size} bytes, clearing buffer")
                            byte_buffer = b""
                            continue
                        
                        # Try to decode and split messages
                        try:
                            # Decode the entire buffer
                            text_buffer = byte_buffer.decode('utf-8')
                            
                            # Split on newlines to get complete messages
                            while '\n' in text_buffer:
                                line, text_buffer = text_buffer.split('\n', 1)
                                line = line.strip()
                                if line:  # Only put non-empty lines in queue
                                    # print(f"Received complete message: {line}")
                                    data_queue.put(line)
                            
                            # Convert remaining text back to bytes for next iteration
                            byte_buffer = text_buffer.encode('utf-8')
                            
                        except UnicodeDecodeError:
                            # Partial UTF-8 sequence, keep the bytes for next iteration
                            # print("Partial UTF-8 sequence, waiting for more data")
                            pass
                            
                    elif not data:  # Server closed connection
                        print("TCP server closed the connection.")
                        break
                except socket.timeout:
                    pass
                except socket.error as e:
                    print(f"Socket error in listener thread: {e}")
                    break # Exit thread on socket error
                except Exception as e:
                    print(f"Error in TCP listener thread: {e}")
                    break # Exit thread on other errors
            time.sleep(0.01) # Small delay to prevent busy-waiting
        print("TCP listener thread stopping.")
        if self.socket:
            self.socket.close()
            self.socket = None

    def send_data(self, data):
        if self.socket:
            try:
                self.socket.sendall(data.encode('utf-8'))
            except Exception as e:
                print(f"Error sending data: {e}")

    def close(self, stop_event):
        if self.socket:
            stop_event.set()
            print("TCP connection marked for closure.")
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)  # Shutdown both read and write
                    self.socket.close()
                    print("TCP socket closed.")
                except OSError as e:
                    print(f"Error shutting down TCP socket: {e}")
                except Exception as e:
                    print(f"Unexpected error closing TCP socket: {e}")
            self.socket = None
        stop_event.clear()  # Clear the event for potential re-runs