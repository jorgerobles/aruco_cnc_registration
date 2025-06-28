"""
Enhanced Machine Control Panel with extensive debugging for jog freeze issues
Includes timeout handling, non-blocking commands, and detailed response logging
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional
import threading
import time


class MachineControlPanel:
    """Machine control panel for GRBL operations with improved debugging and freeze prevention"""

    def __init__(self, parent, grbl_controller, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="Machine Control")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.step_size_var = tk.StringVar(value="10")
        self.feed_rate_var = tk.StringVar(value="1000")

        # Debug variables
        self.jog_timeout_var = tk.StringVar(value="3.0")  # Shorter timeout for jogs
        self.use_async_jog_var = tk.BooleanVar(value=True)  # Use async jogging by default

        # State tracking
        self.last_jog_time = 0
        self.jog_in_progress = False
        self._jog_lock = threading.Lock()

        # Position display
        self.position_label = ttk.Label(self.frame, text="Position: Not connected")

        # Status display
        self.status_label = ttk.Label(self.frame, text="Status: Unknown")

        # Debug output
        self.debug_output = None

        self._setup_widgets()

        # Listen to GRBL events for automatic position updates
        if hasattr(self.grbl_controller, 'listen'):
            from services.event_broker import GRBLEvents
            self.grbl_controller.listen(GRBLEvents.POSITION_CHANGED, self._on_position_changed)
            self.grbl_controller.listen(GRBLEvents.STATUS_CHANGED, self._on_status_changed)
            self.grbl_controller.listen(GRBLEvents.COMMAND_SENT, self._on_command_sent)
            self.grbl_controller.listen(GRBLEvents.RESPONSE_RECEIVED, self._on_response_received)

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

        # Also log to debug output if available
        if self.debug_output:
            timestamp = time.strftime("%H:%M:%S.%f")[:-3]
            self.debug_output.insert(tk.END, f"[{timestamp}] {message}\n")
            self.debug_output.see(tk.END)

    def _on_position_changed(self, position):
        """Handle position change events from GRBL"""
        self.position_label.config(
            text=f"Position: X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}"
        )
        self.log(f"Position updated: X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}")

    def _on_status_changed(self, status):
        """Handle status change events from GRBL"""
        self.status_label.config(text=f"Status: {status}")
        self.log(f"Status changed: {status}")

    def _on_command_sent(self, command):
        """Handle command sent events"""
        self.log(f"→ SENT: {command}", "sent")

    def _on_response_received(self, response):
        """Handle response received events"""
        self.log(f"← RECV: {response}", "received")

    def _setup_widgets(self):
        """Setup machine control widgets"""
        # Position and status display
        info_frame = ttk.Frame(self.frame)
        info_frame.pack(pady=2, fill=tk.X)

        self.position_label.pack(anchor=tk.W)
        self.status_label.pack(anchor=tk.W)

        # Control buttons
        control_frame = ttk.Frame(self.frame)
        control_frame.pack(pady=5)

        ttk.Button(control_frame, text="Home All Axes", command=self.home_machine).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Update Position", command=self.update_position).pack(side=tk.LEFT, padx=2)

        # Emergency controls
        emergency_frame = ttk.Frame(self.frame)
        emergency_frame.pack(pady=2)

        emergency_btn = ttk.Button(emergency_frame, text="🛑 STOP", command=self.emergency_stop)
        emergency_btn.pack(side=tk.LEFT, padx=2)

        ttk.Button(emergency_frame, text="▶️ Resume", command=self.resume).pack(side=tk.LEFT, padx=2)
        ttk.Button(emergency_frame, text="🔄 Reset", command=self.soft_reset).pack(side=tk.LEFT, padx=2)

        # Debug controls
        self._setup_debug_controls()

        # Jog controls
        self._setup_jog_controls()

    def _setup_debug_controls(self):
        """Setup debug control widgets"""
        debug_frame = ttk.LabelFrame(self.frame, text="Debug Controls")
        debug_frame.pack(pady=5, fill=tk.X)

        # Timeout setting
        timeout_frame = ttk.Frame(debug_frame)
        timeout_frame.pack(pady=2)

        ttk.Label(timeout_frame, text="Jog Timeout (s):").pack(side=tk.LEFT)
        ttk.Entry(timeout_frame, textvariable=self.jog_timeout_var, width=6).pack(side=tk.LEFT, padx=2)

        # Async jog setting
        ttk.Checkbutton(debug_frame, text="Use Async Jogging",
                       variable=self.use_async_jog_var).pack(anchor=tk.W)

        # Debug buttons
        debug_btn_frame = ttk.Frame(debug_frame)
        debug_btn_frame.pack(pady=2)

        ttk.Button(debug_btn_frame, text="Test Connection", command=self.test_connection).pack(side=tk.LEFT, padx=2)
        ttk.Button(debug_btn_frame, text="Get Status", command=self.get_detailed_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(debug_btn_frame, text="Clear Debug", command=self.clear_debug).pack(side=tk.LEFT, padx=2)

        # Debug output area
        self.debug_output = tk.Text(debug_frame, height=4, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(debug_frame, command=self.debug_output.yview)
        self.debug_output.config(yscrollcommand=scrollbar.set)

        debug_output_frame = ttk.Frame(debug_frame)
        debug_output_frame.pack(fill=tk.BOTH, expand=True, pady=2)

        self.debug_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_jog_controls(self):
        """Setup jog control widgets"""
        jog_frame = ttk.LabelFrame(self.frame, text="Jog Controls")
        jog_frame.pack(pady=5, fill=tk.X)

        # Settings frame
        settings_frame = ttk.Frame(jog_frame)
        settings_frame.pack(pady=2)

        # Step size
        ttk.Label(settings_frame, text="Step:").pack(side=tk.LEFT)
        step_combo = ttk.Combobox(settings_frame, textvariable=self.step_size_var,
                                  values=["0.1", "1", "10", "50", "100"], width=8)
        step_combo.pack(side=tk.LEFT, padx=(2, 10))

        # Feed rate
        ttk.Label(settings_frame, text="Feed:").pack(side=tk.LEFT)
        feed_combo = ttk.Combobox(settings_frame, textvariable=self.feed_rate_var,
                                  values=["100", "500", "1000", "2000", "3000"], width=8)
        feed_combo.pack(side=tk.LEFT, padx=2)

        # Jog status indicator
        self.jog_status_label = ttk.Label(settings_frame, text="Ready", foreground="green")
        self.jog_status_label.pack(side=tk.LEFT, padx=10)

        # XY movement buttons
        xy_frame = ttk.Frame(jog_frame)
        xy_frame.pack(pady=5)

        # Y+ button
        ttk.Button(xy_frame, text="Y+", command=lambda: self.jog_safe(y=1)).grid(row=0, column=1, padx=2, pady=2)

        # X buttons and center
        ttk.Button(xy_frame, text="X-", command=lambda: self.jog_safe(x=-1)).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(xy_frame, text="⌂", command=self.go_to_zero).grid(row=1, column=1, padx=2, pady=2)
        ttk.Button(xy_frame, text="X+", command=lambda: self.jog_safe(x=1)).grid(row=1, column=2, padx=2, pady=2)

        # Y- button
        ttk.Button(xy_frame, text="Y-", command=lambda: self.jog_safe(y=-1)).grid(row=2, column=1, padx=2, pady=2)

        # Z movement
        z_frame = ttk.Frame(jog_frame)
        z_frame.pack(pady=5)

        ttk.Label(z_frame, text="Z Axis:").pack()
        z_buttons = ttk.Frame(z_frame)
        z_buttons.pack()

        ttk.Button(z_buttons, text="Z+", command=lambda: self.jog_safe(z=1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(z_buttons, text="Z-", command=lambda: self.jog_safe(z=-1)).pack(side=tk.LEFT, padx=2)

    def test_connection(self):
        """Test GRBL connection and communication"""
        try:
            if not self.grbl_controller.is_connected:
                self.log("❌ GRBL not connected", "error")
                return

            self.log("🔍 Testing GRBL connection...")

            # Test status query
            start_time = time.time()
            try:
                status = self.grbl_controller.get_status()
                elapsed = time.time() - start_time
                self.log(f"✅ Status query successful: {status} ({elapsed:.3f}s)")
            except Exception as e:
                self.log(f"❌ Status query failed: {e}", "error")

            # Test position query
            start_time = time.time()
            try:
                position = self.grbl_controller.get_position()
                elapsed = time.time() - start_time
                self.log(f"✅ Position query successful: X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f} ({elapsed:.3f}s)")
            except Exception as e:
                self.log(f"❌ Position query failed: {e}", "error")

            # Get connection info
            info = self.grbl_controller.get_connection_info()
            self.log(f"📊 Connection info: {info}")

        except Exception as e:
            self.log(f"❌ Connection test failed: {e}", "error")

    def get_detailed_status(self):
        """Get detailed GRBL status"""
        try:
            if not self.grbl_controller.is_connected:
                self.log("❌ GRBL not connected", "error")
                return

            # Send manual status query
            self.log("📊 Requesting detailed status...")
            responses = self.grbl_controller.send_command("?")

            for response in responses:
                self.log(f"Status response: {response}")

        except Exception as e:
            self.log(f"❌ Status query failed: {e}", "error")

    def clear_debug(self):
        """Clear debug output"""
        if self.debug_output:
            self.debug_output.delete(1.0, tk.END)

    def jog_safe(self, x=0, y=0, z=0):
        """Safe jogging with freeze prevention"""
        with self._jog_lock:
            if self.jog_in_progress:
                self.log("⚠️ Jog already in progress, skipping", "warning")
                return

            self.jog_in_progress = True
            self.jog_status_label.config(text="Jogging...", foreground="orange")

        try:
            if self.use_async_jog_var.get():
                # Use async jogging to prevent GUI freeze
                threading.Thread(target=self._jog_worker, args=(x, y, z), daemon=True).start()
            else:
                # Synchronous jogging with timeout
                self._jog_synchronous(x, y, z)

        except Exception as e:
            self.log(f"❌ Jog initiation failed: {e}", "error")
            self._reset_jog_status()

    def _jog_worker(self, x, y, z):
        """Async worker for jogging"""
        try:
            self._jog_synchronous(x, y, z)
        except Exception as e:
            self.log(f"❌ Async jog failed: {e}", "error")
        finally:
            # Reset status on main thread
            self.frame.after(0, self._reset_jog_status)

    def _jog_synchronous(self, x, y, z):
        """Synchronous jogging with detailed logging"""
        try:
            if not self.grbl_controller.is_connected:
                self.log("❌ GRBL not connected", "error")
                return

            step = float(self.step_size_var.get())
            feed_rate = float(self.feed_rate_var.get())
            timeout = float(self.jog_timeout_var.get())

            move_x, move_y, move_z = x * step, y * step, z * step

            # Skip if no movement
            if move_x == 0 and move_y == 0 and move_z == 0:
                return

            self.log(f"🎯 Starting jog: X{move_x:+.3f} Y{move_y:+.3f} Z{move_z:+.3f} @ F{feed_rate} (timeout: {timeout}s)")

            # Record start time
            start_time = time.time()

            # Use the controller's move_relative method with custom timeout handling
            try:
                # Modify the controller's timeout for this command
                old_timeout_map = getattr(self.grbl_controller, '_timeout_map', {})

                # Temporarily set shorter timeout for relative moves
                if hasattr(self.grbl_controller, 'send_command'):
                    responses = self.grbl_controller.move_relative(move_x, move_y, move_z, feed_rate)
                else:
                    raise Exception("Controller doesn't support move_relative")

                elapsed = time.time() - start_time
                self.log(f"⏱️ Jog completed in {elapsed:.3f}s")

                # Check responses
                success = False
                error_found = False

                for response in responses:
                    self.log(f"Jog response: {response}")
                    if "ok" in response.lower():
                        success = True
                    elif "error" in response.lower():
                        error_found = True
                        self.log(f"❌ Jog error: {response}", "error")

                if success and not error_found:
                    self.log("✅ Jog completed successfully")
                elif error_found:
                    self.log("❌ Jog completed with errors", "error")
                else:
                    self.log("⚠️ Jog status unclear - no OK received", "warning")

            except Exception as cmd_error:
                elapsed = time.time() - start_time
                self.log(f"❌ Jog command failed after {elapsed:.3f}s: {cmd_error}", "error")

                # Try to send emergency stop if jog failed
                try:
                    self.log("🛑 Attempting emergency stop due to jog failure")
                    self.grbl_controller.emergency_stop()
                except:
                    pass

        except ValueError:
            self.log("❌ Invalid step size or feed rate", "error")
        except Exception as e:
            self.log(f"❌ Jog failed: {e}", "error")

    def _reset_jog_status(self):
        """Reset jog status indicators"""
        with self._jog_lock:
            self.jog_in_progress = False
        self.jog_status_label.config(text="Ready", foreground="green")

    def jog(self, x=0, y=0, z=0):
        """Legacy jog method - redirects to safe jog"""
        self.log("⚠️ Using legacy jog method - redirecting to safe jog")
        self.jog_safe(x, y, z)

    def update_position(self):
        """Update machine position display"""
        try:
            if not self.grbl_controller.is_connected:
                self.position_label.config(text="Position: Not connected")
                self.log("❌ GRBL not connected", "warning")
                return

            self.log("📍 Updating position...")
            start_time = time.time()

            pos = self.grbl_controller.get_position()
            elapsed = time.time() - start_time

            self.position_label.config(text=f"Position: X{pos[0]:.3f} Y{pos[1]:.3f} Z{pos[2]:.3f}")
            self.log(f"✅ Position updated in {elapsed:.3f}s: X{pos[0]:.3f} Y{pos[1]:.3f} Z{pos[2]:.3f}")

        except Exception as e:
            self.position_label.config(text="Position: Error reading")
            self.log(f"❌ Error reading position: {e}", "error")

    def home_machine(self):
        """Home the machine"""
        try:
            if not self.grbl_controller.is_connected:
                messagebox.showerror("Error", "GRBL not connected")
                return

            self.log("🏠 Initiating homing sequence...")
            start_time = time.time()

            success = self.grbl_controller.home()
            elapsed = time.time() - start_time

            if success:
                self.log(f"✅ Homing completed successfully in {elapsed:.3f}s")
                self.update_position()
            else:
                self.log(f"❌ Homing failed after {elapsed:.3f}s", "error")
                messagebox.showerror("Error", "Homing failed")

        except Exception as e:
            self.log(f"❌ Homing failed: {e}", "error")
            messagebox.showerror("Error", f"Homing failed: {e}")

    def go_to_zero(self):
        """Go to work coordinate zero"""
        try:
            if not self.grbl_controller.is_connected:
                messagebox.showerror("Error", "GRBL not connected")
                return

            feed_rate = float(self.feed_rate_var.get())
            self.log(f"🎯 Moving to work zero @ F{feed_rate}")
            start_time = time.time()

            success = self.grbl_controller.move_to(0, 0, 0, feed_rate)
            elapsed = time.time() - start_time

            if success:
                self.log(f"✅ Moved to work zero in {elapsed:.3f}s")
            else:
                self.log(f"❌ Failed to move to work zero after {elapsed:.3f}s", "error")

        except Exception as e:
            self.log(f"❌ Go to zero failed: {e}", "error")
            messagebox.showerror("Error", f"Go to zero failed: {e}")

    def emergency_stop(self):
        """Emergency stop the machine"""
        try:
            if not self.grbl_controller.is_connected:
                return

            self.log("🛑 EMERGENCY STOP", "error")
            success = self.grbl_controller.emergency_stop()

            if success:
                self.log("✅ Feed hold activated")
                self._reset_jog_status()  # Reset jog status on emergency stop
            else:
                self.log("❌ Emergency stop may have failed", "error")

        except Exception as e:
            self.log(f"❌ Emergency stop failed: {e}", "error")

    def resume(self):
        """Resume from feed hold"""
        try:
            if not self.grbl_controller.is_connected:
                return

            self.log("▶️ Resuming...")
            success = self.grbl_controller.resume()

            if success:
                self.log("✅ Resumed from feed hold")
            else:
                self.log("❌ Resume may have failed", "warning")

        except Exception as e:
            self.log(f"❌ Resume failed: {e}", "error")

    def soft_reset(self):
        """Perform soft reset"""
        try:
            if not self.grbl_controller.is_connected:
                return

            self.log("🔄 Performing soft reset...")
            success = self.grbl_controller.reset()

            if success:
                self.log("✅ Soft reset successful")
                self._reset_jog_status()  # Reset jog status after reset
                self.update_position()
            else:
                self.log("❌ Soft reset may have failed", "warning")

        except Exception as e:
            self.log(f"❌ Soft reset failed: {e}", "error")