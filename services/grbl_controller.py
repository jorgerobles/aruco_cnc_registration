"""
Example GRBLController class refactored to use EventBroker
This shows how to apply the same pattern to other components
"""

import serial
import time
import threading
from typing import List, Tuple, Optional
from services.event_broker import EventBroker, EventPublisher, GRBLEvents


class GRBLController(EventPublisher):
    """GRBL Controller with EventBroker integration"""

    def __init__(self, event_broker: EventBroker = None):
        super().__init__(event_broker)

        self.serial_connection = None
        self.is_connected = False
        self.current_position = [0.0, 0.0, 0.0]  # X, Y, Z
        self.current_status = "Unknown"

        # Response handling
        self._response_buffer = []
        self._response_lock = threading.Lock()
        self._read_thread = None
        self._running = False

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect to GRBL controller"""
        try:
            self.serial_connection = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # Wait for GRBL to initialize

            # Test connection
            response = self.send_command("$")
            if response and any("$" in line for line in response):
                self.is_connected = True
                self._start_read_thread()
                self.emit(GRBLEvents.CONNECTED, True)
                return True
            else:
                self.serial_connection.close()
                self.serial_connection = None
                self.emit(GRBLEvents.CONNECTED, False)
                return False

        except Exception as e:
            error_msg = f"Failed to connect to GRBL on {port}: {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            self.emit(GRBLEvents.CONNECTED, False)
            return False

    def disconnect(self):
        """Disconnect from GRBL controller"""
        self._running = False

        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=1)

        if self.serial_connection:
            self.serial_connection.close()
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
                    line = self.serial_connection.readline().decode().strip()
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

    def send_command(self, command: str) -> List[str]:
        """Send command to GRBL and wait for response"""
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

            # Wait for response
            timeout = time.time() + 5.0  # 5 second timeout
            responses = []

            while time.time() < timeout:
                with self._response_lock:
                    if self._response_buffer:
                        response = self._response_buffer.pop(0)
                        responses.append(response)

                        # Check for completion
                        if response in ['ok', 'error'] or response.startswith('error:'):
                            break

                time.sleep(0.01)

            return responses

        except Exception as e:
            error_msg = f"Error sending command '{command}': {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            raise

    def get_position(self) -> List[float]:
        """Get current machine position"""
        try:
            # Request status update
            self.send_command("?")
            return self.current_position.copy()
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Error getting position: {e}")
            return [0.0, 0.0, 0.0]

    def get_status(self) -> str:
        """Get current machine status"""
        try:
            # Request status update
            self.send_command("?")
            return self.current_status
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Error getting status: {e}")
            return "Unknown"

    def home(self) -> bool:
        """Home all axes"""
        try:
            responses = self.send_command("$H")
            success = any("ok" in response for response in responses)
            if success:
                # Position will be updated via status responses
                pass
            return success
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Homing failed: {e}")
            return False

    def move_to(self, x: float = None, y: float = None, z: float = None,
                feed_rate: float = None) -> bool:
        """Move to specified coordinates"""
        try:
            # Build G-code command
            cmd_parts = ["G1"]

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
                time.sleep(1)  # Wait for reset

                # Clear buffers
                with self._response_lock:
                    self._response_buffer.clear()

                return True
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Reset failed: {e}")
            return False

    def emergency_stop(self) -> bool:
        """Emergency stop (feed hold)"""
        try:
            if self.serial_connection:
                # Send ! (feed hold)
                self.serial_connection.write(b'!')
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
                return True
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Resume failed: {e}")
            return False