import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional

class ConnectionPanel:
    """Connection controls for GRBL and Camera"""

    def __init__(self, parent, grbl_controller, camera_manager, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.camera_manager = camera_manager
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="Connections")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.grbl_port_var = tk.StringVar(value="/dev/ttyUSB0")
        self.camera_id_var = tk.StringVar(value="0")

        self._setup_widgets()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def _setup_widgets(self):
        """Setup connection control widgets"""
        # GRBL Port
        ttk.Label(self.frame, text="GRBL Port:").pack()
        ttk.Entry(self.frame, textvariable=self.grbl_port_var, width=20).pack()

        # Camera ID
        ttk.Label(self.frame, text="Camera ID:").pack()
        ttk.Entry(self.frame, textvariable=self.camera_id_var, width=20).pack()

        # Connect buttons
        ttk.Button(self.frame, text="Connect GRBL", command=self.connect_grbl).pack(pady=2)
        ttk.Button(self.frame, text="Connect Camera", command=self.connect_camera).pack(pady=2)

    def connect_grbl(self):
        """Connect to GRBL controller"""
        port = self.grbl_port_var.get()
        self.grbl_controller.port = port
        self.log(f"Attempting to connect to GRBL on {port}")

        try:
            if self.grbl_controller.connect():
                self.log("GRBL connected successfully")
                return True
            else:
                self.log("Failed to connect to GRBL", "error")
                messagebox.showerror("Error", "Failed to connect to GRBL")
                return False
        except Exception as e:
            self.log(f"GRBL connection error: {e}", "error")
            messagebox.showerror("Error", f"Failed to connect to GRBL: {e}")
            return False

    def connect_camera(self):
        """Connect to camera"""
        try:
            camera_id = int(self.camera_id_var.get())
            self.camera_manager.camera_id = camera_id
            self.log(f"Attempting to connect to camera {camera_id}")

            if self.camera_manager.connect():
                self.log("Camera connected successfully")
                return True
            else:
                self.log("Failed to connect to camera", "error")
                messagebox.showerror("Error", "Failed to connect to camera")
                return False
        except ValueError:
            self.log("Invalid camera ID format", "error")
            messagebox.showerror("Error", "Invalid camera ID")
            return False
        except Exception as e:
            self.log(f"Camera connection error: {e}", "error")
            messagebox.showerror("Error", f"Failed to connect to camera: {e}")
            return False
