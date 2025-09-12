"""
Supernumerary Finger Controller Library
A non-blocking library for controlling robotic finger servos via HTTP API

Author: Pi Ko (pi.ko@nyu.edu)
Date: 2025
Version: 1.0.0

This library provides a simple interface to control a robotic finger servo
through HTTP API calls. It automatically discovers the device on the network,
sends flex commands, and handles reset operations.

Installation:
    pip install aiohttp aioconsole requests

Usage:
    from finger_controller import FingerController
    
    # Initialize the controller
    controller = FingerController()
    
    # Execute finger movement (0-100%)
    controller.execute_finger(50)  # Move to 50% flex
    
    # Optional: Set custom delay between flex and reset
    controller.set_reset_delay(2.0)  # 2 seconds delay
"""

import asyncio
import aiohttp
import platform
import sys
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, Callable
from functools import wraps

# Try to import aioconsole, install if not present
try:
    from aioconsole import ainput
except ImportError:
    print("Installing aioconsole for non-blocking input...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aioconsole"])
    from aioconsole import ainput


class FingerController:
    """
    Supernumerary Finger Controller
    
    A controller class for managing robotic finger servo operations through HTTP API.
    Provides automatic device discovery, network verification, and non-blocking control.
    
    Attributes:
        reset_delay (float): Time delay between flex and reset commands (default: 1.0 seconds)
        base_ip (str): IP address of the servo controller device
        base_url (str): Base URL for API endpoints
        required_ssid (str): Required WiFi network name (default: "AIMLAB")
    
    Example:
        >>> controller = FingerController()
        >>> controller.execute_finger(75)  # Flex finger to 75%
        >>> controller.execute_finger(0)   # Return to rest position
    """
    
    def __init__(self, reset_delay: float = 2.5, required_ssid: str = "AIMLAB", auto_discover: bool = True):
        """
        Initialize the Finger Controller.
        
        Args:
            reset_delay (float): Delay in seconds between flex and reset commands (default: 1.0)
            required_ssid (str): Required WiFi SSID for operation (default: "AIMLAB")
            auto_discover (bool): Automatically discover device on initialization (default: True)
        
        Raises:
            RuntimeError: If auto_discover is True and device cannot be found
        """
        # Configuration parameters
        self.reset_delay = reset_delay
        self.required_ssid = required_ssid
        self.base_ip = None
        self.base_url = None
        
        # Internal state management
        self._session = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._loop = None
        self._thread = None
        self._discovered = False
        
        # Start the async event loop in a background thread
        self._start_event_loop()
        
        # Auto-discover device if requested
        if auto_discover:
            print("Initializing Supernumerary Finger Controller...")
            if not self.discover_and_connect():
                raise RuntimeError("Failed to discover servo controller device. Please check network connection.")
            print(f"✓ Controller ready. Device at {self.base_ip}")
    
    def _start_event_loop(self):
        """
        Start the asyncio event loop in a background thread.
        This allows us to run async operations from synchronous code.
        """
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=run_loop, args=(self._loop,), daemon=True)
        self._thread.start()
        time.sleep(0.1)  # Give the loop time to start
    
    def _run_async(self, coro):
        """
        Run an async coroutine from synchronous code.
        
        Args:
            coro: Async coroutine to execute
            
        Returns:
            The result of the coroutine execution
        """
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=10)
    
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
        
        Performs network scanning to automatically find the servo controller
        on the current subnet. Updates base_ip and base_url on success.
        
        Returns:
            bool: True if device found and connected, False otherwise
        """
        try:
            # Run the async discovery process
            discovered_ip = self._run_async(self._discover_device_async())
            
            if discovered_ip:
                self.base_ip = discovered_ip
                self.base_url = f"http://{self.base_ip}"
                self._discovered = True
                return True
            return False
            
        except Exception as e:
            print(f"[ERROR] Discovery failed: {e}")
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
            RuntimeError: If device not discovered/connected
            
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
        
        # Check if device is discovered
        if not self._discovered or not self.base_ip:
            print("[ERROR] Device not discovered. Run discover_and_connect() first.")
            raise RuntimeError("Device not connected")
        
        # Convert to integer for API
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
            # Send flex command (non-blocking HTTP request)
            flex_url = f"{self.base_url}/testFlexPercent?percent={percentage}"
            
            # Use requests with very short timeout - we don't wait for response
            try:
                # Fire and forget - very short timeout
                response = requests.get(flex_url, timeout=0.5)
                print(f"→ Flex command sent: {percentage}%")
            except requests.Timeout:
                # This is expected - we're not waiting for the response
                print(f"→ Flex command sent: {percentage}% (non-blocking)")
            except Exception as e:
                print(f"[WARNING] Flex command may have failed: {e}")
            
            # Wait for the specified delay (hardware needs time to execute)
            time.sleep(self.reset_delay)
            
            # Send reset command
            reset_url = f"{self.base_url}/resetAll"
            try:
                # Fire and forget - very short timeout
                response = requests.get(reset_url, timeout=0.5)
                print(f"← Reset command sent")
            except requests.Timeout:
                # This is expected - we're not waiting for the response
                print(f"← Reset command sent (non-blocking)")
            except Exception as e:
                print(f"[WARNING] Reset command may have failed: {e}")
                
        except Exception as e:
            print(f"[ERROR] Command sequence failed: {e}")
    
    def verify_network(self) -> bool:
        """
        Verify that the system is connected to the correct WiFi network.
        
        Returns:
            bool: True if connected to required SSID, False otherwise
        """
        try:
            return self._run_async(self._verify_network_async())
        except Exception as e:
            print(f"[ERROR] Network verification failed: {e}")
            return False
    
    def ping_device(self) -> bool:
        """
        Ping the servo controller to check connectivity.
        
        Returns:
            bool: True if device responds to ping, False otherwise
        """
        if not self.base_ip:
            print("[ERROR] No device IP configured")
            return False
            
        try:
            return self._run_async(self._ping_device_async())
        except Exception as e:
            print(f"[ERROR] Ping failed: {e}")
            return False
    
    def get_status(self) -> Optional[str]:
        """
        Get the current status of the servo controller.
        
        Returns:
            Optional[str]: Status string if successful, None otherwise
        """
        if not self.base_ip:
            print("[ERROR] No device IP configured")
            return None
            
        try:
            status_url = f"{self.base_url}/status"
            response = requests.get(status_url, timeout=2.0)
            if response.status_code == 200:
                return response.text
            return None
        except Exception as e:
            print(f"[ERROR] Failed to get status: {e}")
            return None
    
    def cleanup(self):
        """
        Clean up resources and close connections.
        
        Should be called when done using the controller, though
        not strictly necessary due to daemon threads.
        """
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._executor:
            self._executor.shutdown(wait=False)
        print("Controller cleaned up")
    
    # ============== ASYNC HELPER METHODS ==============
    # These methods contain the async logic from the original code
    
    async def _get_local_ip_and_subnet(self) -> Optional[tuple]:
        """
        Get the local IP address and subnet of the current machine.
        
        Returns:
            Optional[tuple]: (local_ip, subnet_prefix) or None if cannot determine
        """
        import socket
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1.0)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            parts = local_ip.split('.')
            subnet = f"{parts[0]}.{parts[1]}.{parts[2]}"
            
            return local_ip, subnet
        except:
            return None
    
    async def _check_device_status(self, ip: str) -> bool:
        """
        Check if a device at given IP is the servo controller.
        
        Args:
            ip: IP address to check
            
        Returns:
            bool: True if device responds with servo status
        """
        test_url = f"http://{ip}/status"
        
        timeout = aiohttp.ClientTimeout(total=0.5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(test_url) as response:
                    if response.status == 200:
                        text = await response.text()
                        if text.strip().startswith("Version"):
                            return True
            except:
                pass
        
        return False
    
    async def _discover_device_async(self) -> Optional[str]:
        """
        Scan the current network to find the servo controller device.
        
        Returns:
            Optional[str]: IP address of the device if found
        """
        print("Discovering servo controller on network...")
        
        # Get current network subnet
        network_info = await self._get_local_ip_and_subnet()
        
        if not network_info:
            print("[ERROR] Could not determine local network")
            return None
        
        local_ip, subnet = network_info
        print(f"Scanning subnet {subnet}.1-254 for servo controller...")
        
        # Create list of all possible IPs in subnet
        ips_to_check = [f"{subnet}.{i}" for i in range(1, 255)]
        
        # Check IPs concurrently in batches
        batch_size = 50
        found_devices = []
        
        for i in range(0, len(ips_to_check), batch_size):
            batch = ips_to_check[i:i+batch_size]
            tasks = [self._check_device_status(ip) for ip in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for ip, result in zip(batch, results):
                if isinstance(result, bool) and result:
                    found_devices.append(ip)
                    print(f"  ✓ Found servo controller at {ip}")
        
        if found_devices:
            selected_ip = found_devices[0]
            if len(found_devices) > 1:
                print(f"Note: Found {len(found_devices)} controllers, using {selected_ip}")
            return selected_ip
        
        print("[ERROR] No servo controller found on network")
        return None
    
    async def _get_current_ssid(self) -> Optional[str]:
        """Get current WiFi SSID."""
        current_platform = platform.system()
        
        try:
            if current_platform == "Darwin":  # macOS
                cmd = ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"]
            elif current_platform == "Windows":
                cmd = ["netsh", "wlan", "show", "interfaces"]
            elif current_platform == "Linux":
                cmd = ["iwgetid", "-r"]
            else:
                return None
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return None
            
            output = stdout.decode('utf-8', errors='ignore')
            
            if current_platform == "Darwin":
                for line in output.split('\n'):
                    if 'SSID' in line and 'BSSID' not in line:
                        return line.split(':')[1].strip()
            elif current_platform == "Windows":
                for line in output.split('\n'):
                    if 'SSID' in line and 'BSSID' not in line:
                        return line.split(':')[1].strip()
            elif current_platform == "Linux":
                if proc.returncode == 0:
                    return output.strip()
                    
        except Exception:
            pass
        
        return None
    
    async def _verify_network_async(self) -> bool:
        """Check if connected to required network."""
        current_ssid = await self._get_current_ssid()
        if current_ssid == self.required_ssid:
            return True
        else:
            print(f"[ERROR] Not connected to {self.required_ssid} (current: {current_ssid})")
            return False
    
    async def _ping_device_async(self) -> bool:
        """Ping the device to check if it's reachable."""
        if not self.base_ip:
            return False
        
        system = platform.system()
        
        if system == "Windows":
            cmd = ["ping", "-n", "1", "-w", "1000", self.base_ip]
        else:  # macOS and Linux
            cmd = ["ping", "-c", "1", "-W", "1", self.base_ip]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
                return proc.returncode == 0
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return False
                
        except Exception:
            return False


# ============== MODULE-LEVEL CONVENIENCE FUNCTIONS ==============

# Global controller instance for simple usage
_global_controller = None


def initialize(reset_delay: float = 1.0, required_ssid: str = "AIMLAB") -> FingerController:
    """
    Initialize the global finger controller.
    
    This is a convenience function for simple use cases where you don't
    need multiple controller instances.
    
    Args:
        reset_delay (float): Delay between flex and reset (default: 1.0)
        required_ssid (str): Required WiFi network (default: "AIMLAB")
        
    Returns:
        FingerController: The initialized controller instance
        
    Example:
        >>> import finger_controller
        >>> finger_controller.initialize()
        >>> finger_controller.execute_finger(50)
    """
    global _global_controller
    _global_controller = FingerController(reset_delay, required_ssid)
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
    """
    print("=" * 60)
    print("Supernumerary Finger Controller - Demo Mode")
    print("=" * 60)
    
    try:
        # Create controller instance
        controller = FingerController(reset_delay=1.5)
        
        print("\nTesting finger movements...")
        print("-" * 40)
        
        # Test sequence
        test_sequence = [
            (25, "Light flex"),
            (50, "Medium flex"),
            (75, "Strong flex"),
            (100, "Full flex"),
            (0, "Rest position")
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