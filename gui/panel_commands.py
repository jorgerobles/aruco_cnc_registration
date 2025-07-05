"""
GRBL Command Panel - Wide panel for manual GRBL command entry
Uses event_aware system for clean integration with the application
Sends responses via events to the debug panel
"""
import time
import tkinter as tk
from tkinter import ttk
import threading
from typing import List, Optional
from concurrent.futures import Future

from services.event_broker import event_aware, event_handler, EventPriority
from services.grbl_controller import GRBLEvents


@event_aware()
class GRBLCommandPanel:
    """
    Wide GRBL command panel for manual command entry
    Integrates with the event system for seamless operation
    """

    def __init__(self, parent, grbl_controller, logger=None):
        self.parent = parent
        self.grbl_controller = grbl_controller
        self.logger = logger or print

        # Command history
        self.command_history = []
        self.history_index = -1

        # Async command tracking
        self.pending_commands = {}

        # Common GRBL commands for quick access
        self.common_commands = [
            ("Status Query", "?"),
            ("Settings", "$"),
            ("Build Info", "$I"),
            ("Home", "$H"),
            ("Reset", "\x18"),
            ("Feed Hold", "!"),
            ("Resume", "~"),
            ("G54 (WCS 1)", "G54"),
            ("G55 (WCS 2)", "G55"),
            ("Absolute Mode", "G90"),
            ("Relative Mode", "G91"),
            ("Units: mm", "G21"),
            ("Units: inch", "G20"),
            ("Zero Current", "G10 L20 P1 X0 Y0 Z0"),
            ("Get Position", "G54 G0 X0 Y0"),
        ]

        # GUI elements
        self.frame = None
        self.command_var = None
        self.command_entry = None
        self.send_button = None
        self.async_button = None
        self.realtime_button = None
        self.status_label = None

        self.setup_gui()

        # Log creation
        self.log("GRBL Command Panel initialized")

    def log(self, message: str, level: str = "info"):
        """Log message via event system"""
        self.emit("grbl.debug_info", f"[CMD] {message}")

    def setup_gui(self):
        """Setup the command panel GUI"""
        # Main frame
        self.frame = ttk.LabelFrame(self.parent, text="🔧 GRBL Command Console")
        self.frame.pack(fill=tk.X, padx=5, pady=5)

        # Top row - Common commands
        self.setup_common_commands()

        # Middle row - Manual command entry
        self.setup_command_entry()

        # Bottom row - Status and controls
        self.setup_status_controls()

    def setup_common_commands(self):
        """Setup common commands row"""
        common_frame = ttk.Frame(self.frame)
        common_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(common_frame, text="Quick Commands:", font=('Arial', 8, 'bold')).pack(side=tk.LEFT, padx=(0, 5))

        # Create buttons for common commands (first 8)
        for i, (name, cmd) in enumerate(self.common_commands[:8]):
            btn = ttk.Button(
                common_frame,
                text=name,
                command=lambda c=cmd: self.execute_quick_command(c),
                width=12
            )
            btn.pack(side=tk.LEFT, padx=1)

        # More commands dropdown
        self.setup_more_commands_dropdown(common_frame)

    def setup_more_commands_dropdown(self, parent):
        """Setup dropdown for additional commands"""
        more_frame = ttk.Frame(parent)
        more_frame.pack(side=tk.RIGHT, padx=5)

        ttk.Label(more_frame, text="More:", font=('Arial', 8)).pack(side=tk.LEFT)

        self.more_commands_var = tk.StringVar()
        more_combo = ttk.Combobox(
            more_frame,
            textvariable=self.more_commands_var,
            values=[f"{name}: {cmd}" for name, cmd in self.common_commands[8:]],
            state="readonly",
            width=20
        )
        more_combo.pack(side=tk.LEFT, padx=2)
        more_combo.bind('<<ComboboxSelected>>', self.on_more_command_selected)

    def setup_command_entry(self):
        """Setup manual command entry row"""
        entry_frame = ttk.Frame(self.frame)
        entry_frame.pack(fill=tk.X, padx=5, pady=2)

        # Command label
        ttk.Label(entry_frame, text="Command:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))

        # Command entry with history support
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(
            entry_frame,
            textvariable=self.command_var,
            font=('Consolas', 10),
            width=50
        )
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Bind keyboard events
        self.command_entry.bind('<Return>', lambda e: self.send_command())
        self.command_entry.bind('<Up>', self.history_up)
        self.command_entry.bind('<Down>', self.history_down)
        self.command_entry.bind('<Tab>', self.auto_complete)

        # Action buttons
        self.send_button = ttk.Button(
            entry_frame,
            text="Send",
            command=self.send_command,
            width=8
        )
        self.send_button.pack(side=tk.LEFT, padx=2)

        self.async_button = ttk.Button(
            entry_frame,
            text="Send Async",
            command=self.send_command_async,
            width=10
        )
        self.async_button.pack(side=tk.LEFT, padx=2)

        self.realtime_button = ttk.Button(
            entry_frame,
            text="Realtime",
            command=self.send_realtime,
            width=10
        )
        self.realtime_button.pack(side=tk.LEFT, padx=2)

    def setup_status_controls(self):
        """Setup status and control row"""
        status_frame = ttk.Frame(self.frame)
        status_frame.pack(fill=tk.X, padx=5, pady=2)

        # Status display
        self.status_label = ttk.Label(
            status_frame,
            text="Ready - Enter GRBL commands above",
            font=('Arial', 8),
            foreground='gray'
        )
        self.status_label.pack(side=tk.LEFT)

        # Control buttons on right
        controls_frame = ttk.Frame(status_frame)
        controls_frame.pack(side=tk.RIGHT)

        ttk.Button(
            controls_frame,
            text="Clear History",
            command=self.clear_history,
            width=12
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            controls_frame,
            text="Connection Info",
            command=self.show_connection_info,
            width=12
        ).pack(side=tk.LEFT, padx=2)

        # Pending commands counter
        self.pending_label = ttk.Label(
            controls_frame,
            text="",
            font=('Arial', 8),
            foreground='blue'
        )
        self.pending_label.pack(side=tk.LEFT, padx=5)

    def execute_quick_command(self, command: str):
        """Execute a quick command"""
        self.command_var.set(command)
        self.send_command()

    def on_more_command_selected(self, event):
        """Handle more commands dropdown selection"""
        selection = self.more_commands_var.get()
        if selection:
            # Extract command from "name: command" format
            command = selection.split(": ", 1)[1]
            self.command_var.set(command)
            self.command_entry.focus_set()

    def send_command(self):
        """Send command synchronously"""
        command = self.command_var.get().strip()
        if not command:
            return

        if not self.grbl_controller.is_connected:
            self.log("GRBL not connected", "error")
            self.status_label.config(text="Error: GRBL not connected", foreground='red')
            return

        # Add to history
        self.add_to_history(command)

        # Update status
        self.status_label.config(text=f"Sending: {command}", foreground='blue')
        self.log(f"Sending command: {command}")

        # Send command in thread to avoid blocking UI
        def send_thread():
            try:
                responses = self.grbl_controller.send_command(command)

                # Log responses via events (will appear in debug panel)
                for response in responses:
                    self.log(f"Response: {response}", "received")

                # Update status on main thread
                self.parent.after(0, lambda: self.status_label.config(
                    text=f"Command sent: {command}", foreground='green'
                ))

            except Exception as e:
                error_msg = f"Command failed: {e}"
                self.log(error_msg, "error")
                self.parent.after(0, lambda: self.status_label.config(
                    text=error_msg, foreground='red'
                ))

        threading.Thread(target=send_thread, daemon=True).start()

        # Clear entry
        self.command_var.set("")

    def send_command_async(self):
        """Send command asynchronously"""
        command = self.command_var.get().strip()
        if not command:
            return

        if not self.grbl_controller.is_connected:
            self.log("GRBL not connected", "error")
            self.status_label.config(text="Error: GRBL not connected", foreground='red')
            return

        # Add to history
        self.add_to_history(command)

        try:
            # Send async command
            future = self.grbl_controller.send_command_async(command)

            # Track the future
            future_id = id(future)
            self.pending_commands[future_id] = {
                'command': command,
                'future': future,
                'start_time': time.time()
            }

            self.update_pending_count()
            self.log(f"Async command queued: {command}")
            self.status_label.config(text=f"Async queued: {command}", foreground='orange')

            # Monitor completion
            def monitor_completion():
                try:
                    responses = future.result(timeout=30)  # 30 second timeout

                    # Log responses
                    for response in responses:
                        self.log(f"Async Response: {response}", "received")

                    # Update UI on main thread
                    self.parent.after(0, lambda: self.on_async_completed(future_id, True))

                except Exception as e:
                    error_msg = f"Async command failed: {e}"
                    self.log(error_msg, "error")
                    self.parent.after(0, lambda: self.on_async_completed(future_id, False, str(e)))

            threading.Thread(target=monitor_completion, daemon=True).start()

        except Exception as e:
            error_msg = f"Failed to queue async command: {e}"
            self.log(error_msg, "error")
            self.status_label.config(text=error_msg, foreground='red')

        # Clear entry
        self.command_var.set("")

    def send_realtime(self):
        """Send realtime command"""
        command = self.command_var.get().strip()
        if not command:
            return

        if not self.grbl_controller.is_connected:
            self.log("GRBL not connected", "error")
            self.status_label.config(text="Error: GRBL not connected", foreground='red')
            return

        # Validate realtime commands
        if command not in ['!', '~', '\x18']:
            self.log(f"Invalid realtime command: {command}. Use !, ~, or \\x18", "error")
            self.status_label.config(text="Error: Invalid realtime command", foreground='red')
            return

        try:
            self.grbl_controller.send_realtime_command(command)
            self.log(f"Realtime command sent: {repr(command)}")
            self.status_label.config(text=f"Realtime sent: {repr(command)}", foreground='green')

            # Add to history
            self.add_to_history(command)

        except Exception as e:
            error_msg = f"Realtime command failed: {e}"
            self.log(error_msg, "error")
            self.status_label.config(text=error_msg, foreground='red')

        # Clear entry
        self.command_var.set("")

    def on_async_completed(self, future_id: int, success: bool, error: str = None):
        """Handle async command completion"""
        if future_id in self.pending_commands:
            cmd_info = self.pending_commands[future_id]
            command = cmd_info['command']
            duration = time.time() - cmd_info['start_time']

            if success:
                self.log(f"Async command completed: {command} ({duration:.2f}s)")
                self.status_label.config(text=f"Async completed: {command}", foreground='green')
            else:
                self.log(f"Async command failed: {command} - {error}")
                self.status_label.config(text=f"Async failed: {command}", foreground='red')

            del self.pending_commands[future_id]
            self.update_pending_count()

    def update_pending_count(self):
        """Update pending commands display"""
        count = len(self.pending_commands)
        if count > 0:
            self.pending_label.config(text=f"Pending: {count}")
        else:
            self.pending_label.config(text="")

    def add_to_history(self, command: str):
        """Add command to history"""
        if command not in self.command_history:
            self.command_history.append(command)
            # Keep only last 50 commands
            if len(self.command_history) > 50:
                self.command_history.pop(0)
        self.history_index = len(self.command_history)

    def history_up(self, event):
        """Navigate up in command history"""
        if self.command_history and self.history_index > 0:
            self.history_index -= 1
            self.command_var.set(self.command_history[self.history_index])
        return "break"

    def history_down(self, event):
        """Navigate down in command history"""
        if self.command_history:
            if self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.command_var.set(self.command_history[self.history_index])
            else:
                self.history_index = len(self.command_history)
                self.command_var.set("")
        return "break"

    def auto_complete(self, event):
        """Basic auto-completion for common commands"""
        current = self.command_var.get().upper()
        if current:
            # Look for matching commands
            matches = [cmd for _, cmd in self.common_commands if cmd.upper().startswith(current)]
            if matches:
                self.command_var.set(matches[0])
                # Select the auto-completed part
                self.command_entry.select_range(len(current), tk.END)
        return "break"

    def clear_history(self):
        """Clear command history"""
        self.command_history.clear()
        self.history_index = -1
        self.log("Command history cleared")
        self.status_label.config(text="History cleared", foreground='gray')

    def show_connection_info(self):
        """Show GRBL connection information"""
        if not self.grbl_controller.is_connected:
            self.log("GRBL not connected", "error")
            return

        try:
            info = self.grbl_controller.get_connection_info()

            # Log detailed connection info
            self.log("=== GRBL Connection Info ===")
            self.log(f"Connected: {info['is_connected']}")
            self.log(f"Port: {info['serial_port']}")
            self.log(f"Baudrate: {info['baudrate']}")
            self.log(f"Status: {info['current_status']}")
            self.log(
                f"Position: X{info['current_position'][0]:.3f} Y{info['current_position'][1]:.3f} Z{info['current_position'][2]:.3f}")
            self.log(f"GRBL Detected: {info['grbl_detected']}")
            self.log(f"Initialization Complete: {info['initialization_complete']}")

            buffer_status = info['buffer_status']
            self.log(f"Pending Commands: {buffer_status['pending_futures']}")

            debug_settings = info['debug_settings']
            self.log(f"Debug Enabled: {debug_settings['debug_enabled']}")
            self.log("=== End Connection Info ===")

            self.status_label.config(text="Connection info logged", foreground='blue')

        except Exception as e:
            error_msg = f"Failed to get connection info: {e}"
            self.log(error_msg, "error")
            self.status_label.config(text=error_msg, foreground='red')

    def update_connection_status(self):
        """Update UI based on connection status"""
        is_connected = self.grbl_controller.is_connected if self.grbl_controller else False

        # Enable/disable buttons
        state = tk.NORMAL if is_connected else tk.DISABLED
        self.send_button.config(state=state)
        self.async_button.config(state=state)
        self.realtime_button.config(state=state)

        # Update status text
        if is_connected:
            try:
                status = self.grbl_controller.get_status()
                position = self.grbl_controller.get_position()
                self.status_label.config(
                    text=f"Connected - Status: {status} | Pos: X{position[0]:.1f} Y{position[1]:.1f} Z{position[2]:.1f}",
                    foreground='green'
                )
            except:
                self.status_label.config(text="Connected - Status unknown", foreground='green')
        else:
            self.status_label.config(text="GRBL not connected", foreground='red')

    # Event handlers
    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def _on_grbl_connected(self, success: bool):
        """Handle GRBL connection events"""
        self.parent.after(0, self.update_connection_status)

    @event_handler(GRBLEvents.DISCONNECTED, EventPriority.HIGH)
    def _on_grbl_disconnected(self):
        """Handle GRBL disconnection events"""
        self.parent.after(0, self.update_connection_status)

    @event_handler(GRBLEvents.STATUS_CHANGED, EventPriority.LOW)
    def _on_status_changed(self, status: str):
        """Handle GRBL status changes"""
        # Update status display periodically (not on every change to avoid spam)
        if hasattr(self, '_last_status_update'):
            if time.time() - self._last_status_update < 1.0:  # Throttle to 1 second
                return

        self._last_status_update = time.time()
        self.parent.after(0, self.update_connection_status)

    def get_panel_status(self):
        """Get current panel status for debugging"""
        return {
            'history_count': len(self.command_history),
            'pending_commands': len(self.pending_commands),
            'last_command': self.command_history[-1] if self.command_history else None,
            'grbl_connected': self.grbl_controller.is_connected if self.grbl_controller else False
        }