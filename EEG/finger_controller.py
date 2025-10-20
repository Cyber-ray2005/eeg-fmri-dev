"""
Supernumerary Finger Controller Library
Direct serial control with test functions

Author: Pi Ko (pi.ko@nyu.edu)
Date: 2025
Version: 6.0.0

This library sends serial commands directly to the servo firmware.
Auto-connects on first use - no setup required.

Serial Commands Used:
- f<0-100>: Flex to percentage
- u<0-100>: Unflex sequence  
- e<0-100>: Execute full cycle
- r: Reset to 50%

Example usage:
    # Step 1: Import the library
    import finger_controller as fc
    
    # Step 2: Calibrate (optional - auto-connects on first use)
    fc.execute_finger(0)
    
    # Step 3: Use any function
    fc.execute_finger(100)     # Original function
    fc.flex_test(100)          # New: Flex with reset sequence
    fc.unflex_test(100)        # New: Unflex with reset sequence  
    fc.full_cycle_test(100)    # New: Full cycle with reset sequence
"""

import serial
import serial.tools.list_ports
import time
from typing import Optional

# Global connection (initialized on first use)
_serial_conn: Optional[serial.Serial] = None
_initialized = False


def _auto_init() -> bool:
    """
    Auto-initialize connection on first use.
    """
    global _serial_conn, _initialized
    
    if _initialized:
        return True
    
    print("Auto-connecting to finger controller...")
    
    # Try to auto-discover
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        # Skip Bluetooth and virtual ports
        if 'Bluetooth' in port.description or 'Virtual' in port.description:
            continue
        
        print(f"Testing {port.device}...", end=' ')
        
        try:
            test_conn = serial.Serial(
                port=port.device,
                baudrate=115200,
                timeout=0.5,
                write_timeout=0.5
            )
            
            # Clear buffers
            test_conn.reset_input_buffer()
            test_conn.reset_output_buffer()
            
            # Wait a bit
            time.sleep(0.3)
            
            # Check for startup messages
            if test_conn.in_waiting:
                msg = test_conn.read(test_conn.in_waiting).decode('utf-8', errors='ignore')
                if 'Servo Controller' in msg or 'SERIAL COMMANDS' in msg:
                    test_conn.close()
                    print("Found!")
                    _serial_conn = serial.Serial(
                        port=port.device,
                        baudrate=115200,
                        timeout=0.5,
                        write_timeout=0.5
                    )
                    _serial_conn.reset_input_buffer()
                    _serial_conn.reset_output_buffer()
                    time.sleep(0.5)
                    _initialized = True
                    print(f"Connected to {port.device}")
                    return True
            
            # Try sending a test command
            test_conn.write(b"r\n")
            test_conn.flush()
            time.sleep(0.2)
            
            if test_conn.in_waiting:
                response = test_conn.read(test_conn.in_waiting).decode('utf-8', errors='ignore')
                if 'Reset' in response or 'SERIAL' in response or ',' in response:
                    test_conn.close()
                    print("Found!")
                    _serial_conn = serial.Serial(
                        port=port.device,
                        baudrate=115200,
                        timeout=0.5,
                        write_timeout=0.5
                    )
                    _serial_conn.reset_input_buffer()
                    _serial_conn.reset_output_buffer()
                    time.sleep(0.5)
                    _initialized = True
                    print(f"Connected to {port.device}")
                    return True
            
            test_conn.close()
            print("No")
            
        except:
            print("No")
            continue
    
    print("[ERROR] No servo controller found")
    return False


def _send_command(command: str) -> bool:
    """
    Send a command to the device.
    """
    global _serial_conn
    
    # Auto-init if needed
    if not _initialized:
        if not _auto_init():
            return False
    
    if not _serial_conn or not _serial_conn.is_open:
        print("[ERROR] Connection lost")
        return False
    
    try:
        _serial_conn.write(f"{command}\n".encode('utf-8'))
        _serial_conn.flush()
        
        # Read any response
        time.sleep(0.1)
        if _serial_conn.in_waiting:
            response = _serial_conn.read(_serial_conn.in_waiting).decode('utf-8', errors='ignore')
            # Print relevant responses
            for line in response.split('\n'):
                if 'SERIAL CMD' in line or 'ERROR' in line or 'Reset' in line:
                    print(f"  Device: {line.strip()}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send command: {e}")
        return False


def execute_finger(percentage: int) -> bool:
    """
    Original execute finger function - full cycle (flex->unflex->reset).
    
    Args:
        percentage (int): Flex percentage (0-100)
        
    Returns:
        bool: True if successful
        
    Example:
        >>> import finger_controller as fc
        >>> fc.execute_finger(100)
    """
    full_cycle_test(percentage)


def flex_test(percentage: int) -> bool:
    """
    Execute flex test with reset sequence.
    Flexes to percentage, waits 2 seconds, then sends reset 3 times.
    
    Args:
        percentage (int): Target flex percentage (0-100)
        
    Returns:
        bool: True if successful
        
    Example:
        >>> import finger_controller as fc
        >>> fc.flex_test(100)
    """
    if not 0 <= percentage <= 100:
        raise ValueError(f"Percentage must be 0-100, got {percentage}")
    
    print(f"\n=== FLEX TEST {percentage}% ===")
    
    # Send flex command
    percentage_adjusted = percentage
    print(f"→ Flexing to {percentage_adjusted}%")
    if not _send_command(f"f{percentage_adjusted}"):
        return False
    
    # Wait 2 seconds
    print("  Waiting 2 seconds...")
    time.sleep(2.0)
    
    # Send reset 3 times
    print("  Sending reset commands...")
    for i in range(10):
        print(f"  Reset {i+1}/10")
        _send_command("r")
        time.sleep(0.1)
    
    print(f"✓ Flex test complete")
    return True


def unflex_test(percentage: int) -> bool:
    """
    Execute unflex sequence test with reset sequence.
    Runs unflex sequence, waits 2 seconds, then sends reset 3 times.
    
    Args:
        percentage (int): Reference percentage (0-100)
        
    Returns:
        bool: True if successful
        
    Example:
        >>> import finger_controller as fc
        >>> fc.unflex_test(100)
    """
    if not 0 <= percentage <= 100:
        raise ValueError(f"Percentage must be 0-100, got {percentage}")
    
    print(f"\n=== UNFLEX TEST from {percentage}% ===")
    
    # Send unflex command
    print(f"← Executing unflex sequence")
    if not _send_command(f"u{percentage}"):
        return False
    
    # Wait 2 seconds
    print("  Waiting 2 seconds...")
    time.sleep(2.5)
    
    # Send reset 3 times
    print("  Sending reset commands...")
    for i in range(5):
        print(f"  Reset {i+1}/5")
        _send_command("r")
        time.sleep(0.1)
    
    print(f"✓ Unflex test complete")
    return True


def full_cycle_test(percentage: int) -> bool:
    """
    Execute full cycle test with reset sequence.
    Runs full cycle, waits 2 seconds, then sends reset 3 times.
    
    Args:
        percentage (int): Flex percentage for the cycle (0-100)
        
    Returns:
        bool: True if successful
        
    Example:
        >>> import finger_controller as fc
        >>> fc.full_cycle_test(100)
    """
    if not 0 <= percentage <= 100:
        raise ValueError(f"Percentage must be 0-100, got {percentage}")
    
    print(f"\n=== FULL CYCLE TEST {percentage}% ===")
    
    # Send execute command
    print(f"↔ Running full cycle (flex→unflex→reset)")
    if not _send_command(f"e{percentage}"):
        return False

    # Wait additional 2 seconds
    print("  Waiting additional 2 seconds...")
    time.sleep(3.0)
    
    # Send reset 3 times
    print("  Sending reset commands...")
    for i in range(3):
        print(f"  Reset {i+1}/3")
        _send_command("r")
        time.sleep(0.3)
    
    print(f"✓ Full cycle test complete")
    return True


def reset() -> bool:
    """
    Send reset command to return to 50% position.
    
    Returns:
        bool: True if successful
        
    Example:
        >>> import finger_controller as fc
        >>> fc.reset()
    """
    print("Resetting to default position")
    return _send_command("r")


def disconnect():
    """
    Close the serial connection and cleanup.
    
    Example:
        >>> import finger_controller as fc
        >>> fc.disconnect()
    """
    global _serial_conn, _initialized
    
    if _serial_conn and _serial_conn.is_open:
        # Send final reset
        try:
            _serial_conn.write(b"r\n")
            _serial_conn.flush()
            time.sleep(0.1)
        except:
            pass
        
        # Close connection
        _serial_conn.close()
        _serial_conn = None
        _initialized = False
        print("Disconnected")


# Demo function
def demo():
    """
    Demo all functions.
    """
    print("Finger Controller Demo")
    print("=" * 40)
    
    # Calibrate
    print("\nCalibrating...")
    execute_finger(0)
    time.sleep(2)
    
    # Test original function
    print("\nTesting original execute_finger...")
    execute_finger(100)
    time.sleep(3)
    
    # Test new functions
    print("\nTesting new functions...")
    flex_test(100)
    time.sleep(2)
    
    unflex_test(100)
    time.sleep(2)
    
    full_cycle_test(100)
    
    print("\n" + "=" * 40)
    print("Demo complete!")
    
    # Cleanup
    disconnect()


if __name__ == "__main__":
    demo()