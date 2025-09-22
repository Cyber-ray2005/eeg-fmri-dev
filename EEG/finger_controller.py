"""
Supernumerary Finger Controller Library
A non-blocking library for controlling robotic finger servos via Serial UART

Author: Pi Ko (pi.ko@nyu.edu)
Date: 2025
Version: 2.0.0

This library provides a simple interface to control a robotic finger servo
through Serial UART commands. It automatically discovers the device on available
COM ports and sends flex/reset commands.

The controller communicates with the servo firmware using simple serial commands:
- e<0-100>: Execute flex test with specified percentage
- r: Reset to default position

Installation:
    pip install pyserial

Usage:
    from finger_controller import FingerController
    
    # Initialize the controller (auto-discovers serial port)
    controller = FingerController()
    
    # Execute finger movement (0-100%)
    controller.execute_finger(50)  # Move to 50% flex
    
    # Optional: Set custom delay between flex and reset
    controller.set_reset_delay(2.0)  # 2 seconds delay
"""

import serial
import serial.tools.list_ports
import time
import threading
import platform
import sys
from typing import Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor

# Default serial settings
DEFAULT_BAUD_RATE = 115200
DEFAULT_TIMEOUT = 0.5


class FingerController:
    """
    Supernumerary Finger Controller
    
    A controller class for managing robotic finger servo operations through Serial UART.
    Provides automatic device discovery on available COM ports.
    
    Attributes:
        reset_delay (float): Time delay between flex and reset commands (default: 2.5 seconds)
        port (str): Serial port name (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
        baud_rate (int): Serial communication baud rate (default: 115200)
        serial_conn (Serial): Active serial connection object
    
    Example:
        >>> controller = FingerController()
        >>> controller.execute_finger(75)  # Flex finger to 75%
        >>> controller.execute_finger(0)   # Return to rest position
    """
    
    def __init__(self, reset_delay: float = 2.5, port: Optional[str] = None,
                 baud_rate: int = DEFAULT_BAUD_RATE, auto_discover: bool = True):
        """
        Initialize the Finger Controller.
        
        Args:
            reset_delay (float): Delay in seconds between flex and reset commands (default: 2.5)
            port (Optional[str]): Specific serial port to use (default: None, auto-discover)
            baud_rate (int): Serial baud rate (default: 115200)
            auto_discover (bool): Automatically discover device on initialization (default: True)
        """
        # Configuration parameters
        self.reset_delay = reset_delay
        self.baud_rate = baud_rate
        self.port = port
        
        # Internal state management
        self.serial_conn = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._discovered = False
        self._lock = threading.Lock()
        
        # Auto-discover device if requested
        if auto_discover:
            print("Initializing Supernumerary Finger Controller...")
            if self.port:
                # Use specified port
                if self.connect_to_port(self.port):
                    print(f"✓ Controller ready. Connected to {self.port}")
                else:
                    print(f"⚠ Failed to connect to specified port {self.port}")
            else:
                # Auto-discover
                self.discover_and_connect()
                if self.serial_conn:
                    print(f"✓ Controller ready. Device discovered at {self.port}")
                else:
                    print("⚠ No servo controller found on any serial port")
    
    def set_reset_delay(self, delay: float):
        """
        Set the delay between flex and reset commands.
        
        Args:
            delay (float): Delay in seconds (must be positive)
            
        Raises:
            ValueError: If delay is negative
        """
        if delay < 0:
            raise ValueError("Reset delay must be positive")
        self.reset_delay = delay
        print(f"Reset delay set to {delay} seconds")
    
    def discover_and_connect(self) -> bool:
        """
        Discover and connect to the servo controller device.
        Scans all available serial ports for the servo controller.
        
        Performs automatic detection by sending a test command to each
        available serial port and checking for a valid response.
        
        Returns:
            bool: True if device found and connected, False otherwise
        """
        print("Discovering servo controller on serial ports...")
        
        # Get list of available serial ports
        ports = self._get_available_ports()
        
        if not ports:
            print("[WARNING] No serial ports found on system")
            return False
        
        print(f"Found {len(ports)} serial port(s) to scan:")
        for port_info in ports:
            print(f"  - {port_info[0]}: {port_info[1]}")
        
        # Try each port
        for port_name, description in ports:
            print(f"Testing {port_name}...", end=' ')
            
            if self._test_port(port_name):
                print("✓ Servo controller found!")
                self.port = port_name
                self._discovered = True
                
                # Connect to the discovered port
                return self.connect_to_port(port_name)
            else:
                print("✗")
        
        print("[WARNING] No servo controller found on any port")
        return False
    
    def connect_to_port(self, port: str) -> bool:
        """
        Connect to a specific serial port.
        
        Args:
            port (str): Serial port name
            
        Returns:
            bool: True if connected successfully, False otherwise
        """
        try:
            # Close existing connection if any
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            
            # Open new connection
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=self.baud_rate,
                timeout=DEFAULT_TIMEOUT,
                write_timeout=DEFAULT_TIMEOUT
            )
            
            # Clear any pending data
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()
            
            # Give device time to initialize
            time.sleep(0.5)
            
            self.port = port
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to connect to {port}: {e}")
            return False
    
    def execute_finger(self, percentage: int) -> bool:
        """
        Execute finger movement to specified flex percentage.
        
        This is the main control function. It sends a flex command to the servo,
        waits for the configured delay, then sends a reset command. All operations
        are non-blocking - the function returns immediately after initiating the
        command sequence.
        
        Args:
            percentage (int): Flex percentage (0-100)
                - 0: Fully extended (rest position)
                - 100: Fully flexed
                
        Returns:
            bool: True if command initiated successfully, False otherwise
            
        Raises:
            ValueError: If percentage is not between 0 and 100
            
        Example:
            >>> controller.execute_finger(50)  # Flex to 50%
            True
            >>> controller.execute_finger(100) # Full flex
            True
            >>> controller.execute_finger(0)   # Return to rest
            True
        """
        # Validate input
        if not isinstance(percentage, (int, float)):
            raise ValueError(f"Percentage must be a number, got {type(percentage)}")
        
        if not 0 <= percentage <= 100:
            raise ValueError(f"Percentage must be between 0 and 100, got {percentage}")
        
        # Check if device is connected
        if not self.serial_conn or not self.serial_conn.is_open:
            print("[ERROR] No serial connection. Run discover_and_connect() first.")
            return False
        
        # Convert to integer for command
        percentage = int(percentage)
        
        # Start the command sequence in a background thread
        # This makes the function non-blocking
        threading.Thread(
            target=self._execute_sequence,
            args=(percentage,),
            daemon=True
        ).start()
        
        return True
    
    def _execute_sequence(self, percentage: int):
        """
        Internal method to execute the flex-wait-reset sequence.
        
        This runs in a background thread to maintain non-blocking behavior.
        
        Args:
            percentage (int): Flex percentage (0-100)
        """
        try:
            with self._lock:
                # Send flex command via serial
                flex_command = f"e{percentage}\n"
                
                try:
                    self.serial_conn.write(flex_command.encode('utf-8'))
                    self.serial_conn.flush()
                    print(f"→ Flex command sent: {percentage}% (serial: {flex_command.strip()})")
                    if(percentage == 0):
                        self.serial_conn.write("r\n".encode('utf-8'))
                    # Read any response (non-blocking)
                    time.sleep(0.1)  # Give device time to respond
                    if self.serial_conn.in_waiting:
                        response = self.serial_conn.read(self.serial_conn.in_waiting).decode('utf-8', errors='ignore')
                        # Parse response if needed (for debugging)
                        for line in response.split('\n'):
                            if 'SERIAL CMD' in line or 'ERROR' in line:
                                print(f"  Device: {line.strip()}")
                                
                except Exception as e:
                    print(f"[WARNING] Flex command may have failed: {e}")
                    return
            
            # Wait for the specified delay (hardware needs time to execute)
            print(f"  Waiting {self.reset_delay}s for movement to complete...")
            time.sleep(self.reset_delay)
            
            with self._lock:
                # Send reset command
                reset_command = "r\n"
                try:
                    self.serial_conn.write(reset_command.encode('utf-8'))
                    self.serial_conn.flush()
                    print(f"← Reset command sent")
                    
                    # Read any response
                    time.sleep(0.1)
                    if self.serial_conn.in_waiting:
                        response = self.serial_conn.read(self.serial_conn.in_waiting).decode('utf-8', errors='ignore')
                        for line in response.split('\n'):
                            if 'SERIAL CMD' in line or 'Reset' in line:
                                print(f"  Device: {line.strip()}")
                                
                except Exception as e:
                    print(f"[WARNING] Reset command may have failed: {e}")
                
        except Exception as e:
            print(f"[ERROR] Command sequence failed: {e}")
    
    def send_raw_command(self, command: str) -> Optional[str]:
        """
        Send a raw command to the device and get response.
        
        Args:
            command (str): Raw command to send (without newline)
            
        Returns:
            Optional[str]: Response from device if any, None otherwise
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("[ERROR] No serial connection")
            return None
        
        try:
            with self._lock:
                # Clear buffers
                self.serial_conn.reset_input_buffer()
                
                # Send command
                self.serial_conn.write(f"{command}\n".encode('utf-8'))
                self.serial_conn.flush()
                
                # Wait for response
                time.sleep(0.2)
                
                # Read response
                if self.serial_conn.in_waiting:
                    response = self.serial_conn.read(self.serial_conn.in_waiting).decode('utf-8', errors='ignore')
                    return response
                    
                return ""
                
        except Exception as e:
            print(f"[ERROR] Failed to send command: {e}")
            return None
    
    def reset(self) -> bool:
        """
        Send a reset command to return the finger to default position.
        
        Returns:
            bool: True if command sent successfully, False otherwise
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("[ERROR] No serial connection")
            return False
        
        try:
            with self._lock:
                self.serial_conn.write(b"r\n")
                self.serial_conn.flush()
                print("Reset command sent")
                return True
        except Exception as e:
            print(f"[ERROR] Reset failed: {e}")
            return False
    
    def cleanup(self):
        """
        Clean up resources and close connections.
        
        Should be called when done using the controller.
        """
        if self.serial_conn and self.serial_conn.is_open:
            # Send final reset before closing
            try:
                self.serial_conn.write(b"r\n")
                self.serial_conn.flush()
                time.sleep(0.1)
            except:
                pass
            
            # Close connection
            self.serial_conn.close()
            
        if self._executor:
            self._executor.shutdown(wait=False)
            
        print("Controller cleaned up")
    
    # ============== HELPER METHODS ==============
    
    def _get_available_ports(self) -> List[Tuple[str, str]]:
        """
        Get list of available serial ports.
        
        Returns:
            List[Tuple[str, str]]: List of (port_name, description) tuples
        """
        ports = []
        
        try:
            available_ports = serial.tools.list_ports.comports()
            
            for port in available_ports:
                # Filter out some obviously non-device ports
                if 'Bluetooth' in port.description or 'Virtual' in port.description:
                    continue
                    
                ports.append((port.device, port.description))
                
        except Exception as e:
            print(f"[ERROR] Failed to list ports: {e}")
        
        return ports
    
    def _test_port(self, port_name: str) -> bool:
        """
        Test if a port has the servo controller.
        
        Args:
            port_name (str): Port name to test
            
        Returns:
            bool: True if servo controller detected, False otherwise
        """
        test_conn = None
        
        try:
            # Try to open the port
            test_conn = serial.Serial(
                port=port_name,
                baudrate=self.baud_rate,
                timeout=0.5,
                write_timeout=0.5
            )
            
            # Clear buffers
            test_conn.reset_input_buffer()
            test_conn.reset_output_buffer()
            
            # Wait for device to be ready
            time.sleep(0.3)
            
            # Read any startup messages
            if test_conn.in_waiting:
                startup_msg = test_conn.read(test_conn.in_waiting).decode('utf-8', errors='ignore')
                
                # Check for servo controller signatures
                if any(marker in startup_msg for marker in ['Servo Controller', 'SERIAL COMMANDS', 'Version']):
                    return True
            
            # Send a test command (small flex)
            test_conn.write(b"e0\n")
            test_conn.flush()
            time.sleep(0.2)
            
            # Check for response
            if test_conn.in_waiting:
                response = test_conn.read(test_conn.in_waiting).decode('utf-8', errors='ignore')
                
                # Look for expected response patterns
                if 'SERIAL CMD' in response or 'Executing' in response or 'Flex' in response:
                    return True
                
                # Also accept if we see encoder data (the comma-separated values)
                if response.count(',') >= 3:  # Encoder output has multiple comma-separated values
                    return True
            
            return False
            
        except (serial.SerialException, OSError):
            # Port might be in use or not valid
            return False
            
        finally:
            if test_conn and test_conn.is_open:
                try:
                    test_conn.close()
                except:
                    pass
    
    def is_connected(self) -> bool:
        """
        Check if controller is connected to a device.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.serial_conn is not None and self.serial_conn.is_open
    
    def get_port_info(self) -> Optional[str]:
        """
        Get information about the connected port.
        
        Returns:
            Optional[str]: Port information string or None if not connected
        """
        if not self.is_connected():
            return None
            
        return f"Port: {self.port}, Baud: {self.baud_rate}"


# ============== MODULE-LEVEL CONVENIENCE FUNCTIONS ==============

# Global controller instance for simple usage
_global_controller = None


def initialize(reset_delay: float = 1.0, port: Optional[str] = None,
               baud_rate: int = DEFAULT_BAUD_RATE) -> FingerController:
    """
    Initialize the global finger controller.
    
    This is a convenience function for simple use cases where you don't
    need multiple controller instances.
    
    Args:
        reset_delay (float): Delay between flex and reset (default: 1.0)
        port (Optional[str]): Specific serial port to use (default: None, auto-discover)
        baud_rate (int): Serial baud rate (default: 115200)
        
    Returns:
        FingerController: The initialized controller instance
        
    Example:
        >>> import finger_controller
        >>> finger_controller.initialize()
        >>> finger_controller.execute_finger(50)
    """
    global _global_controller
    _global_controller = FingerController(reset_delay, port=port, baud_rate=baud_rate)
    return _global_controller


def execute_finger(percentage: int) -> bool:
    """
    Execute finger movement using the global controller.
    
    This is a convenience function that uses a global controller instance.
    Will automatically initialize the controller if not already done.
    
    Args:
        percentage (int): Flex percentage (0-100)
        
    Returns:
        bool: True if successful, False otherwise
        
    Example:
        >>> import finger_controller as fc
        >>> fc.execute_finger(75)  # Auto-initializes if needed
        True
    """
    global _global_controller
    
    # Auto-initialize if needed
    if _global_controller is None:
        print("Auto-initializing controller...")
        _global_controller = FingerController()
    
    return _global_controller.execute_finger(percentage)


def cleanup():
    """
    Clean up the global controller resources.
    
    Call this when done using the controller to properly
    close all connections and threads.
    """
    global _global_controller
    if _global_controller:
        _global_controller.cleanup()
        _global_controller = None


# ============== MAIN DEMO ==============

def main():
    """
    Demo/test function showing library usage.
    
    Run this file directly to test the finger controller.
    Will automatically discover the servo controller on available serial ports.
    """
    print("=" * 60)
    print("Supernumerary Finger Controller - Demo Mode")
    print("=" * 60)
    
    try:
        # Create controller instance
        controller = FingerController(reset_delay=1.5)
        
        if not controller.is_connected():
            print("\n[ERROR] No servo controller found. Please check:")
            print("  1. Device is connected via USB")
            print("  2. Device is powered on")
            print("  3. Correct drivers are installed")
            return 1
        
        print(f"\nConnected: {controller.get_port_info()}")
        print("\nTesting finger movements...")
        print("-" * 40)
        
        # Test sequence
        test_sequence = [
            (0, "Rest position"),
            (25, "Light flex"),
            (50, "Medium flex"),
            (75, "Strong flex"),
            (100, "Full flex"),
            (0, "Return to rest")
        ]
        
        for percentage, description in test_sequence:
            print(f"\n{description}: {percentage}%")
            controller.execute_finger(percentage)
            time.sleep(3)  # Wait between commands for demo
        
        print("\n" + "=" * 60)
        print("Demo complete!")
        
        # Cleanup
        controller.cleanup()
        
    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())