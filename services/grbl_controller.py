"""
GRBL Controller - FIXED position reading issue
The problem was in get_position() method doing redundant parsing
Now it uses the already-parsed position from _parse_status()
"""

import time
from abc import ABC
from concurrent.futures import Future
from typing import List, Optional, Dict, Any

import serial

from services.event_broker import event_aware, event_handler, EventPriority
from services.grbl_interfaces import IGRBLStatus, IGRBLConnection, IGRBLMovement, IGRBLCommunication


class GRBLEvents:
    """GRBL event type constants"""

    # Connection events
    CONNECTED = "grbl.connected"
    DISCONNECTED = "grbl.disconnected"

    # Command events
    COMMAND_SENT = "grbl.command_sent"

    # Response events
    RESPONSE_RECEIVED = "grbl.response_received"

    # Status events
    STATUS_CHANGED = "grbl.status_changed"
    POSITION_CHANGED = "grbl.position_changed"
    HOMING_POSITION = "grbl.homing_position"

    # Error events
    ERROR = "grbl.error"

    # Debug events
    DEBUG_INFO = "grbl.debug_info"

@event_aware()
class GRBLController(IGRBLConnection, IGRBLStatus, IGRBLMovement, IGRBLCommunication):
    """GRBL Controller with FIXED position reading"""

    def __init__(self):
        # Connection state
        self.serial_connection = None
        self._is_connected = False
        self.current_position = [0.0, 0.0, 0.0]  # X, Y, Z
        self.current_status = "Unknown"

        # Position tracking
        self._position_last_updated = 0
        self._position_valid = False

        # Internal state
        self._grbl_detected = False
        self._initialization_complete = False

        # Debug settings
        self._debug_enabled = True
        self._log_status_queries = False
        self._log_position_updates = False
        self._log_routine_responses = False
        self._log_buffer_operations = False
        self._log_command_flow = True

        # Simple command tracking for async operations
        self._active_futures: Dict[str, Future] = {}

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect to GRBL controller"""
        try:
            self._log(f"Connecting to {port}:{baudrate}")

            # Open serial connection
            self.serial_connection = serial.Serial(port, baudrate, timeout=2)

            # Wait for GRBL startup
            time.sleep(2)
            self._clear_startup_messages()

            # Test communication
            if self._test_communication():
                self._is_connected = True
                self._grbl_detected = True
                self._initialization_complete = True

                # Get initial position - FIXED: Force position update
                self._force_position_update()

                self.emit(GRBLEvents.CONNECTED, True)
                self._log("✅ Connected successfully")
                return True
            else:
                self.serial_connection.close()
                self.serial_connection = None
                self._log("❌ Communication test failed")
                self.emit(GRBLEvents.CONNECTED, False)
                return False

        except Exception as e:
            self._log(f"❌ Connection failed: {e}")
            if self.serial_connection:
                try:
                    self.serial_connection.close()
                except:
                    pass
                self.serial_connection = None
            self.emit(GRBLEvents.CONNECTED, False)
            return False

    def disconnect(self):
        """Immediate disconnect - no threads to wait for"""
        self._log("Disconnecting...")

        was_connected = self._is_connected

        # Cancel any active futures
        for future in list(self._active_futures.values()):
            if not future.done():
                try:
                    future.set_exception(ConnectionError("Disconnected"))
                except:
                    future.cancel()
        self._active_futures.clear()

        # Close serial connection
        if self.serial_connection:
            try:
                self.serial_connection.close()
            except:
                pass
            self.serial_connection = None

        # Reset state
        self._is_connected = False
        self._grbl_detected = False
        self._initialization_complete = False
        self.current_position = [0.0, 0.0, 0.0]
        self.current_status = "Disconnected"
        self._position_valid = False

        if was_connected:
            self.emit(GRBLEvents.DISCONNECTED)
            self._log("✅ Disconnected")

    def get_position(self) -> List[float]:
        """Get current machine position - FIXED implementation"""
        if not self.is_connected:
            raise Exception("GRBL not connected")

        try:
            # Check if we have a recent valid position (within last 2 seconds)
            current_time = time.time()
            if (self._position_valid and
                (current_time - self._position_last_updated) < 2.0):
                return self.current_position.copy()

            # Need to update position
            self._force_position_update()

            if self._position_valid:
                return self.current_position.copy()
            else:
                raise Exception("Failed to get valid position from GRBL")

        except Exception as e:
            self._log(f"❌ Position read failed: {e}")
            raise Exception(f"Failed to read machine position: {e}")

    def _force_position_update(self):
        """Force position update by sending status query with enhanced logging"""
        try:
            self._log("🔄 Forcing position update...")

            # Clear any buffered input first
            if self.serial_connection and self.serial_connection.in_waiting:
                buffered = self.serial_connection.read(self.serial_connection.in_waiting)
                self._log(f"🧹 Cleared {len(buffered)} buffered bytes")

            # Send status query and process response
            responses = self._send_and_wait("?", 3.0)
            self._log(f"📥 Status query responses: {responses}")

            # Check if position was updated during the query
            if self._position_valid:
                self._log(f"✅ Position updated: X{self.current_position[0]:.3f} Y{self.current_position[1]:.3f} Z{self.current_position[2]:.3f}")

                # Double-check with a second query if the first one seemed successful
                try:
                    time.sleep(0.1)
                    confirmation_responses = self._send_and_wait("?", 2.0)
                    self._log(f"🔍 Confirmation query responses: {confirmation_responses}")

                    if self._position_valid:
                        self._log(f"✅ Position confirmed: X{self.current_position[0]:.3f} Y{self.current_position[1]:.3f} Z{self.current_position[2]:.3f}")
                    else:
                        self._log("⚠️ Position lost during confirmation")

                except Exception as e:
                    self._log(f"⚠️ Confirmation query failed: {e}")

            else:
                # Log all responses for debugging
                self._log("❌ Position not found in responses:")
                for i, response in enumerate(responses):
                    self._log(f"  Response {i}: '{response}' (len={len(response)})")

                # Try manual parsing as fallback
                self._manual_position_parse(responses)

                # If still no position, try one more query
                if not self._position_valid:
                    self._log("🔄 Retrying status query...")
                    time.sleep(0.2)
                    retry_responses = self._send_and_wait("?", 3.0)
                    self._log(f"📥 Retry responses: {retry_responses}")

                    if not self._position_valid:
                        self._log("❌ Still no valid position after retry")

        except Exception as e:
            self._log(f"❌ Force position update failed: {e}")
            raise

    def _manual_position_parse(self, responses: List[str]):
        """Manual fallback position parsing"""
        for response in responses:
            self._log(f"🔍 Manual parsing: {response}")

            if response.startswith('<') and response.endswith('>'):
                try:
                    # Remove < and > brackets
                    content = response[1:-1]
                    self._log(f"  Content: {content}")

                    # Split by |
                    parts = content.split('|')
                    self._log(f"  Parts: {parts}")

                    # Look for MPos or WPos
                    for part in parts:
                        self._log(f"  Checking part: {part}")

                        if part.startswith('MPos:') or part.startswith('WPos:'):
                            coords_str = part[5:]  # Remove 'MPos:' or 'WPos:'
                            self._log(f"  Coords string: {coords_str}")

                            try:
                                coords = [float(x.strip()) for x in coords_str.split(',')]
                                if len(coords) >= 3:
                                    self.current_position = coords[:3]
                                    self._position_valid = True
                                    self._position_last_updated = time.time()
                                    self._log(f"  ✅ Manual parse success: {self.current_position}")
                                    return
                            except ValueError as ve:
                                self._log(f"  ❌ Coord parse error: {ve}")

                except Exception as e:
                    self._log(f"  ❌ Manual parse error: {e}")

    def get_status(self) -> str:
        """Get current machine status"""
        try:
            self._update_position()  # Status query also updates position
            return self.current_status
        except:
            return "Unknown"

    def send_command(self, command: str, custom_timeout: Optional[float] = None) -> List[str]:
        """Send command synchronously and wait for response"""
        if not self._is_connected:
            raise Exception("GRBL not connected")

        timeout = custom_timeout or 5.0
        return self._send_and_wait(command, timeout)

    def send_command_async(self, command: str, custom_timeout: Optional[float] = None) -> Future:
        """Send command asynchronously"""
        if not self._is_connected:
            raise Exception("GRBL not connected")

        timeout = custom_timeout or 5.0
        future = Future()

        def execute():
            try:
                responses = self._send_and_wait(command, timeout)
                if not future.done():
                    future.set_result(responses)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            finally:
                # Clean up from tracking
                future_id = id(future)
                if future_id in self._active_futures:
                    del self._active_futures[future_id]

        # Track the future
        future_id = id(future)
        self._active_futures[future_id] = future

        return future

    def send_realtime_command(self, command: str) -> None:
        """Send real-time command (emergency commands)"""
        if not self._is_connected:
            raise Exception("GRBL not connected")

        if command in ['!', '~', '\x18']:
            if command == '\x18':
                self.serial_connection.write(b'\x18')
            else:
                self.serial_connection.write(command.encode())

            if self._log_command_flow:
                self.emit(GRBLEvents.COMMAND_SENT, f"{command} (realtime)")
        else:
            raise ValueError(f"Not a real-time command: {command}")

    def home(self) -> bool:
        """Home all axes"""
        try:
            responses = self.send_command("$H", 30.0)
            success = any("ok" in response.lower() for response in responses)
            if success:
                # Update position after homing
                time.sleep(1)
                self._update_position()

                # NEW: Emit homing position event
                self.emit(GRBLEvents.POSITION_CHANGED,self.current_position.copy())
                self.emit(GRBLEvents.HOMING_POSITION, {
                    'position': self.current_position.copy(),
                    'success': True,
                    'timestamp': time.time()
                })

            return success
        except Exception as e:
            self._log(f"Homing failed: {e}")

            # NEW: Emit homing failed event
            self.emit(GRBLEvents.HOMING_POSITION, {
                'position': None,
                'success': False,
                'error': str(e),
                'timestamp': time.time()
            })

            return False

    def move_to(self, x: float = None, y: float = None, z: float = None, feed_rate: float = None) -> bool:
        """Move to absolute coordinates with position tracking"""
        try:
            old_position = self.current_position.copy()
            self._log(f"🎯 Moving to absolute position from [{old_position[0]:.3f}, {old_position[1]:.3f}, {old_position[2]:.3f}]")

            cmd_parts = ["G90", "G1"]  # Absolute mode, linear move

            target_position = old_position.copy()
            if x is not None:
                cmd_parts.append(f"X{x:.3f}")
                target_position[0] = x
            if y is not None:
                cmd_parts.append(f"Y{y:.3f}")
                target_position[1] = y
            if z is not None:
                cmd_parts.append(f"Z{z:.3f}")
                target_position[2] = z
            if feed_rate is not None:
                cmd_parts.append(f"F{feed_rate:.0f}")

            command = " ".join(cmd_parts)
            self._log(f"📤 Sending move command: {command}")
            self._log(f"🎯 Target position: [{target_position[0]:.3f}, {target_position[1]:.3f}, {target_position[2]:.3f}]")

            responses = self.send_command(command, 15.0)
            self._log(f"📥 Move responses: {responses}")

            success = any("ok" in response.lower() for response in responses)
            self._log(f"✅ Move command success: {success}")

            if success:
                # Wait for movement to complete
                time.sleep(0.2)

                # Force position update
                self._log("🔄 Updating position after move...")
                self._force_position_update()

                new_position = self.current_position.copy()
                self._log(f"📍 Position after move: [{new_position[0]:.3f}, {new_position[1]:.3f}, {new_position[2]:.3f}]")

                # Validate position
                position_error = [
                    abs(new_position[i] - target_position[i]) for i in range(3)
                ]
                self._log(f"📊 Position error: [{position_error[0]:.3f}, {position_error[1]:.3f}, {position_error[2]:.3f}]")

                if all(error < 0.1 for error in position_error):
                    self._log("✅ Position updated correctly after move")
                else:
                    self._log("⚠️ Position doesn't match target")

                # Emit position changed event
                self.emit(GRBLEvents.POSITION_CHANGED, self.current_position.copy())

            return success

        except Exception as e:
            self._log(f"❌ Move failed: {e}")
            return False

    def jog_relative(self, x: float = 0, y: float = 0, z: float = 0, feed_rate: float = 1000) -> bool:
        """Simple relative jogging method with position tracking"""
        try:
            if x == 0 and y == 0 and z == 0:
                return True  # No movement needed

            # Store expected new position for validation
            old_position = self.current_position.copy()
            expected_position = [
                old_position[0] + x,
                old_position[1] + y,
                old_position[2] + z
            ]

            self._log(f"🎯 Jogging: {x:+.3f}, {y:+.3f}, {z:+.3f} from [{old_position[0]:.3f}, {old_position[1]:.3f}, {old_position[2]:.3f}]")
            self._log(f"🎯 Expected new position: [{expected_position[0]:.3f}, {expected_position[1]:.3f}, {expected_position[2]:.3f}]")

            # Build relative move command
            cmd_parts = ["G91", "G1"]  # Relative mode, linear move

            if x != 0:
                cmd_parts.append(f"X{x:.3f}")
            if y != 0:
                cmd_parts.append(f"Y{y:.3f}")
            if z != 0:
                cmd_parts.append(f"Z{z:.3f}")
            cmd_parts.append(f"F{feed_rate:.0f}")

            relative_command = " ".join(cmd_parts)
            self._log(f"📤 Sending jog command: {relative_command}")

            # Send the relative move command
            responses = self.send_command(relative_command, 10.0)
            self._log(f"📥 Jog responses: {responses}")

            # Return to absolute mode
            try:
                abs_responses = self.send_command("G90", 2.0)
                self._log(f"📥 Absolute mode responses: {abs_responses}")
            except Exception as e:
                self._log(f"⚠️ Failed to return to absolute mode: {e}")

            success = any("ok" in response.lower() for response in responses)
            self._log(f"✅ Jog command success: {success}")

            if success:
                # Wait a moment for movement to complete
                time.sleep(0.2)

                # Force position update with validation
                self._log("🔄 Updating position after jog...")
                old_pos_before_update = self.current_position.copy()

                self._force_position_update()

                new_position = self.current_position.copy()
                self._log(f"📍 Position after jog: [{new_position[0]:.3f}, {new_position[1]:.3f}, {new_position[2]:.3f}]")

                # Validate position change
                position_delta = [
                    new_position[0] - old_position[0],
                    new_position[1] - old_position[1],
                    new_position[2] - old_position[2]
                ]

                expected_delta = [x, y, z]
                delta_error = [
                    abs(position_delta[i] - expected_delta[i]) for i in range(3)
                ]

                self._log(f"📊 Expected delta: [{expected_delta[0]:+.3f}, {expected_delta[1]:+.3f}, {expected_delta[2]:+.3f}]")
                self._log(f"📊 Actual delta: [{position_delta[0]:+.3f}, {position_delta[1]:+.3f}, {position_delta[2]:+.3f}]")
                self._log(f"📊 Delta error: [{delta_error[0]:.3f}, {delta_error[1]:.3f}, {delta_error[2]:.3f}]")

                # Check if position updated as expected (within 0.1mm tolerance)
                if all(error < 0.1 for error in delta_error):
                    self._log("✅ Position updated correctly after jog")
                else:
                    self._log("⚠️ Position delta doesn't match expected movement")

                # Emit position changed event
                self.emit(GRBLEvents.POSITION_CHANGED, self.current_position.copy())

            return success

        except Exception as e:
            # Ensure we're back in absolute mode
            try:
                self.send_command("G90", 1.0)
            except:
                pass
            self._log(f"❌ Jog relative failed: {e}")
            return False

    def move_relative(self, x: float = 0, y: float = 0, z: float = 0, feed_rate: float = None) -> List[str]:
        """Move relative to current position"""
        try:
            # Use the jog_relative method
            success = self.jog_relative(x, y, z, feed_rate or 1000)
            if success:
                return ["ok"]
            else:
                return ["error: Move failed"]

        except Exception as e:
            return [f"error: {e}"]

    def emergency_stop(self) -> bool:
        """Emergency stop (feed hold)"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.send_realtime_command('!')
                self._log("Emergency stop sent")
                return True
            else:
                return False
        except Exception as e:
            self._log(f"Emergency stop failed: {e}")
            return False

    def resume(self) -> bool:
        """Resume from feed hold"""
        try:
            self.send_realtime_command('~')
            self._log("Resume sent")
            return True
        except Exception as e:
            self._log(f"Resume failed: {e}")
            return False

    def reset(self) -> bool:
        """Soft reset GRBL"""
        try:
            self.send_realtime_command('\x18')
            time.sleep(2)

            # Cancel active futures
            for future in list(self._active_futures.values()):
                if not future.done():
                    future.cancel()
            self._active_futures.clear()

            # Reset position tracking
            self._position_valid = False

            # Test communication after reset
            time.sleep(1)
            success = self._test_communication()
            if success:
                self._force_position_update()
            return success
        except Exception as e:
            self._log(f"Reset failed: {e}")
            return False

    def set_work_offset(self, position: List[float], coordinate_system: int = 1) -> List[str]:
        """Set work coordinate system offset"""
        try:
            if coordinate_system < 1 or coordinate_system > 6:
                raise ValueError("Coordinate system must be 1-6 (G54-G59)")

            command = f"G10 L2 P{coordinate_system} X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}"
            responses = self.send_command(command, 5.0)

            self._log(f"Work offset G5{3 + coordinate_system} set to {position}")
            return responses

        except Exception as e:
            self._log(f"Set work offset failed: {e}")
            return [f"error: {e}"]

    def get_buffer_status(self) -> Dict[str, Any]:
        """Get current buffer status"""
        return {
            'total_commands': 0,  # No persistent buffer
            'pending_futures': len(self._active_futures)
        }

    def get_connection_info(self) -> dict:
        """Get connection information"""
        return {
            'is_connected': self._is_connected,
            'grbl_detected': self._grbl_detected,
            'initialization_complete': self._initialization_complete,
            'current_status': self.current_status,
            'current_position': self.current_position.copy(),
            'position_valid': self._position_valid,
            'position_last_updated': self._position_last_updated,
            'serial_port': self.serial_connection.port if self.serial_connection else None,
            'baudrate': self.serial_connection.baudrate if self.serial_connection else None,
            'buffer_status': self.get_buffer_status(),
            'debug_settings': self.get_debug_settings()
        }

    def is_properly_disconnected(self) -> bool:
        """Check if properly disconnected"""
        return (not self._is_connected and
                not self._grbl_detected and
                not self._initialization_complete and
                self.serial_connection is None and
                len(self._active_futures) == 0)

    def get_disconnect_status(self) -> Dict[str, Any]:
        """Get disconnect status"""
        return {
            'is_connected': self._is_connected,
            'grbl_detected': self._grbl_detected,
            'initialization_complete': self._initialization_complete,
            'serial_connection_exists': self.serial_connection is not None,
            'serial_connection_open': (self.serial_connection.is_open if self.serial_connection else False),
            'pending_commands': len(self._active_futures),
            'current_status': self.current_status,
            'is_properly_disconnected': self.is_properly_disconnected()
        }

    def set_debug_level(self,
                        debug_enabled: bool = True,
                        log_status_queries: bool = False,
                        log_position_updates: bool = False,
                        log_routine_responses: bool = False,
                        log_buffer_operations: bool = False,
                        log_command_flow: bool = True):
        """Configure debug logging levels"""
        self._debug_enabled = debug_enabled
        self._log_status_queries = log_status_queries
        self._log_position_updates = log_position_updates
        self._log_routine_responses = log_routine_responses
        self._log_buffer_operations = log_buffer_operations
        self._log_command_flow = log_command_flow

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
        """Enable all debug logging"""
        self.set_debug_level(
            debug_enabled=True,
            log_status_queries=True,
            log_position_updates=True,
            log_routine_responses=True,
            log_buffer_operations=True,
            log_command_flow=True
        )

    def enable_quiet_logging(self):
        """Enable minimal logging"""
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

    # INTERNAL METHODS (private)

    def _update_position(self):
        """Update current position by querying GRBL"""
        try:
            # Check if position is recent enough
            current_time = time.time()
            if (self._position_valid and
                (current_time - self._position_last_updated) < 1.0):
                return  # Position is recent enough

            responses = self._send_and_wait("?", 2.0)
            # Position will be updated by _process_response during the query
        except Exception as e:
            self._log(f"Position update failed: {e}")

    def _send_and_wait(self, command: str, timeout: float) -> List[str]:
        """Send command and wait for responses"""
        if not self.serial_connection:
            raise Exception("No serial connection")

        try:
            # Send command
            full_command = command + '\n'
            self.serial_connection.write(full_command.encode())

            if self._log_command_flow:
                self.emit(GRBLEvents.COMMAND_SENT, command)

            # Collect responses
            responses = []
            start_time = time.time()

            while time.time() - start_time < timeout:
                if self.serial_connection.in_waiting:
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        responses.append(line)
                        self._process_response(line)

                        # Check if command is complete
                        if self._is_complete_response(command, line):
                            break
                else:
                    time.sleep(0.01)

            return responses

        except Exception as e:
            self._log(f"Send command error: {e}")
            raise

    def _is_complete_response(self, command: str, response: str) -> bool:
        """Check if response completes the command"""
        response_lower = response.lower().strip()

        # Standard completion responses
        if response_lower in ['ok', 'error']:
            return True

        # Status query completion
        if command.strip() == '?' and response.startswith('<') and response.endswith('>'):
            return True

        # Settings query completion
        if command.strip().startswith('$') and (response.startswith('$') or response_lower == 'ok'):
            return True

        return False

    def _process_response(self, response: str):
        """Process incoming response"""
        # Emit response event
        if self._log_command_flow and not (response.startswith('<') and response.endswith('>')):
            self.emit(GRBLEvents.RESPONSE_RECEIVED, response)

        # Parse status responses
        if response.startswith('<') and response.endswith('>'):
            self._parse_status(response)

    def _parse_status(self, response: str):
        """Parse status response - FIXED with better logging"""
        try:
            self._log(f"🔍 Parsing status: {response}")

            parts = response[1:-1].split('|')
            self._log(f"🔍 Status parts: {parts}")

            # Update status
            old_status = self.current_status
            self.current_status = parts[0]

            if old_status != self.current_status:
                self.emit(GRBLEvents.STATUS_CHANGED, self.current_status)

            # Update position - look for both MPos and WPos
            for part in parts:
                self._log(f"🔍 Checking part: {part}")

                if part.startswith('MPos:') or part.startswith('WPos:'):
                    coords_str = part[5:]  # Remove 'MPos:' or 'WPos:'
                    self._log(f"🔍 Found position string: {coords_str}")

                    try:
                        coords = [float(x.strip()) for x in coords_str.split(',')]
                        if len(coords) >= 3:
                            old_position = self.current_position.copy()
                            self.current_position = coords[:3]
                            self._position_valid = True
                            self._position_last_updated = time.time()

                            self._log(f"✅ Position parsed: {self.current_position}")

                            # Check for significant position change
                            if any(abs(old - new) > 0.001 for old, new in zip(old_position, self.current_position)):
                                if self._log_position_updates:
                                    self.emit(GRBLEvents.POSITION_CHANGED, self.current_position.copy())
                        else:
                            self._log(f"❌ Not enough coordinates: {len(coords)}")
                    except ValueError as ve:
                        self._log(f"❌ Failed to parse coordinates: {ve}")
                    break

        except Exception as e:
            self._log(f"❌ Status parse error: {e}")

    def _clear_startup_messages(self):
        """Clear GRBL startup messages"""
        try:
            self.serial_connection.reset_input_buffer()
            time.sleep(0.5)

            # Read any remaining startup messages
            timeout = time.time() + 1.0
            while time.time() < timeout:
                if self.serial_connection.in_waiting:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    if self._debug_enabled:
                        decoded = data.decode('utf-8', errors='ignore').strip()
                        if decoded:
                            self._log(f"Startup: {decoded}")
                else:
                    break
                time.sleep(0.1)

        except Exception as e:
            self._log(f"Clear startup error: {e}")

    def _test_communication(self) -> bool:
        """Test GRBL communication"""
        test_commands = ['?', '$', '$I']

        for command in test_commands:
            try:
                responses = self._send_and_wait(command, 3.0)

                for response in responses:
                    # Look for GRBL-specific responses
                    if (response.startswith('<') or
                            response.startswith('Grbl') or
                            response.startswith('$') or
                            response.startswith('[') or
                            response == 'ok'):
                        self._log(f"✅ GRBL detected: {response}")
                        return True

            except Exception as e:
                self._log(f"Test command '{command}' failed: {e}")
                continue

        return False

    def _log(self, message: str):
        """Internal logging"""
        if self._debug_enabled:
            self.emit(GRBLEvents.DEBUG_INFO, message)

    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def _on_connected(self, success: bool):
        """Handle connection events"""
        pass

    @event_handler(GRBLEvents.ERROR, EventPriority.NORMAL)
    def _on_error(self, error_message: str):
        """Handle error events"""
        pass

    def debug_position_status(self):
        """Debug method to check current position status"""
        try:
            self._log("🔍 === POSITION DEBUG STATUS ===")
            self._log(f"Connected: {self._is_connected}")
            self._log(f"Position valid: {self._position_valid}")
            self._log(f"Current position: {self.current_position}")
            self._log(f"Last updated: {getattr(self, '_position_last_updated', 'Never')}")

            if self._is_connected:
                current_time = time.time()
                age = current_time - getattr(self, '_position_last_updated', 0)
                self._log(f"Position age: {age:.2f} seconds")

                # Try a fresh status query
                self._log("🔄 Sending fresh status query for debug...")
                try:
                    responses = self._send_and_wait("?", 3.0)
                    self._log(f"📥 Fresh responses: {responses}")

                    for response in responses:
                        if response.startswith('<') and response.endswith('>'):
                            self._log(f"🔍 Detailed status parsing for: {response}")
                            content = response[1:-1]
                            parts = content.split('|')
                            for i, part in enumerate(parts):
                                self._log(f"  Part {i}: '{part}'")
                                if 'Pos:' in part:
                                    self._log(f"    >>> POSITION PART: '{part}'")

                except Exception as e:
                    self._log(f"❌ Debug query failed: {e}")

            self._log("🔍 === END POSITION DEBUG ===")

        except Exception as e:
            self._log(f"❌ Debug position status failed: {e}")

    def is_connected(self) -> bool:
        return self._is_connected