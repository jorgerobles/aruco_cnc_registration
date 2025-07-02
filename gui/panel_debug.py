"""
Simple Debug Panel - Clean log display with proper color coding by level
Removed GRBL-specific filtering - that responsibility belongs to GRBL controller
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import time
from datetime import datetime
from typing import Optional, Callable, Dict, Any
import threading
import queue

from services.event_broker import (event_aware, event_handler, EventPriority,
                                   GRBLEvents, CameraEvents, ApplicationEvents)


@event_aware()
class DebugPanel:
    """Simple debug panel focused on clean log display with proper color coding"""

    def __init__(self, parent, grbl_controller, camera_manager, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.camera_manager = camera_manager
        self.logger = logger

        # Threading and queue for safe GUI updates
        self.log_queue = queue.Queue()
        self._gui_update_running = True

        # Simple statistics
        self._stats = {
            'total_logs': 0,
            'start_time': time.time()
        }

        self.setup_gui(parent)
        self.start_gui_updater()

    def setup_gui(self, parent):
        """Setup the simple debug panel GUI"""
        # Main frame
        self.frame = ttk.LabelFrame(parent, text="🐛 Debug Console")
        self.frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Control frame
        control_frame = ttk.Frame(self.frame)
        control_frame.pack(fill=tk.X, padx=5, pady=2)

        # Status frame (left side)
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Connection status labels
        ttk.Label(status_frame, text="GRBL:").pack(side=tk.LEFT)
        self.grbl_status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.grbl_status_label.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(status_frame, text="Camera:").pack(side=tk.LEFT)
        self.camera_status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.camera_status_label.pack(side=tk.LEFT, padx=(0, 10))

        # Log count
        ttk.Label(status_frame, text="Logs:").pack(side=tk.LEFT)
        self.log_count_label = ttk.Label(status_frame, text="0")
        self.log_count_label.pack(side=tk.LEFT)

        # Action buttons (right side)
        action_frame = ttk.Frame(control_frame)
        action_frame.pack(side=tk.RIGHT)

        ttk.Button(action_frame, text="Clear", command=self.clear_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Export", command=self.export_log).pack(side=tk.LEFT, padx=2)

        # Log display with scrolling
        log_frame = ttk.Frame(self.frame)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_display = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='white'
        )
        self.log_display.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for different log levels
        self.log_display.tag_configure("info", foreground="#00ff00")
        self.log_display.tag_configure("warning", foreground="#ffaa00")
        self.log_display.tag_configure("error", foreground="#ff4444")
        self.log_display.tag_configure("debug", foreground="#888888")
        self.log_display.tag_configure("received", foreground="#00aaff")
        self.log_display.tag_configure("sent", foreground="#ff00aa")
        self.log_display.tag_configure("grbl", foreground="#00ffaa")
        self.log_display.tag_configure("timestamp", foreground="#666666")

        # Make read-only
        self.log_display.config(state=tk.DISABLED)

        # Initialize status
        self.update_status_display()

    def start_gui_updater(self):
        """Start the GUI update thread"""
        def gui_updater():
            while self._gui_update_running:
                try:
                    # Process log queue
                    while not self.log_queue.empty():
                        try:
                            log_entry = self.log_queue.get_nowait()
                            self._append_to_display(log_entry)
                        except queue.Empty:
                            break

                    time.sleep(0.1)  # 10 FPS update rate
                except Exception as e:
                    print(f"GUI updater error: {e}")
                    break

        self.gui_thread = threading.Thread(target=gui_updater, daemon=True)
        self.gui_thread.start()

    def log(self, message: str, level: str = "info"):
        """Main logging method - thread-safe, simple color coding by level"""
        try:
            # Update statistics
            self._stats['total_logs'] += 1

            # Create log entry
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            log_entry = {
                'timestamp': timestamp,
                'level': level,
                'message': message
            }

            # Add to queue for GUI thread processing
            self.log_queue.put(log_entry)

            # Update log count display
            if hasattr(self, 'log_count_label'):
                self.log_count_label.config(text=str(self._stats['total_logs']))

        except Exception as e:
            # Fallback - print to console if GUI logging fails
            print(f"[{level.upper()}] {message}")

    def _append_to_display(self, log_entry: Dict[str, str]):
        """Append log entry to display (called from GUI thread)"""
        try:
            self.log_display.config(state=tk.NORMAL)

            # Insert timestamp
            self.log_display.insert(tk.END, f"[{log_entry['timestamp']}] ", "timestamp")

            # Insert level indicator with appropriate color
            level = log_entry['level']
            level_text = f"[{level.upper()}] "
            self.log_display.insert(tk.END, level_text, level)

            # Insert message
            self.log_display.insert(tk.END, f"{log_entry['message']}\n")

            # Auto-scroll to bottom
            self.log_display.see(tk.END)

            # Limit log length to prevent memory issues
            line_count = int(self.log_display.index('end-1c').split('.')[0])
            if line_count > 1000:  # Keep last 1000 lines
                self.log_display.delete('1.0', '200.end')  # Remove first 200 lines

            self.log_display.config(state=tk.DISABLED)

        except Exception as e:
            print(f"Display append error: {e}")

    def clear_log(self):
        """Clear the log display"""
        try:
            self.log_display.config(state=tk.NORMAL)
            self.log_display.delete('1.0', tk.END)
            self.log_display.config(state=tk.DISABLED)

            # Reset statistics
            self._stats = {
                'total_logs': 0,
                'start_time': time.time()
            }

            # Update display
            self.log_count_label.config(text="0")

            self.log("Debug log cleared", "info")

        except Exception as e:
            print(f"Clear log error: {e}")

    def export_log(self):
        """Export log to file"""
        try:
            # Get log content
            self.log_display.config(state=tk.NORMAL)
            content = self.log_display.get('1.0', tk.END)
            self.log_display.config(state=tk.DISABLED)

            # Ask for save location
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialname=f"debug_log_{timestamp}.txt"
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(f"Debug Log Export - {datetime.now()}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(content)

                    # Add basic statistics
                    f.write("\n" + "=" * 50 + "\n")
                    f.write("Statistics:\n")
                    f.write(f"Total logs: {self._stats['total_logs']}\n")
                    f.write(f"Session duration: {time.time() - self._stats['start_time']:.1f}s\n")

                self.log(f"Debug log exported to: {filename}", "info")

        except Exception as e:
            self.log(f"Export failed: {e}", "error")

    def update_status_display(self):
        """Update connection status display"""
        try:
            # Update GRBL status
            if self.grbl_controller and self.grbl_controller.is_connected:
                self.grbl_status_label.config(text="Connected", foreground="green")
            else:
                self.grbl_status_label.config(text="Disconnected", foreground="red")

            # Update camera status
            if self.camera_manager and self.camera_manager.is_connected:
                self.camera_status_label.config(text="Connected", foreground="green")
            else:
                self.camera_status_label.config(text="Disconnected", foreground="red")

        except Exception as e:
            print(f"Status update error: {e}")

    def update_camera_status(self):
        """Update camera status (called externally)"""
        self.update_status_display()

    def is_ready(self) -> bool:
        """Check if debug panel is ready for logging"""
        return hasattr(self, 'log_display') and self.log_display.winfo_exists()

    def cleanup(self):
        """Clean up resources"""
        self._gui_update_running = False
        if hasattr(self, 'gui_thread') and self.gui_thread.is_alive():
            self.gui_thread.join(timeout=1.0)

    # Simple event handlers - just log what happens
    @event_handler(GRBLEvents.CONNECTED, EventPriority.NORMAL)
    def _on_grbl_connected(self, success: bool):
        """Handle GRBL connection events"""
        if success:
            self.log("GRBL connected successfully", "info")
        else:
            self.log("GRBL connection failed", "error")
        self.update_status_display()

    @event_handler(GRBLEvents.DISCONNECTED, EventPriority.NORMAL)
    def _on_grbl_disconnected(self):
        """Handle GRBL disconnection"""
        self.log("GRBL disconnected", "info")
        self.update_status_display()

    @event_handler(GRBLEvents.ERROR, EventPriority.LOW)
    def _on_grbl_error(self, error_message: str):
        """Handle GRBL error messages - for actual errors only"""
        self.log(f"GRBL ERROR: {error_message}", "error")

    @event_handler(GRBLEvents.DEBUG_INFO, EventPriority.LOW)
    def _on_grbl_debug_info(self, debug_message: str):
        """Handle GRBL debug information - for general debug messages"""
        self.log(f"GRBL: {debug_message}", "grbl")

    @event_handler(GRBLEvents.COMMAND_SENT, EventPriority.LOW)
    def _on_grbl_command_sent(self, command: str):
        """Handle GRBL command sent events"""
        self.log(f"GRBL SENT: {command}", "sent")

    @event_handler(GRBLEvents.RESPONSE_RECEIVED, EventPriority.LOW)
    def _on_grbl_response_received(self, response: str):
        """Handle GRBL response events"""
        self.log(f"GRBL RECV: {response}", "received")

    @event_handler(CameraEvents.CONNECTED, EventPriority.NORMAL)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection events"""
        if success:
            self.log("Camera connected successfully", "info")
        else:
            self.log("Camera connection failed", "error")
        self.update_status_display()

    @event_handler(CameraEvents.DISCONNECTED, EventPriority.NORMAL)
    def _on_camera_disconnected(self):
        """Handle camera disconnection"""
        self.log("Camera disconnected", "info")
        self.update_status_display()

    @event_handler(CameraEvents.ERROR, EventPriority.NORMAL)
    def _on_camera_error(self, error_message: str):
        """Handle camera errors"""
        self.log(f"Camera error: {error_message}", "error")

    @event_handler(ApplicationEvents.SHUTDOWN, EventPriority.HIGH)
    def _on_app_shutdown(self):
        """Handle application shutdown"""
        self.log("Application shutting down", "info")
        self.cleanup()