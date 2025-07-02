"""
Enhanced GRBL Controller with asynchronous command buffer system
FIXED: Eliminated duplicate event emissions and improved logging
Clean separation of responsibilities - GRBL handles all its own filtering
"""

import serial
import time
import threading
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
from concurrent.futures import Future
from services.event_broker import event_aware, event_handler, EventPriority
from services.events import GRBLEvents


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

        # Internal logging control - GRBL handles its own filtering
        self._debug_enabled = True
        self._log_status_queries = False      # Don't log routine ? commands
        self._log_position_updates = False    # Don't log frequent position changes
        self._log_routine_responses = False   # Don't log routine ok/error
        self._log_buffer_operations = False   # Don't log buffer add/remove
        self._log_command_flow = True         # Log important command flow

        # Event emission control
        self._last_emitted_events = {}
        self._event_debounce_time = 0.1  # 100ms debounce for events
        self._emit_lock = threading.Lock()

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

    def _should_log_message(self, message: str, message_type: str) -> bool:
        """GRBL controller decides what should be logged - not the debug panel"""
        if not self._debug_enabled:
            return False

        message_lower = message.lower()

        # Filter out routine status queries
        if message_type == 'status_query' and not self._log_status_queries:
            if '?' in message or message.startswith('<'):
                return False

        # Filter out routine responses
        if message_type == 'routine_response' and not self._log_routine_responses:
            if message_lower.strip() in ['ok', 'error']:
                return False

        # Filter out buffer operations
        if message_type == 'buffer_operation' and not self._log_buffer_operations:
            return False

        # Filter out frequent position updates
        if message_type == 'position_update' and not self._log_position_updates:
            return False

        return True

    def _log_internal(self, message: str, message_type: str = 'general'):
        """Internal logging with GRBL's own filtering - FIXED: Use correct event type"""
        if self._should_log_message(message, message_type):
            # FIXED: Use proper event type mapping instead of always using ERROR
            event_type = self._get_event_type_for_message(message_type)
            self._emit_single_event(event_type, message, f"{message_type}_{message[:30]}")

    def _get_event_type_for_message(self, message_type: str) -> str:
        """Map message types to appropriate event types"""
        # Map internal message types to proper GRBL events
        if message_type in ['error', 'timeout']:
            return GRBLEvents.ERROR
        elif message_type == 'command_flow':
            return GRBLEvents.COMMAND_SENT  # Or create a dedicated debug event
        elif message_type in ['general', 'buffer_operation', 'position_update', 'routine_response', 'status_query']:
            # Create a dedicated debug event instead of misusing ERROR
            return "grbl.debug_info"  # This should be added to GRBLEvents
        else:
            return GRBLEvents.ERROR  # Default fallback

    def _emit_single_event(self, event_type: str, data: Any = None, debounce_key: str = None):
        """Emit a single event with debouncing - replaces _emit_debounced"""
        with self._emit_lock:
            current_time = time.time()

            # Create a unique key for this event
            if debounce_key is None:
                debounce_key = f"{event_type}_{str(data)[:50]}"

            # Check if we recently emitted this event
            if debounce_key in self._last_emitted_events:
                last_time = self._last_emitted_events[debounce_key]
                if current_time - last_time < self._event_debounce_time:
                    return  # Skip duplicate emission

            # Emit the event ONLY ONCE
            if data is not None:
                self.emit(event_type, data)
            else:
                self.emit(event_type)

            # Update last emission time
            self._last_emitted_events[debounce_key] = current_time

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

            # GRBL decides what to log about buffer operations
            self._log_internal(
                f"Command queued: {entry.command} (ID: {entry.command_id[:8]})",
                'buffer_operation'
            )

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

                        # GRBL logs command flow only if enabled
                        if self._log_command_flow:
                            self._emit_single_event(
                                GRBLEvents.COMMAND_SENT,
                                pending_entry.command,
                                f"cmd_sent_{pending_entry.command_id}"
                            )

                    except Exception as e:
                        pending_entry.state = CommandState.ERROR
                        pending_entry.responses.append(f"Send error: {e}")
                        if pending_entry.future and not pending_entry.future.done():
                            pending_entry.future.set_exception(e)

                        # Log send errors (always important)
                        self._log_internal(f"Error sending command: {e}", 'error')

                # Check for timeouts
                self._check_command_timeouts()

                time.sleep(0.01)  # Small delay to prevent excessive CPU usage

            except Exception as e:
                if self._running:
                    self._log_internal(f"Error in command processor: {e}", 'error')
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

                    # Log timeouts (always important)
                    self._log_internal(timeout_msg, 'error')

    def _process_response(self, response: str):
        """Process incoming response and match to commands"""
        # Add to response buffer for other processing
        with self._response_lock:
            self._response_buffer.append(response)

        # GRBL decides what responses to emit based on content
        if not (response.startswith('<') and response.endswith('>')):  # Don't emit routine status
            if self._log_command_flow:
                self._emit_single_event(
                    GRBLEvents.RESPONSE_RECEIVED,
                    response,
                    f"response_{response[:30]}"  # Use first 30 chars as key
                )

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

                    # Log command completion only if it's significant
                    if not self._is_routine_command(entry.command):
                        self._log_internal(
                            f"Command completed: {entry.command} -> {response}",
                            'command_flow'
                        )
                    matched = True
                    break

            # Only log unmatched responses if they're not routine
            if not matched and not self._is_routine_response(response):
                self._log_internal(f"Unmatched response: {response}", 'general')

        # Parse status and feedback responses
        if response.startswith('<') and response.endswith('>'):
            self._parse_status_response(response)
        elif response.startswith('[') and response.endswith(']'):
            self._parse_feedback_response(response)

    def _is_routine_command(self, command: str) -> bool:
        """Check if command is routine (status query, etc.)"""
        return command.strip() in ['?', '$', '$$'] or command.startswith('$')

    def _is_routine_response(self, response: str) -> bool:
        """Check if response is routine"""
        return (response.startswith('<') or
                response.startswith('$') or
                response.strip() in ['ok', 'error'])

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect to GRBL controller with improved reliability"""
        try:
            # Connection attempt log (always important)
            self._log_internal(f"Attempting connection to {port}:{baudrate}", 'general')

            # Step 1: Open serial connection
            self.serial_connection = serial.Serial(port, baudrate, timeout=2)

            # Step 2: Wait for GRBL initialization and clear any startup messages
            self._log_internal("Waiting for GRBL initialization...", 'general')
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

                # Connection success (always important)
                self._emit_single_event(GRBLEvents.CONNECTED, True, "connection_success")
                self._log_internal("✅ GRBL connection successful!", 'general')
                return True
            else:
                # Connection test failed
                self.serial_connection.close()
                self.serial_connection = None
                self._log_internal("❌ GRBL communication test failed", 'error')
                self._emit_single_event(GRBLEvents.CONNECTED, False, "connection_failed")
                return False

        except serial.SerialException as e:
            error_msg = f"Serial connection failed: {e}"
            self._log_internal(error_msg, 'error')
            self._emit_single_event(GRBLEvents.CONNECTED, False, "connection_failed")
            if self.serial_connection:
                self.serial_connection.close()
                self.serial_connection = None
            return False
        except Exception as e:
            error_msg = f"Unexpected error connecting to GRBL on {port}: {e}"
            self._log_internal(error_msg, 'error')
            self._emit_single_event(GRBLEvents.CONNECTED, False, "connection_failed")
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
                    # Only log startup messages if debug enabled
                    if decoded.strip() and self._debug_enabled:
                        self._log_internal(f"Startup message: {repr(decoded.strip())}", 'general')
                else:
                    break
                time.sleep(0.1)

        except Exception as e:
            self._log_internal(f"Error clearing buffer: {e}", 'error')

    def _test_grbl_communication(self) -> bool:
        """Test GRBL communication using the new command system"""
        test_commands = [
            ('?', 'status_query'),
            ('$', 'settings_query'),
            ('$I', 'version_query'),
        ]

        for command, cmd_type in test_commands:
            try:
                self._log_internal(f"Testing {cmd_type}...", 'general')

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
                            self._log_internal(f"Test response: {line}", 'general')

                            if entry.matches_response(line):
                                self._log_internal(f"✅ {cmd_type} test successful", 'general')
                                return True

                            # Check for GRBL-specific patterns
                            if (line.startswith('<') and line.endswith('>')) or \
                               line.startswith('Grbl') or \
                               line == 'ok' or \
                               line.startswith('$') or \
                               line.startswith('['):
                                self._log_internal(f"✅ GRBL response detected: {line}", 'general')
                                return True

                    time.sleep(0.05)

            except Exception as e:
                self._log_internal(f"Test command error: {e}", 'error')
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
                    self._log_internal(f"Error reading responses: {e}", 'error')
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
            self._emit_single_event(GRBLEvents.DISCONNECTED, None, "disconnection")

    def set_debug_level(self,
                        debug_enabled: bool = True,
                        log_status_queries: bool = False,
                        log_position_updates: bool = False,
                        log_routine_responses: bool = False,
                        log_buffer_operations: bool = False,
                        log_command_flow: bool = True):
        """Configure GRBL's internal debug logging levels"""
        self._debug_enabled = debug_enabled
        self._log_status_queries = log_status_queries
        self._log_position_updates = log_position_updates
        self._log_routine_responses = log_routine_responses
        self._log_buffer_operations = log_buffer_operations
        self._log_command_flow = log_command_flow

        self._log_internal("GRBL debug settings updated", 'general')

    # ... (rest of the methods remain the same)

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
                self._log_internal(f"Command future error: {e}", 'error')
                return entry.responses if entry.responses else []

        except Exception as e:
            error_msg = f"Error sending command '{command}': {e}"
            self._log_internal(error_msg, 'error')
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
            self._log_internal(error_msg, 'error')
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

                # Emit realtime command (always important)
                if self._log_command_flow:
                    self._emit_single_event(
                        GRBLEvents.COMMAND_SENT,
                        f"{command} (realtime)",
                        f"realtime_{command}"
                    )
            else:
                raise ValueError(f"Not a real-time command: {command}")
        except Exception as e:
            error_msg = f"Error sending real-time command '{command}': {e}"
            self._log_internal(error_msg, 'error')
            raise

    def get_position(self) -> List[float]:
        """Get current machine position"""
        try:
            responses = self.send_command("?", custom_timeout=5.0)
            return self.current_position.copy()
        except Exception as e:
            self._log_internal(f"Error getting position: {e}", 'error')
            return [0.0, 0.0, 0.0]

    def get_status(self) -> str:
        """Get current machine status"""
        try:
            responses = self.send_command("?", custom_timeout=5.0)
            return self.current_status
        except Exception as e:
            self._log_internal(f"Error getting status: {e}", 'error')
            return "Unknown"

    def home(self) -> bool:
        """Home all axes"""
        try:
            responses = self.send_command("$H")
            success = any("ok" in response for response in responses)
            if not success and responses:
                for response in responses:
                    if "error" in response.lower():
                        self._log_internal(f"Homing error: {response}", 'error')
            return success
        except Exception as e:
            self._log_internal(f"Homing failed: {e}", 'error')
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
            self._log_internal(f"Move command failed: {e}", 'error')
            return False

    def move_relative(self, x: float = 0, y: float = 0, z: float = 0,
                      feed_rate: float = None) -> List[str]:
        """Move relative to current position using async command system"""
        try:
            # Single debug message for relative move start (only if command flow enabled)
            if self._log_command_flow:
                self._log_internal(
                    f"Starting relative move: X{x:+.3f} Y{y:+.3f} Z{z:+.3f}",
                    'command_flow'
                )

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
                    self._log_internal(f"Jog command {i+1} failed: {e}", 'error')
                    all_responses.append(f"error: {e}")

            # Single completion message (only if command flow enabled)
            if self._log_command_flow:
                self._log_internal(
                    f"Relative move completed with {len(all_responses)} responses",
                    'command_flow'
                )
            return all_responses

        except Exception as e:
            error_msg = f"Relative move failed: {e}"
            self._log_internal(error_msg, 'error')

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
            self._log_internal("Emergency stop sent", 'general')
            return True
        except Exception as e:
            self._log_internal(f"Emergency stop failed: {e}", 'error')
            return False

    def resume(self) -> bool:
        """Resume from feed hold"""
        try:
            self.send_realtime_command('~')
            self._log_internal("Resume sent", 'general')
            return True
        except Exception as e:
            self._log_internal(f"Resume failed: {e}", 'error')
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
            self._log_internal(f"Reset failed: {e}", 'error')
            return False

    def set_work_offset(self, position: List[float], coordinate_system: int = 1) -> List[str]:
        """Set work coordinate system offset"""
        try:
            if coordinate_system < 1 or coordinate_system > 6:
                raise ValueError("Coordinate system must be 1-6 (G54-G59)")

            # G10 L20 P1 X0 Y0 Z0 sets G54 work offset to current position
            # G10 L2 P1 X0 Y0 Z0 sets G54 work offset to specified coordinates
            command = f"G10 L2 P{coordinate_system} X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}"
            responses = self.send_command(command)

            self._log_internal(
                f"Work offset G5{3+coordinate_system} set to X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}",
                'general'
            )

            return responses
        except Exception as e:
            self._log_internal(f"Failed to set work offset: {e}", 'error')
            return [f"error: {e}"]

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
            'debug_settings': {
                'debug_enabled': self._debug_enabled,
                'log_status_queries': self._log_status_queries,
                'log_position_updates': self._log_position_updates,
                'log_routine_responses': self._log_routine_responses,
                'log_buffer_operations': self._log_buffer_operations,
                'log_command_flow': self._log_command_flow
            }
        }

    def _parse_status_response(self, response: str):
        """Parse real-time status response"""
        try:
            parts = response[1:-1].split('|')

            # Parse status
            old_status = self.current_status
            self.current_status = parts[0]

            if old_status != self.current_status:
                self._emit_single_event(
                    GRBLEvents.STATUS_CHANGED,
                    self.current_status,
                    f"status_{self.current_status}"
                )

            # Parse position
            for part in parts:
                if part.startswith('MPos:'):
                    coords = part[5:].split(',')
                    old_position = self.current_position.copy()
                    self.current_position = [float(x) for x in coords]

                    # Only emit position change if there's a significant change
                    if any(abs(old - new) > 0.001 for old, new in zip(old_position, self.current_position)):
                        if self._log_position_updates:
                            self._emit_single_event(
                                GRBLEvents.POSITION_CHANGED,
                                self.current_position.copy(),
                                f"pos_{self.current_position[0]:.1f}_{self.current_position[1]:.1f}_{self.current_position[2]:.1f}"
                            )
                        else:
                            # Always emit position changes for other components, just don't log them
                            # Use direct emit to avoid debouncing for position updates that other components need
                            self.emit(GRBLEvents.POSITION_CHANGED, self.current_position.copy())
                    break

        except Exception as e:
            self._log_internal(f"Error parsing status: {e}", 'error')

    def _parse_feedback_response(self, response: str):
        """Parse feedback messages like [MSG:...]"""
        # Most feedback messages don't need special handling
        # They're already captured in the response processing
        pass

    def cleanup_event_history(self):
        """Clean up old event emission history to prevent memory leaks"""
        with self._emit_lock:
            current_time = time.time()
            # Remove entries older than 10 seconds
            cutoff_time = current_time - 10.0

            self._last_emitted_events = {
                key: timestamp for key, timestamp in self._last_emitted_events.items()
                if timestamp > cutoff_time
            }

    def get_debug_settings(self) -> Dict[str, bool]:
        """Get current debug settings"""
        return {
            'debug_enabled': self._debug_enabled,
            'log_status_queries': self._log_status_queries,
            'log_position_updates': self._log_position_updates,
            'log_routine_responses': self._log_routine_responses,
            'log_buffer_operations': self._log_buffer_operations,
            'log_command_flow': self._log_command_flow
        }

    def enable_verbose_logging(self):
        """Enable all debug logging for troubleshooting"""
        self.set_debug_level(
            debug_enabled=True,
            log_status_queries=True,
            log_position_updates=True,
            log_routine_responses=True,
            log_buffer_operations=True,
            log_command_flow=True
        )

    def enable_quiet_logging(self):
        """Enable minimal logging (default settings)"""
        self.set_debug_level(
            debug_enabled=True,
            log_status_queries=False,
            log_position_updates=False,
            log_routine_responses=False,
            log_buffer_operations=False,
            log_command_flow=True
        )

    def disable_all_logging(self):
        """Disable all debug logging"""
        self.set_debug_level(debug_enabled=False)

    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def _on_connection_status(self, success: bool):
        """Handle connection status changes internally"""
        # Clean up event history on new connections
        if success:
            self.cleanup_event_history()

    @event_handler(GRBLEvents.ERROR, EventPriority.NORMAL)
    def _on_error(self, error_message: str):
        """Handle internal errors"""
        # This can be used for internal error processing if needed
        pass