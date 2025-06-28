"""
Enhanced GRBL Controller with specific fixes for jog command timeouts
Addresses the freezing issue during jogging operations
"""

import serial
import time
import threading
from typing import List, Tuple, Optional
from services.event_broker import event_aware, event_handler, GRBLEvents, EventPriority


@event_aware()
class GRBLController:
    """Enhanced GRBL Controller with improved jog handling and timeout management"""

    def __init__(self):
        # Note: event broker is automatically injected by @event_aware decorator
        # self._event_broker, self.emit(), self.listen(), etc. are now available

        self.serial_connection = None
        self.is_connected = False
        self.current_position = [0.0, 0.0, 0.0]  # X, Y, Z
        self.current_status = "Unknown"

        # Response handling
        self._response_buffer = []
        self._response_lock = threading.Lock()
        self._read_thread = None
        self._running = False

        # Connection state
        self._grbl_detected = False
        self._initialization_complete = False

        # Enhanced timeout handling for different command types
        self._command_timeouts = {
            '$H': 30.0,      # Homing can take a while
            'G28': 30.0,     # Return to home
            '?': 1.0,        # Status queries are fast
            'G91': 2.0,      # Relative positioning mode
            'G90': 2.0,      # Absolute positioning mode
            'G1': 3.0,       # Linear moves (including jogs)
            '!': 0.5,        # Emergency stop
            '~': 0.5,        # Resume
            '\x18': 2.0,     # Soft reset
        }

        # Jog-specific settings
        self._jog_timeout = 3.0  # Default jog timeout
        self._max_jog_wait = 5.0  # Maximum time to wait for jog completion

    def set_jog_timeout(self, timeout: float):
        """Set custom timeout for jog operations"""
        self._jog_timeout = max(0.5, min(timeout, 10.0))  # Clamp between 0.5 and 10 seconds
        self.emit(GRBLEvents.ERROR, f"Jog timeout set to {self._jog_timeout}s")

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect to GRBL controller with improved reliability"""
        try:
            self.emit(GRBLEvents.ERROR, f"Attempting connection to {port}:{baudrate}")

            # Step 1: Open serial connection
            self.serial_connection = serial.Serial(port, baudrate, timeout=2)

            # Step 2: Wait for GRBL initialization and clear any startup messages
            self.emit(GRBLEvents.ERROR, "Waiting for GRBL initialization...")
            time.sleep(3)  # Increased wait time for GRBL startup

            # Clear any startup messages
            self._clear_serial_buffer()

            # Step 3: Test GRBL communication with multiple strategies
            if self._test_grbl_communication():
                # Step 4: Start response reading thread
                self._start_read_thread()

                # Step 5: Final verification
                self.is_connected = True
                self._grbl_detected = True
                self._initialization_complete = True

                self.emit(GRBLEvents.CONNECTED, True)
                self.emit(GRBLEvents.ERROR, "✅ GRBL connection successful!")
                return True
            else:
                # Connection test failed
                self.serial_connection.close()
                self.serial_connection = None
                self.emit(GRBLEvents.ERROR, "❌ GRBL communication test failed")
                self.emit(GRBLEvents.CONNECTED, False)
                return False

        except serial.SerialException as e:
            error_msg = f"Serial connection failed: {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            self.emit(GRBLEvents.CONNECTED, False)
            if self.serial_connection:
                self.serial_connection.close()
                self.serial_connection = None
            return False
        except Exception as e:
            error_msg = f"Unexpected error connecting to GRBL on {port}: {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            self.emit(GRBLEvents.CONNECTED, False)
            if self.serial_connection:
                self.serial_connection.close()
                self.serial_connection = None
            return False

    def _clear_serial_buffer(self):
        """Clear any pending data in serial buffers"""
        try:
            # Clear input buffer
            self.serial_connection.reset_input_buffer()

            # Read and discard any remaining startup messages
            timeout = time.time() + 2.0
            while time.time() < timeout:
                if self.serial_connection.in_waiting:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    decoded = data.decode('utf-8', errors='ignore')
                    self.emit(GRBLEvents.ERROR, f"Startup message: {repr(decoded.strip())}")
                else:
                    break
                time.sleep(0.1)

        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Error clearing buffer: {e}")

    def _test_grbl_communication(self) -> bool:
        """Test GRBL communication with multiple methods"""

        # Test 1: Simple newline/carriage return
        self.emit(GRBLEvents.ERROR, "Testing basic communication...")
        if self._test_command(b'\r\n', expected_responses=['ok', 'error', '$', '<']):
            return True

        # Test 2: Status query
        self.emit(GRBLEvents.ERROR, "Testing status query...")
        if self._test_command(b'?\r\n', expected_responses=['<']):
            return True

        # Test 3: Settings query
        self.emit(GRBLEvents.ERROR, "Testing settings query...")
        if self._test_command(b'$\r\n', expected_responses=['$']):
            return True

        # Test 4: Help command
        self.emit(GRBLEvents.ERROR, "Testing help command...")
        if self._test_command(b'$\r\n', expected_responses=['$'], timeout=3.0):
            return True

        # Test 5: Version query (for newer GRBL versions)
        self.emit(GRBLEvents.ERROR, "Testing version query...")
        if self._test_command(b'$I\r\n', expected_responses=['[', 'VER', 'OPT']):
            return True

        return False

    def _test_command(self, command: bytes, expected_responses: List[str], timeout: float = 2.0) -> bool:
        """Test a specific command and check for expected responses"""
        try:
            # Clear buffers first
            self.serial_connection.reset_input_buffer()

            # Send command
            self.serial_connection.write(command)
            self.emit(GRBLEvents.ERROR, f"Sent: {repr(command)}")

            # Wait for and collect responses
            end_time = time.time() + timeout
            all_responses = []

            while time.time() < end_time:
                if self.serial_connection.in_waiting:
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        all_responses.append(line)
                        self.emit(GRBLEvents.ERROR, f"Received: {repr(line)}")

                        # Check if this line contains any expected response
                        for expected in expected_responses:
                            if expected in line:
                                self.emit(GRBLEvents.ERROR, f"✅ Found expected response: {expected}")
                                return True

                        # Check for GRBL-specific patterns
                        if (line.startswith('<') and line.endswith('>')) or \
                           line.startswith('Grbl') or \
                           line == 'ok' or \
                           line.startswith(')') or \
                           line.startswith('['):
                            self.emit(GRBLEvents.ERROR, f"✅ GRBL response detected: {line}")
                            return True

                time.sleep(0.05)

            # Log all responses for debugging
            if all_responses:
                self.emit(GRBLEvents.ERROR, f"All responses: {all_responses}")
            else:
                self.emit(GRBLEvents.ERROR, "No responses received")

            return False

        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Command test error: {e}")
            return False

    def disconnect(self):
        """Disconnect from GRBL controller"""
        self._running = False
        self._grbl_detected = False
        self._initialization_complete = False

        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=2)

        if self.serial_connection:
            try:
                self.serial_connection.close()
            except:
                pass
            self.serial_connection = None

        was_connected = self.is_connected
        self.is_connected = False

        if was_connected:
            self.emit(GRBLEvents.DISCONNECTED)

    def _start_read_thread(self):
        """Start background thread for reading responses"""
        self._running = True
        self._read_thread = threading.Thread(target=self._read_responses, daemon=True)
        self._read_thread.start()

    def _read_responses(self):
        """Background thread to read GRBL responses"""
        while self._running and self.serial_connection:
            try:
                if self.serial_connection.in_waiting:
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._process_response(line)
                time.sleep(0.01)  # Small delay to prevent excessive CPU usage

            except Exception as e:
                if self._running:  # Only emit error if we're supposed to be running
                    self.emit(GRBLEvents.ERROR, f"Error reading responses: {e}")
                break

    def _process_response(self, response: str):
        """Process incoming response from GRBL"""
        with self._response_lock:
            self._response_buffer.append(response)

        # Emit response event
        self.emit(GRBLEvents.RESPONSE_RECEIVED, response)

        # Parse status responses
        if response.startswith('<') and response.endswith('>'):
            self._parse_status_response(response)
        elif response.startswith('[') and response.endswith(']'):
            self._parse_feedback_response(response)

    def _parse_status_response(self, response: str):
        """Parse real-time status response"""
        try:
            # Example: <Idle|MPos:0.000,0.000,0.000|FS:0,0>
            parts = response[1:-1].split('|')

            # Parse status
            old_status = self.current_status
            self.current_status = parts[0]

            if old_status != self.current_status:
                self.emit(GRBLEvents.STATUS_CHANGED, self.current_status)

            # Parse position
            for part in parts:
                if part.startswith('MPos:'):
                    coords = part[5:].split(',')
                    old_position = self.current_position.copy()
                    self.current_position = [float(x) for x in coords]

                    # Check if position changed significantly
                    if any(abs(old - new) > 0.001 for old, new in zip(old_position, self.current_position)):
                        self.emit(GRBLEvents.POSITION_CHANGED, self.current_position.copy())
                    break

        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Error parsing status: {e}")

    def _parse_feedback_response(self, response: str):
        """Parse feedback messages like [MSG:...]"""
        # Could emit specific events for different feedback types
        pass

    def _get_command_timeout(self, command: str) -> float:
        """Get timeout for specific command type"""
        command = command.strip().upper()

        # Check for exact matches first
        if command in self._command_timeouts:
            return self._command_timeouts[command]

        # Check for command prefixes
        for cmd_prefix, timeout in self._command_timeouts.items():
            if command.startswith(cmd_prefix):
                return timeout

        # For jog commands (G91 G1), use jog timeout
        if 'G91' in command and 'G1' in command:
            return self._jog_timeout

        # Default timeout
        return 5.0

    def send_command(self, command: str, custom_timeout: Optional[float] = None) -> List[str]:
        """Send command to GRBL and wait for response with improved timeout handling"""
        if not self.is_connected or not self.serial_connection:
            raise Exception("GRBL not connected")

        try:
            # Clear response buffer
            with self._response_lock:
                self._response_buffer.clear()

            # Send command
            full_command = command + '\n'
            self.serial_connection.write(full_command.encode())
            self.emit(GRBLEvents.COMMAND_SENT, command)

            # Get timeout for this command
            timeout_duration = custom_timeout or self._get_command_timeout(command)

            self.emit(GRBLEvents.ERROR, f"Waiting for response (timeout: {timeout_duration}s)")

            timeout = time.time() + timeout_duration
            responses = []

            while time.time() < timeout:
                with self._response_lock:
                    if self._response_buffer:
                        response = self._response_buffer.pop(0)
                        responses.append(response)

                        # Check for completion
                        if response in ['ok', 'error'] or response.startswith('error:'):
                            self.emit(GRBLEvents.ERROR, f"Command completed: {response}")
                            break

                        # For status queries, the response itself is the completion
                        if command == '?' and response.startswith('<'):
                            break

                time.sleep(0.01)

            if not responses:
                self.emit(GRBLEvents.ERROR, f"Command timeout after {timeout_duration}s: {command}")
                # Don't raise exception for timeout, just return empty list
                return []

            return responses

        except Exception as e:
            error_msg = f"Error sending command '{command}': {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            raise

    def send_command_async(self, command: str) -> None:
        """Send command without waiting for response (for real-time commands)"""
        if not self.is_connected or not self.serial_connection:
            raise Exception("GRBL not connected")

        try:
            full_command = command + '\n'
            self.serial_connection.write(full_command.encode())
            self.emit(GRBLEvents.COMMAND_SENT, f"{command} (async)")
        except Exception as e:
            error_msg = f"Error sending async command '{command}': {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            raise

    def get_position(self) -> List[float]:
        """Get current machine position with better error handling"""
        try:
            # If we have recent position data, use it
            if self._initialization_complete:
                # Request fresh status update
                responses = self.send_command("?", custom_timeout=2.0)
                # Position is updated via _parse_status_response
                return self.current_position.copy()
            else:
                # During initialization, try a simple approach
                return [0.0, 0.0, 0.0]
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Error getting position: {e}")
            return [0.0, 0.0, 0.0]

    def get_status(self) -> str:
        """Get current machine status"""
        try:
            # Request status update with short timeout
            responses = self.send_command("?", custom_timeout=2.0)
            return self.current_status
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Error getting status: {e}")
            return "Unknown"

    def home(self) -> bool:
        """Home all axes"""
        try:
            responses = self.send_command("$H")
            success = any("ok" in response for response in responses)
            if not success and responses:
                # Check for homing-related error messages
                for response in responses:
                    if "error" in response.lower():
                        self.emit(GRBLEvents.ERROR, f"Homing error: {response}")
            return success
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Homing failed: {e}")
            return False

    def move_to(self, x: float = None, y: float = None, z: float = None,
                feed_rate: float = None) -> bool:
        """Move to specified coordinates (absolute positioning)"""
        try:
            # Build G-code command for absolute positioning
            cmd_parts = ["G90", "G1"]  # G90 = absolute mode, G1 = linear move

            if x is not None:
                cmd_parts.append(f"X{x:.3f}")
            if y is not None:
                cmd_parts.append(f"Y{y:.3f}")
            if z is not None:
                cmd_parts.append(f"Z{z:.3f}")
            if feed_rate is not None:
                cmd_parts.append(f"F{feed_rate:.0f}")

            command = " ".join(cmd_parts)
            responses = self.send_command(command)

            return any("ok" in response for response in responses)

        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Move command failed: {e}")
            return False

    def move_relative(self, x: float = 0, y: float = 0, z: float = 0,
                      feed_rate: float = None) -> List[str]:
        """Move relative to current position (for jogging) with improved handling"""
        try:
            self.emit(GRBLEvents.ERROR, f"Starting relative move: X{x:+.3f} Y{y:+.3f} Z{z:+.3f}")

            # Build G-code commands for relative positioning
            commands = []

            # Set relative mode
            commands.append("G91")

            # Build movement command
            cmd_parts = ["G1"]
            if x != 0:
                cmd_parts.append(f"X{x:.3f}")
            if y != 0:
                cmd_parts.append(f"Y{y:.3f}")
            if z != 0:
                cmd_parts.append(f"Z{z:.3f}")
            if feed_rate is not None:
                cmd_parts.append(f"F{feed_rate:.0f}")
            else:
                # Default jog feed rate
                cmd_parts.append("F1000")

            commands.append(" ".join(cmd_parts))

            # Return to absolute mode
            commands.append("G90")

            all_responses = []

            # Send commands sequentially with custom timeout
            for i, command in enumerate(commands):
                self.emit(GRBLEvents.ERROR, f"Sending jog command {i+1}/{len(commands)}: {command}")

                # Use jog timeout for all jog-related commands
                responses = self.send_command(command, custom_timeout=self._jog_timeout)
                all_responses.extend(responses)

                # Check for errors after each command
                for response in responses:
                    if "error" in response.lower():
                        self.emit(GRBLEvents.ERROR, f"Jog command error: {response}")
                        # Still continue with remaining commands to ensure we return to absolute mode

            self.emit(GRBLEvents.ERROR, f"Relative move completed with {len(all_responses)} responses")
            return all_responses

        except Exception as e:
            error_msg = f"Relative move failed: {e}"
            self.emit(GRBLEvents.ERROR, error_msg)

            # Try to ensure we're back in absolute mode
            try:
                self.send_command("G90", custom_timeout=1.0)
            except:
                pass

            return [f"error: {error_msg}"]

    def move_relative_realtime(self, x: float = 0, y: float = 0, z: float = 0,
                               feed_rate: float = 1000) -> bool:
        """Alternative jog method using GRBL's real-time jog commands (if supported)"""
        try:
            # GRBL 1.1+ supports $J= commands for real-time jogging
            cmd_parts = ["$J=G91", "G1"]

            if x != 0:
                cmd_parts.append(f"X{x:.3f}")
            if y != 0:
                cmd_parts.append(f"Y{y:.3f}")
            if z != 0:
                cmd_parts.append(f"Z{z:.3f}")

            cmd_parts.append(f"F{feed_rate:.0f}")

            command = " ".join(cmd_parts)
            self.emit(GRBLEvents.ERROR, f"Sending real-time jog: {command}")

            # Send as async command since it's real-time
            self.send_command_async(command)
            return True

        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Real-time jog failed: {e}")
            return False

    def set_work_offset(self, coordinates: List[float], coordinate_system: int = 1) -> List[str]:
        """Set work coordinate system offset"""
        try:
            if not (1 <= coordinate_system <= 6):
                raise ValueError("Coordinate system must be 1-6 (G54-G59)")

            # G10 L20 P1 X0 Y0 Z0 (set G54 to current position)
            # G10 L2 P1 X10 Y10 Z0 (set G54 offset)

            cmd = f"G10 L2 P{coordinate_system}"
            if len(coordinates) > 0:
                cmd += f" X{coordinates[0]:.3f}"
            if len(coordinates) > 1:
                cmd += f" Y{coordinates[1]:.3f}"
            if len(coordinates) > 2:
                cmd += f" Z{coordinates[2]:.3f}"

            return self.send_command(cmd)

        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Set work offset failed: {e}")
            return []

    def reset(self) -> bool:
        """Soft reset GRBL"""
        try:
            if self.serial_connection:
                # Send Ctrl-X (0x18)
                self.serial_connection.write(b'\x18')
                time.sleep(2)  # Wait for reset

                # Clear buffers
                with self._response_lock:
                    self._response_buffer.clear()

                # Re-establish communication
                time.sleep(1)
                return self._test_grbl_communication()
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Reset failed: {e}")
            return False

    def emergency_stop(self) -> bool:
        """Emergency stop (feed hold)"""
        try:
            if self.serial_connection:
                # Send ! (feed hold)
                self.serial_connection.write(b'!')
                self.emit(GRBLEvents.ERROR, "Emergency stop sent")
                return True
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Emergency stop failed: {e}")
            return False

    def resume(self) -> bool:
        """Resume from feed hold"""
        try:
            if self.serial_connection:
                # Send ~ (cycle start/resume)
                self.serial_connection.write(b'~')
                self.emit(GRBLEvents.ERROR, "Resume sent")
                return True
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Resume failed: {e}")
            return False

    def get_connection_info(self) -> dict:
        """Get detailed connection information for debugging"""
        return {
            'is_connected': self.is_connected,
            'grbl_detected': self._grbl_detected,
            'initialization_complete': self._initialization_complete,
            'current_status': self.current_status,
            'current_position': self.current_position.copy(),
            'serial_port': self.serial_connection.port if self.serial_connection else None,
            'baudrate': self.serial_connection.baudrate if self.serial_connection else None,
            'jog_timeout': self._jog_timeout,
        }

    # Optional: Add event handlers if you want the controller to respond to its own events
    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def _on_connection_status(self, success: bool):
        """Handle connection status changes internally"""
        if success:
            # Controller connected, could trigger additional setup
            pass
        else:
            # Connection failed, could trigger cleanup
            pass

    @event_handler(GRBLEvents.ERROR, EventPriority.NORMAL)
    def _on_error(self, error_message: str):
        """Handle internal errors - could log to file, trigger recovery, etc."""
        # This is where you could add error logging, recovery logic, etc.
        pass