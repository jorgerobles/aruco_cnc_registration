import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional

class CalibrationPanel:
    """Camera calibration control panel"""

    def __init__(self, parent, camera_manager, logger: Optional[Callable] = None):
        self.camera_manager = camera_manager
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="Camera Calibration")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.marker_length_var = tk.StringVar(value="20.0")

        # Camera connection state
        self.camera_connected = False

        self._setup_widgets()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def _setup_widgets(self):
        """Setup calibration control widgets"""
        self.load_btn = ttk.Button(self.frame, text="Load Camera Calibration",
                                  command=self.load_calibration, state='disabled')
        self.load_btn.pack(pady=2)

        ttk.Label(self.frame, text="Marker Length (mm):").pack()
        marker_entry = ttk.Entry(self.frame, textvariable=self.marker_length_var, width=20)
        marker_entry.pack()

        # Bind enter key to update marker length
        marker_entry.bind('<Return>', self._on_marker_length_changed)
        marker_entry.bind('<FocusOut>', self._on_marker_length_changed)

        # Status display
        self.status_label = ttk.Label(self.frame, text="Camera: Disconnected", foreground="red")
        self.status_label.pack(pady=2)

    def _on_marker_length_changed(self, event=None):
        """Called when marker length is changed"""
        # This would be used to update the marker overlay if we had access to it
        # In the new architecture, the main window handles this
        pass

    def on_camera_connected(self):
        """Enable camera-dependent controls when camera connects"""
        self.camera_connected = True
        self.load_btn.config(state='normal')

        # Update status
        if self.camera_manager.is_calibrated():
            self.status_label.config(text="Camera: Connected & Calibrated", foreground="green")
        else:
            self.status_label.config(text="Camera: Connected (Not Calibrated)", foreground="orange")

    def on_camera_disconnected(self):
        """Disable camera-dependent controls when camera disconnects"""
        self.camera_connected = False
        self.load_btn.config(state='disabled')
        self.status_label.config(text="Camera: Disconnected", foreground="red")

    def load_calibration(self):
        """Load camera calibration from file"""
        filename = filedialog.askopenfilename(
            title="Load Camera Calibration",
            filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
        )
        if filename:
            try:
                if self.camera_manager.load_calibration(filename):
                    self.log(f"Camera calibration loaded from {filename}")
                    self.status_label.config(text="Camera: Connected & Calibrated", foreground="green")
                else:
                    self.log(f"Failed to load calibration from {filename}", "error")
                    messagebox.showerror("Error", "Failed to load calibration")
            except Exception as e:
                self.log(f"Error loading calibration: {e}", "error")
                messagebox.showerror("Error", f"Failed to load calibration: {e}")

    def get_marker_length(self) -> float:
        """Get current marker length, with validation"""
        try:
            marker_length_str = self.marker_length_var.get().strip()
            if not marker_length_str:
                self.marker_length_var.set("20.0")
                return 20.0
            return float(marker_length_str)
        except ValueError:
            self.marker_length_var.set("20.0")
            if self.logger:
                self.log("Invalid marker length, using default 20.0mm", "error")
            return 20.0
        except Exception as e:
            self.marker_length_var.set("20.0")
            if self.logger:
                self.log(f"Error getting marker length: {e}, using default 20.0mm", "error")
            return 20.0