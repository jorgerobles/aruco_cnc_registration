"""
Enhanced GRBL Controller with asynchronous command buffer system
Uses command tracking and response matching for improved timeout handling
"""

import serial
import time
import threading
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
from concurrent.futures import Future
from services.event_broker import event_aware, event_handler, GRBLEvents, EventPriority


class CommandState(Enum):
    """Command execution states"""
    PENDING = auto()
    SENT = auto()
    ACKNOWLEDGED = auto()
    COMPLETED = auto()
    ERROR = auto()
    TIMEOUT = auto()


@dataclass
class CommandEntry:
    """Represents a command in the buffer with its metadata"""
    command_id: str
    command: str
    command_type: str
    sent_time: Optional[float] = None
    timeout_duration: float = 5.0
    state: CommandState = CommandState.PENDING
    responses: List[str] = field(default_factory=list)
    future: Optional[Future] = None
    expected_response_patterns: List[str] = field(default_factory=lambda: ['ok', 'error'])

    def is_expired(self) -> bool:
        """Check if command has timed out"""
        if self.sent_time is None:
            return False
        return time.time() - self.sent_time > self.timeout_duration

    def is_complete(self) -> bool:
        """Check if command has completed (successfully or with error)"""
        return self.state in [CommandState.COMPLETED, CommandState.ERROR, CommandState.TIMEOUT]

    def matches_response(self, response: str) -> bool:
        """Check if response indicates command completion"""
        response_lower = response.lower().strip()

        # Check for explicit completion patterns
        for pattern in self.expected_response_patterns:
            if pattern in response_lower:
                return True

        # Special cases for different command types
        if self.command_type == 'status_query' and response.startswith('<'):
            return True
        elif self.command_type == 'settings_query' and response.startswith('$'):
            return True
        elif self.command_type == 'version_query' and (response.startswith('[') or 'grbl' in response_lower):
            return True

        return False


@event_aware()
class GRBLController:
    """Enhanced GRBL Controller with asynchronous command buffer system"""

    def __init__(self):
        # Serial connection
        self.serial_connection = None
        self.is_connected = False
        self.current_position = [0.0, 0.0, 0.0]  # X, Y, Z
        self.current_status = "Unknown"

        # Threading
        self._read_thread = None
        self._command_processor_thread = None
        self._running = False

        # Command buffer system
        self._command_buffer: Dict[str, CommandEntry] = {}
        self._command_queue: List[str] = []  # Command IDs in order
        self._buffer_lock = threading.RLock()
        self._max_buffer_size = 50

        # Response processing
        self._response_buffer = []
        self._response_lock = threading.Lock()

        # Connection state
        self._grbl_detected = False
        self._initialization_complete = False

        # Command type configurations
        self._command_configs = {
            'homing': {
                'patterns': ['$H'],
                'timeout': 30.0,
                'expected_responses': ['ok', 'error'],
            },
            'move': {
                'patterns': ['G1', 'G0'],
                'timeout': 10.0,
                'expected_responses': ['ok', 'error'],
            },
            'jog': {
                'patterns': ['G91', '$J='],
                'timeout': 3.0,
                'expected_responses': ['ok', 'error'],
            },
            'status_query': {
                'patterns': ['?'],
                'timeout': 2.0,
                'expected_responses': ['<'],
            },
            'settings_query': {
                'patterns': ['$', '$$'],
                'timeout': 3.0,
                'expected_responses': ['$', 'ok'],
            },
            'version_query': {
                'patterns': ['$I'],
                'timeout': 3.0,
                'expected_responses': ['[', 'VER', 'OPT'],
            },
            'positioning_mode': {
                'patterns': ['G90', 'G91'],
                'timeout': 2.0,
                'expected_responses': ['ok', 'error'],
            },
            'emergency': {
                'patterns': ['!', '~', '\x18'],
                'timeout': 1.0,
                'expected_responses': [],  # Emergency commands don't always respond
            },
            'work_offset': {
                'patterns': ['G10'],
                'timeout': 5.0,
                'expected_responses': ['ok', 'error'],
            },
        }

    def _get_command_type(self, command: str) -> str:
        """Determine command type based on command string"""
        command_upper = command.upper().strip()

        for cmd_type, config in self._command_configs.items():
            for pattern in config['patterns']:
                if pattern in command_upper:
                    return cmd_type

        return 'generic'

    def _get_command_config(self, command_type: str) -> Dict[str, Any]:
        """Get configuration for command type"""
        return self._command_configs.get(command_type, {
            'timeout': 5.0,
            'expected_responses': ['ok', 'error']
        })

    def _create_command_entry(self, command: str, custom_timeout: Optional[float] = None) -> CommandEntry:
        """Create a new command entry for the buffer"""
        command_id = str(uuid.uuid4())
        command_type = self._get_command_type(command)
        config = self._get_command_config(command_type)

        timeout = custom_timeout or config['timeout']
        expected_responses = config['expected_responses']

        entry = CommandEntry(
            command_id=command_id,
            command=command.strip(),
            command_type=command_type,
            timeout_duration=timeout,
            expected_response_patterns=expected_responses,
            future=Future()
        )

        return entry

    def _add_command_to_buffer(self, entry: CommandEntry) -> str:
        """Add command to buffer and queue"""
        with self._buffer_lock:
            # Clean old completed commands if buffer is full
            if len(self._command_buffer) >= self._max_buffer_size:
                self._cleanup_completed_commands()

            self._command_buffer[entry.command_id] = entry
            self._command_queue.append(entry.command_id)

            self.emit(GRBLEvents.ERROR, f"Added command to buffer: {entry.command} (ID: {entry.command_id[:8]})")

        return entry.command_id

    def _cleanup_completed_commands(self):
        """Remove completed commands from buffer (called with buffer lock held)"""
        completed_ids = [
            cmd_id for cmd_id, entry in self._command_buffer.items()
            if entry.is_complete()
        ]

        for cmd_id in completed_ids[:10]:  # Remove up to 10 completed commands
            if cmd_id in self._command_buffer:
                del self._command_buffer[cmd_id]
            if cmd_id in self._command_queue:
                self._command_queue.remove(cmd_id)

    def _process_commands(self):
        """Background thread to process command queue"""
        while self._running:
            try:
                with self._buffer_lock:
                    # Find next pending command
                    pending_entry = None
                    for cmd_id in self._command_queue:
                        if cmd_id in self._command_buffer:
                            entry = self._command_buffer[cmd_id]
                            if entry.state == CommandState.PENDING:
                                pending_entry = entry
                                break

                if pending_entry and self.serial_connection:
                    # Send the command
                    try:
                        full_command = pending_entry.command + '\n'
                        self.serial_connection.write(full_command.encode())

                        # Update command state
                        pending_entry.sent_time = time.time()
                        pending_entry.state = CommandState.SENT

                        self.emit(GRBLEvents.COMMAND_SENT, pending_entry.command)
                        self.emit(GRBLEvents.ERROR, f"Sent command: {pending_entry.command} (ID: {pending_entry.command_id[:8]})")

                    except Exception as e:
                        pending_entry.state = CommandState.ERROR
                        pending_entry.responses.append(f"Send error: {e}")
                        if pending_entry.future and not pending_entry.future.done():
                            pending_entry.future.set_exception(e)
                        self.emit(GRBLEvents.ERROR, f"Error sending command: {e}")

                # Check for timeouts
                self._check_command_timeouts()

                time.sleep(0.01)  # Small delay to prevent excessive CPU usage

            except Exception as e:
                if self._running:
                    self.emit(GRBLEvents.ERROR, f"Error in command processor: {e}")
                break

    def _check_command_timeouts(self):
        """Check for and handle command timeouts"""
        with self._buffer_lock:
            current_time = time.time()

            for entry in list(self._command_buffer.values()):
                if entry.state == CommandState.SENT and entry.is_expired():
                    entry.state = CommandState.TIMEOUT
                    timeout_msg = f"Command timeout after {entry.timeout_duration}s: {entry.command}"
                    entry.responses.append(timeout_msg)

                    if entry.future and not entry.future.done():
                        entry.future.set_result(entry.responses)

                    self.emit(GRBLEvents.ERROR, timeout_msg)

    def _process_response(self, response: str):
        """Process incoming response and match to commands"""
        # Add to response buffer for other processing
        with self._response_lock:
            self._response_buffer.append(response)

        # Emit response event
        self.emit(GRBLEvents.RESPONSE_RECEIVED, response)

        # Try to match response to pending commands
        with self._buffer_lock:
            matched = False

            # Look for commands that might match this response
            for cmd_id in list(self._command_queue):
                if cmd_id not in self._command_buffer:
                    continue

                entry = self._command_buffer[cmd_id]

                # Only consider sent commands that haven't completed
                if entry.state != CommandState.SENT:
                    continue

                # Add response to command
                entry.responses.append(response)

                # Check if this response completes the command
                if entry.matches_response(response):
                    if 'error' in response.lower():
                        entry.state = CommandState.ERROR
                    else:
                        entry.state = CommandState.COMPLETED

                    # Complete the future
                    if entry.future and not entry.future.done():
                        entry.future.set_result(entry.responses)

                    self.emit(GRBLEvents.ERROR, f"Command completed: {entry.command} -> {response}")
                    matched = True
                    break

            if not matched:
                self.emit(GRBLEvents.ERROR, f"Unmatched response: {response}")

        # Parse status and feedback responses
        if response.startswith('<') and response.endswith('>'):
            self._parse_status_response(response)
        elif response.startswith('[') and response.endswith(']'):
            self._parse_feedback_response(response)

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

            # Step 3: Test GRBL communication
            if self._test_grbl_communication():
                # Step 4: Start background threads
                self._start_threads()

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
        """Test GRBL communication using the new command system"""
        test_commands = [
            ('?', 'status_query'),
            ('$', 'settings_query'),
            ('$I', 'version_query'),
        ]

        for command, cmd_type in test_commands:
            try:
                self.emit(GRBLEvents.ERROR, f"Testing {cmd_type}...")

                # Create test command entry
                entry = self._create_command_entry(command, custom_timeout=3.0)

                # Send directly for testing (bypass queue)
                self.serial_connection.write((command + '\n').encode())
                entry.sent_time = time.time()
                entry.state = CommandState.SENT

                # Wait for response
                timeout = time.time() + 3.0
                while time.time() < timeout:
                    if self.serial_connection.in_waiting:
                        line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            entry.responses.append(line)
                            self.emit(GRBLEvents.ERROR, f"Test response: {line}")

                            if entry.matches_response(line):
                                self.emit(GRBLEvents.ERROR, f"✅ {cmd_type} test successful")
                                return True

                            # Check for GRBL-specific patterns
                            if (line.startswith('<') and line.endswith('>')) or \
                               line.startswith('Grbl') or \
                               line == 'ok' or \
                               line.startswith('$') or \
                               line.startswith('['):
                                self.emit(GRBLEvents.ERROR, f"✅ GRBL response detected: {line}")
                                return True

                    time.sleep(0.05)

            except Exception as e:
                self.emit(GRBLEvents.ERROR, f"Test command error: {e}")
                continue

        return False

    def _start_threads(self):
        """Start background threads for response reading and command processing"""
        self._running = True

        # Start response reading thread
        self._read_thread = threading.Thread(target=self._read_responses, daemon=True)
        self._read_thread.start()

        # Start command processing thread
        self._command_processor_thread = threading.Thread(target=self._process_commands, daemon=True)
        self._command_processor_thread.start()

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

    def disconnect(self):
        """Disconnect from GRBL controller"""
        self._running = False
        self._grbl_detected = False
        self._initialization_complete = False

        # Wait for threads to finish
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=2)
        if self._command_processor_thread and self._command_processor_thread.is_alive():
            self._command_processor_thread.join(timeout=2)

        # Cancel pending futures
        with self._buffer_lock:
            for entry in self._command_buffer.values():
                if entry.future and not entry.future.done():
                    entry.future.cancel()

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

    def send_command(self, command: str, custom_timeout: Optional[float] = None) -> List[str]:
        """Send command to GRBL and wait for response using async buffer system"""
        if not self.is_connected or not self.serial_connection:
            raise Exception("GRBL not connected")

        try:
            # Create command entry
            entry = self._create_command_entry(command, custom_timeout)

            # Add to buffer
            command_id = self._add_command_to_buffer(entry)

            # Wait for completion using the future
            try:
                responses = entry.future.result(timeout=entry.timeout_duration + 1.0)
                return responses
            except Exception as e:
                self.emit(GRBLEvents.ERROR, f"Command future error: {e}")
                return entry.responses if entry.responses else []

        except Exception as e:
            error_msg = f"Error sending command '{command}': {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            raise

    def send_command_async(self, command: str, custom_timeout: Optional[float] = None) -> Future:
        """Send command asynchronously and return Future for response"""
        if not self.is_connected or not self.serial_connection:
            raise Exception("GRBL not connected")

        try:
            # Create command entry
            entry = self._create_command_entry(command, custom_timeout)

            # Add to buffer
            self._add_command_to_buffer(entry)

            # Return the future
            return entry.future

        except Exception as e:
            error_msg = f"Error sending async command '{command}': {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            raise

    def send_realtime_command(self, command: str) -> None:
        """Send real-time command without buffering (emergency commands)"""
        if not self.is_connected or not self.serial_connection:
            raise Exception("GRBL not connected")

        try:
            if command in ['!', '~'] or command == '\x18':
                # Send immediately without newline for real-time commands
                if command == '\x18':
                    self.serial_connection.write(b'\x18')
                else:
                    self.serial_connection.write(command.encode())
                self.emit(GRBLEvents.COMMAND_SENT, f"{command} (realtime)")
            else:
                raise ValueError(f"Not a real-time command: {command}")
        except Exception as e:
            error_msg = f"Error sending real-time command '{command}': {e}"
            self.emit(GRBLEvents.ERROR, error_msg)
            raise

    def get_position(self) -> List[float]:
        """Get current machine position"""
        try:
            responses = self.send_command("?", custom_timeout=5.0)
            return self.current_position.copy()
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Error getting position: {e}")
            return [0.0, 0.0, 0.0]

    def get_status(self) -> str:
        """Get current machine status"""
        try:
            responses = self.send_command("?", custom_timeout=5.0)
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
        """Move relative to current position using async command system"""
        try:
            self.emit(GRBLEvents.ERROR, f"Starting relative move: X{x:+.3f} Y{y:+.3f} Z{z:+.3f}")

            # Create futures for all commands
            futures = []

            # Set relative mode
            futures.append(self.send_command_async("G91"))

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
                cmd_parts.append("F1000")

            futures.append(self.send_command_async(" ".join(cmd_parts)))

            # Return to absolute mode
            futures.append(self.send_command_async("G90"))

            # Wait for all commands to complete
            all_responses = []
            for i, future in enumerate(futures):
                try:
                    responses = future.result(timeout=10.0)  # Overall timeout
                    all_responses.extend(responses)
                except Exception as e:
                    self.emit(GRBLEvents.ERROR, f"Jog command {i+1} failed: {e}")
                    all_responses.append(f"error: {e}")

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

    def emergency_stop(self) -> bool:
        """Emergency stop (feed hold)"""
        try:
            self.send_realtime_command('!')
            self.emit(GRBLEvents.ERROR, "Emergency stop sent")
            return True
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Emergency stop failed: {e}")
            return False

    def resume(self) -> bool:
        """Resume from feed hold"""
        try:
            self.send_realtime_command('~')
            self.emit(GRBLEvents.ERROR, "Resume sent")
            return True
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Resume failed: {e}")
            return False

    def reset(self) -> bool:
        """Soft reset GRBL"""
        try:
            self.send_realtime_command('\x18')
            time.sleep(2)  # Wait for reset

            # Clear command buffer
            with self._buffer_lock:
                for entry in self._command_buffer.values():
                    if entry.future and not entry.future.done():
                        entry.future.cancel()
                self._command_buffer.clear()
                self._command_queue.clear()

            # Re-establish communication
            time.sleep(1)
            return self._test_grbl_communication()
        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Reset failed: {e}")
            return False

    def get_buffer_status(self) -> Dict[str, Any]:
        """Get current buffer status for debugging"""
        with self._buffer_lock:
            status = {
                'total_commands': len(self._command_buffer),
                'pending': sum(1 for e in self._command_buffer.values() if e.state == CommandState.PENDING),
                'sent': sum(1 for e in self._command_buffer.values() if e.state == CommandState.SENT),
                'completed': sum(1 for e in self._command_buffer.values() if e.state == CommandState.COMPLETED),
                'error': sum(1 for e in self._command_buffer.values() if e.state == CommandState.ERROR),
                'timeout': sum(1 for e in self._command_buffer.values() if e.state == CommandState.TIMEOUT),
                'queue_length': len(self._command_queue)
            }
        return status

    def get_connection_info(self) -> dict:
        """Get detailed connection information for debugging"""
        buffer_status = self.get_buffer_status()

        return {
            'is_connected': self.is_connected,
            'grbl_detected': self._grbl_detected,
            'initialization_complete': self._initialization_complete,
            'current_status': self.current_status,
            'current_position': self.current_position.copy(),
            'serial_port': self.serial_connection.port if self.serial_connection else None,
            'baudrate': self.serial_connection.baudrate if self.serial_connection else None,
            'buffer_status': buffer_status,
        }

    def _parse_status_response(self, response: str):
        """Parse real-time status response"""
        try:
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

                    if any(abs(old - new) > 0.001 for old, new in zip(old_position, self.current_position)):
                        self.emit(GRBLEvents.POSITION_CHANGED, self.current_position.copy())
                    break

        except Exception as e:
            self.emit(GRBLEvents.ERROR, f"Error parsing status: {e}")

    def _parse_feedback_response(self, response: str):
        """Parse feedback messages like [MSG:...]"""
        pass

    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def _on_connection_status(self, success: bool):
        """Handle connection status changes internally"""
        pass

    @event_handler(GRBLEvents.ERROR, EventPriority.NORMAL)
    def _on_error(self, error_message: str):
        """Handle internal errors"""
        pass