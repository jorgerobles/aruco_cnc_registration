"""
Simple Debug Panel - Clean log display with proper color coding by level
Removed external dependencies - self-contained logging panel
"""

import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk, scrolledtext, filedialog
from typing import Dict

from services.event_broker import (event_aware, event_handler, EventPriority)
from services.events import ApplicationEvents


@event_aware()
class DebugPanel:
    """Simple debug panel focused on clean log display with proper color coding"""

    def __init__(self, parent):
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
        self.frame = parent

        # Control frame
        control_frame = ttk.Frame(self.frame)
        control_frame.pack(fill=tk.X, padx=5, pady=2)

        # Status frame (left side)
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

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

    def is_ready(self) -> bool:
        """Check if debug panel is ready for logging"""
        return hasattr(self, 'log_display') and self.log_display.winfo_exists()

    def cleanup(self):
        """Clean up resources"""
        self._gui_update_running = False
        if hasattr(self, 'gui_thread') and self.gui_thread.is_alive():
            self.gui_thread.join(timeout=1.0)

    @event_handler(ApplicationEvents.SHUTDOWN, EventPriority.HIGH)
    def _on_app_shutdown(self):
        """Handle application shutdown"""
        self.log("Application shutting down", "info")
        self.cleanup()
