import serial
import time

# --- CONFIGURATION ---
LISTENER_PORT = 'COM12'  # Or '/tmp/vport2' - THE OTHER END of the virtual pair
BAUD_RATE = 9600
# --- END CONFIGURATION ---

print(f"Attempting to listen on {LISTENER_PORT} at {BAUD_RATE} baud...")
try:
    listener_ser = serial.Serial(LISTENER_PORT, BAUD_RATE, timeout=0.1) # timeout allows checking for new data
    print(f"Successfully listening on {LISTENER_PORT}. Press Ctrl+C to stop.")

    while True:
        if listener_ser.in_waiting > 0:
            received_byte = listener_ser.read(1) # Read one byte
            if received_byte:
                trigger_value = int.from_bytes(received_byte, 'big')
                print(f"Received: {received_byte} (Hex: {received_byte.hex()}), Value: {trigger_value}, Timestamp: {time.time()}")
        time.sleep(0.01) # Check for data periodically

except serial.SerialException as e:
    print(f"Error: Could not open or read from serial port {LISTENER_PORT}. {e}")
except KeyboardInterrupt:
    print("\nListener stopped by user.")
finally:
    if 'listener_ser' in locals() and listener_ser.is_open:
        listener_ser.close()
        print(f"Serial port {LISTENER_PORT} closed.")