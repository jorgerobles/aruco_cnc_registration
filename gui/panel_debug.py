"""
Debug Panel - Comprehensive debug console and controls with event awareness
Handles all debug functionality including console, manual commands, and status displays
"""

import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Callable, Optional

from services.event_broker import (event_aware, event_handler, EventPriority,
                                   CameraEvents, GRBLEvents, RegistrationEvents, ApplicationEvents)


@event_aware()
class DebugPanel:
    """Debug console and controls panel for GRBL Camera Registration application"""

    def __init__(self, parent, grbl_controller, camera_manager, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.camera_manager = camera_manager
        self.logger = logger
        self.parent = parent

        # Debug state
        self.debug_enabled = True
        self.debug_text = None

        # Variables for controls
        self.debug_var = tk.BooleanVar(value=True)
        self.manual_cmd_var = tk.StringVar()

        self._setup_debug_panel()

    # Event handlers for all event types
    @event_handler(GRBLEvents.CONNECTED)
    def _on_grbl_connected(self, success: bool):
        """Handle GRBL connection events"""
        if success:
            self.log("GRBL: Connected successfully", "info")
        else:
            self.log("GRBL: Connection failed", "error")

    @event_handler(GRBLEvents.DISCONNECTED)
    def _on_grbl_disconnected(self):
        """Handle GRBL disconnection events"""
        self.log("GRBL: Disconnected", "info")

    @event_handler(GRBLEvents.STATUS_CHANGED)
    def _on_grbl_status_changed(self, status: str):
        """Handle GRBL status changes"""
        self.log(f"GRBL: Status changed to {status}", "info")

    @event_handler(GRBLEvents.POSITION_CHANGED)
    def _on_grbl_position_changed(self, position: list):
        """Handle GRBL position changes - filtered to avoid spam"""
        # Only log position changes occasionally to avoid spam
        if hasattr(self, '_last_position_log'):
            now = time.time()
            if now - self._last_position_log < 2.0:  # Log at most every 2 seconds
                return
        self._last_position_log = time.time()
        self.log(f"GRBL: Position X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}", "info")

    @event_handler(GRBLEvents.ERROR)
    def _on_grbl_error(self, error_message: str):
        """Handle GRBL errors with filtering"""
        self.log_grbl_event(error_message, "error")

    @event_handler(GRBLEvents.COMMAND_SENT)
    def _on_grbl_command_sent(self, command: str):
        """Handle GRBL commands being sent"""
        self.log(f"GRBL SENT: {command}", "sent")

    @event_handler(GRBLEvents.RESPONSE_RECEIVED)
    def _on_grbl_response_received(self, response: str):
        """Handle GRBL responses"""
        self.log(f"GRBL RECV: {response}", "received")

    @event_handler(CameraEvents.CONNECTED)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection events"""
        if success:
            self.log("Camera: Connected successfully", "info")
        else:
            self.log("Camera: Connection failed", "error")

    @event_handler(CameraEvents.DISCONNECTED)
    def _on_camera_disconnected(self):
        """Handle camera disconnection events"""
        self.log("Camera: Disconnected", "info")

    @event_handler(CameraEvents.ERROR)
    def _on_camera_error(self, error_message: str):
        """Handle camera errors"""
        self.log(f"Camera: {error_message}", "error")

    @event_handler(CameraEvents.CALIBRATION_LOADED)
    def _on_camera_calibrated(self, file_path: str):
        """Handle camera calibration loaded"""
        self.log(f"Camera: Calibration loaded from {file_path}", "info")

    @event_handler(RegistrationEvents.POINT_ADDED)
    def _on_registration_point_added(self, point_data: dict):
        """Handle registration point added"""
        point_index = point_data['point_index']
        total_points = point_data['total_points']
        machine_pos = point_data['machine_pos']
        self.log(f"Registration: Point {point_index + 1} added at X{machine_pos[0]:.3f} Y{machine_pos[1]:.3f} Z{machine_pos[2]:.3f}", "info")

    @event_handler(RegistrationEvents.COMPUTED)
    def _on_registration_computed(self, computation_data: dict):
        """Handle registration computation"""
        point_count = computation_data['point_count']
        error = computation_data['error']
        self.log(f"Registration: Computed with {point_count} points, RMS error: {error:.4f}", "info")

    @event_handler(RegistrationEvents.ERROR)
    def _on_registration_error(self, error_message: str):
        """Handle registration errors"""
        self.log(f"Registration: {error_message}", "error")

    @event_handler(ApplicationEvents.STARTUP)
    def _on_app_startup(self):
        """Handle application startup"""
        self.log("Application: Starting up", "info")

    @event_handler(ApplicationEvents.SHUTDOWN)
    def _on_app_shutdown(self):
        """Handle application shutdown"""
        self.log("Application: Shutting down", "info")

    def _setup_debug_panel(self):
        """Setup debug console panel with integrated debug controls"""
        # Create main frame for debug panel content
        main_debug_frame = ttk.Frame(self.parent)
        main_debug_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Console controls row (integrated into console frame)
        console_controls_frame = ttk.Frame(main_debug_frame)
        console_controls_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(console_controls_frame, text="Enable Debug",
                        variable=self.debug_var, command=self.toggle_debug).pack(side=tk.LEFT)

        ttk.Button(console_controls_frame, text="Clear Console",
                   command=self.clear_debug).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Button(console_controls_frame, text="Show Event Stats",
                   command=self.show_event_stats).pack(side=tk.LEFT, padx=(10, 0))

        # Debug text area with scrollbar
        self.debug_text = scrolledtext.ScrolledText(main_debug_frame, height=10, wrap=tk.WORD)
        self.debug_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Configure text tags for different message types
        self.debug_text.tag_configure("sent", foreground="blue")
        self.debug_text.tag_configure("received", foreground="green")
        self.debug_text.tag_configure("error", foreground="red")
        self.debug_text.tag_configure("info", foreground="gray")

        # Manual GRBL command section
        manual_cmd_frame = ttk.LabelFrame(main_debug_frame, text="Manual GRBL Command")
        manual_cmd_frame.pack(fill=tk.X, pady=5)

        # Command input row
        cmd_input_frame = ttk.Frame(manual_cmd_frame)
        cmd_input_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(cmd_input_frame, text="Command:").pack(side=tk.LEFT)

        cmd_entry = ttk.Entry(cmd_input_frame, textvariable=self.manual_cmd_var)
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        cmd_entry.bind('<Return>', self.send_manual_command)

        ttk.Button(cmd_input_frame, text="Send",
                   command=self.send_manual_command).pack(side=tk.RIGHT)

        # Quick command buttons
        quick_cmd_frame = ttk.Frame(manual_cmd_frame)
        quick_cmd_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Label(quick_cmd_frame, text="Quick:").pack(side=tk.LEFT)

        quick_commands = [
            ("?", "?"),  # Status query
            ("$$", "$$"),  # Settings
            ("$H", "$H"),  # Home
            ("G90", "G90"),  # Absolute positioning
            ("G91", "G91"),  # Relative positioning
            ("M3", "M3 S1000"),  # Spindle on
            ("M5", "M5")  # Spindle off
        ]

        for label, command in quick_commands:
            btn = ttk.Button(quick_cmd_frame, text=label, width=4,
                             command=lambda cmd=command: self.send_quick_command(cmd))
            btn.pack(side=tk.LEFT, padx=1)

        # Initialize with welcome message
        self.log("Debug Panel initialized", "info")

    def log(self, message: str, level: str = "info"):
        """Log message to debug console with safe initialization handling"""
        # Handle case where GUI is not fully initialized yet
        if not hasattr(self, 'debug_enabled') or self.debug_enabled is None:
            print(f"[{level.upper()}] {message}")  # Fallback to console
            return

        if self.debug_enabled and self.debug_text:
            timestamp = time.strftime("%H:%M:%S")
            tag_map = {
                "info": "info",
                "error": "error",
                "sent": "sent",
                "received": "received",
                "warning": "error"  # Map warning to error color
            }
            tag = tag_map.get(level, "info")
            self.debug_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
            self.debug_text.see(tk.END)
        else:
            # Fallback to console if debug_text is not ready
            print(f"[{level.upper()}] {message}")

        # NOTE: Removed external logger call to prevent circular dependency
        # The debug panel should be the final destination for log messages

    def toggle_debug(self):
        """Toggle debug mode on/off"""
        self.debug_enabled = self.debug_var.get()
        if self.debug_enabled:
            self.log("Debug mode enabled", "info")
        else:
            self.log("Debug mode disabled", "info")

    def clear_debug(self):
        """Clear debug console"""
        if self.debug_text:
            self.debug_text.delete(1.0, tk.END)
            self.log("Debug console cleared", "info")

    def show_event_stats(self):
        """Show event broker statistics"""
        try:
            if not hasattr(self, '_event_broker') or self._event_broker is None:
                self.log("Event broker not available", "warning")
                return

            event_types = self._event_broker.list_event_types()
            stats = []
            for event_type in event_types:
                count = self._event_broker.get_subscriber_count(event_type)
                stats.append(f"{event_type}: {count} subscribers")

            if stats:
                self.log("Event Statistics:")
                for stat in stats:
                    self.log(f"  {stat}")
            else:
                self.log("No active event subscriptions")
        except Exception as e:
            self.log(f"Error getting event stats: {e}", "error")

    def send_manual_command(self, event=None):
        """Send manual GRBL command"""
        command = self.manual_cmd_var.get().strip()
        if not command:
            return

        try:
            if not self.grbl_controller.is_connected:
                self.log("GRBL not connected", "error")
                return

            # Manual commands don't go through events, log directly
            self.log(f"Manual SENT: {command}", "sent")
            response = self.grbl_controller.send_command(command)
            for line in response:
                self.log(f"Manual RECV: {line}", "received")
            self.manual_cmd_var.set("")  # Clear entry
        except Exception as e:
            self.log(f"Manual command error: {e}", "error")

    def send_quick_command(self, command):
        """Send a quick command by setting it in the entry field"""
        self.manual_cmd_var.set(command)
        self.send_manual_command()

    def get_debug_enabled(self):
        """Get current debug enabled state"""
        return self.debug_enabled

    def set_debug_enabled(self, enabled: bool):
        """Set debug enabled state"""
        self.debug_enabled = enabled
        self.debug_var.set(enabled)

    def is_ready(self):
        """Check if debug panel is ready for logging"""
        return self.debug_text is not None

    def log_grbl_event(self, message: str, level: str = "info"):
        """Log GRBL-specific events with filtering"""
        # Filter debug messages from actual errors for GRBL events
        if "✅" in message or "Testing" in message or "Sent:" in message or "Received:" in message:
            # These are debug/info messages from the improved controller
            self.log(f"GRBL Debug: {message}", "info")
        else:
            # These are actual errors or important messages
            self.log(f"GRBL: {message}", level)

    def log_camera_event(self, message: str, level: str = "info"):
        """Log camera-specific events"""
        self.log(f"Camera: {message}", level)

    def log_registration_event(self, message: str, level: str = "info"):
        """Log registration-specific events"""
        self.log(f"Registration: {message}", level)

    def log_application_event(self, message: str, level: str = "info"):
        """Log application-level events"""
        self.log(f"App: {message}", level)

    def get_frame(self):
        """Get the main frame for external access"""
        return self.parent

    def focus_command_entry(self):
        """Focus the command entry field"""
        # Find the command entry widget and focus it
        for widget in self.parent.winfo_children():
            if isinstance(widget, ttk.Frame):
                for subwidget in widget.winfo_children():
                    if isinstance(subwidget, ttk.LabelFrame) and "Manual GRBL Command" in subwidget.cget("text"):
                        for cmd_widget in subwidget.winfo_children():
                            if isinstance(cmd_widget, ttk.Frame):
                                for entry_widget in cmd_widget.winfo_children():
                                    if isinstance(entry_widget, ttk.Entry):
                                        entry_widget.focus_set()
                                        return

    def insert_command(self, command: str):
        """Insert a command into the command entry field"""
        self.manual_cmd_var.set(command)

    def get_console_content(self):
        """Get all content from the debug console"""
        if self.debug_text:
            return self.debug_text.get(1.0, tk.END)
        return ""

    def save_console_to_file(self, filename: str):
        """Save console content to a file"""
        try:
            content = self.get_console_content()
            with open(filename, 'w') as f:
                f.write(content)
            self.log(f"Console saved to: {filename}")
            return True
        except Exception as e:
            self.log(f"Error saving console: {e}", "error")
            return False

    def load_commands_from_file(self, filename: str):
        """Load and execute commands from a file"""
        try:
            with open(filename, 'r') as f:
                commands = f.readlines()

            self.log(f"Loading commands from: {filename}")
            for i, command in enumerate(commands, 1):
                command = command.strip()
                if command and not command.startswith('#'):  # Skip empty lines and comments
                    self.log(f"Executing command {i}: {command}")
                    self.manual_cmd_var.set(command)
                    self.send_manual_command()
                    time.sleep(0.1)  # Small delay between commands

            self.log(f"Finished executing {len([c for c in commands if c.strip() and not c.startswith('#')])} commands")
            return True
        except Exception as e:
            self.log(f"Error loading commands: {e}", "error")
            return False

    def add_debug_menu_items(self, menu):
        """Add debug-specific menu items to a menu"""
        debug_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Debug", menu=debug_menu)

        debug_menu.add_command(label="Clear Console", command=self.clear_debug)
        debug_menu.add_separator()
        debug_menu.add_command(label="Show Event Stats", command=self.show_event_stats)
        debug_menu.add_separator()
        debug_menu.add_checkbutton(label="Enable Debug", variable=self.debug_var, command=self.toggle_debug)

    def get_statistics(self):
        """Get debug panel statistics"""
        stats = {
            'debug_enabled': self.debug_enabled,
            'console_lines': 0,
            'camera_connected': self.camera_manager.is_connected if self.camera_manager else False,
            'grbl_connected': self.grbl_controller.is_connected if self.grbl_controller else False
        }

        if self.debug_text:
            content = self.debug_text.get(1.0, tk.END)
            stats['console_lines'] = len(content.split('\n')) - 1  # -1 for the last empty line

        return stats

    def update_camera_status(self):
        """Update camera status display (called from main window)"""
        if self.camera_manager and self.camera_manager.is_connected:
            info = self.camera_manager.get_camera_info()
            self.log(f"Camera status update: ID={info['camera_id']}, Resolution={info['width']}x{info['height']}, Calibrated={info['calibrated']}", "info")
        else:
            self.log("Camera status update: Disconnected", "info")