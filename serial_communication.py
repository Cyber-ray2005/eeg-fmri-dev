import serial
import time

class SerialCommunication:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def initialize(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.01)
            print(f"Serial port {self.port} opened successfully at {self.baudrate} baud.")
            time.sleep(0.1)
        except serial.SerialException as e:
            print(f"Error: Could not open serial port {self.port}. {e}")
            print("Proceeding without serial triggers.")
            self.ser = None
        except Exception as e:
            print(f"An unexpected error occurred during serial port initialization: {e}")
            self.ser = None

    def send_trigger(self, trigger_value):
        if self.ser and self.ser.is_open:
            try:
                # message_to_send = str(trigger_value).encode('ascii')
                # self.ser.write(bytes([trigger_value]))
                self.ser.write(trigger_value.to_bytes(length=1, byteorder="big"))
                print(f"Sent trigger: {trigger_value} (0x{trigger_value:02X})")
                time.sleep(0.001)
            except serial.SerialTimeoutException:
                print(f"Serial port timeout when sending trigger {trigger_value}.")
            except Exception as e:
                print(f"Error sending trigger {trigger_value}: {e}")

    def close(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                print("Serial port closed.")
            except Exception as e:
                print(f"Error closing serial port: {e}")
        self.ser = None