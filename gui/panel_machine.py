
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional



class MachineControlPanel:
    """Machine control panel for GRBL operations"""

    def __init__(self, parent, grbl_controller, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="Machine Control")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.step_size_var = tk.StringVar(value="10")

        # Position display
        self.position_label = ttk.Label(self.frame, text="Position: Not connected")

        self._setup_widgets()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def _setup_widgets(self):
        """Setup machine control widgets"""
        # Position display
        self.position_label.pack()

        # Control buttons
        ttk.Button(self.frame, text="Home", command=self.home_machine).pack(pady=2)
        ttk.Button(self.frame, text="Update Position", command=self.update_position).pack(pady=2)

        # Jog controls
        self._setup_jog_controls()

    def _setup_jog_controls(self):
        """Setup jog control widgets"""
        jog_frame = ttk.Frame(self.frame)
        jog_frame.pack(pady=5)

        # Step size
        ttk.Label(jog_frame, text="Step Size:").pack()
        step_combo = ttk.Combobox(jog_frame, textvariable=self.step_size_var,
                                  values=["0.1", "1", "10", "50"], width=10)
        step_combo.pack()

        # XY movement buttons
        xy_frame = ttk.Frame(jog_frame)
        xy_frame.pack(pady=5)

        ttk.Button(xy_frame, text="Y+", command=lambda: self.jog(y=1)).grid(row=0, column=1)
        ttk.Button(xy_frame, text="X-", command=lambda: self.jog(x=-1)).grid(row=1, column=0)
        ttk.Button(xy_frame, text="Home", command=lambda: self.jog(x=0, y=0)).grid(row=1, column=1)
        ttk.Button(xy_frame, text="X+", command=lambda: self.jog(x=1)).grid(row=1, column=2)
        ttk.Button(xy_frame, text="Y-", command=lambda: self.jog(y=-1)).grid(row=2, column=1)

        # Z movement
        z_frame = ttk.Frame(jog_frame)
        z_frame.pack(pady=5)
        ttk.Button(z_frame, text="Z+", command=lambda: self.jog(z=1)).pack()
        ttk.Button(z_frame, text="Z-", command=lambda: self.jog(z=-1)).pack()

    def update_position(self):
        """Update machine position display"""
        try:
            pos = self.grbl_controller.get_position()
            self.position_label.config(text=f"Position: X{pos[0]:.3f} Y{pos[1]:.3f} Z{pos[2]:.3f}")
            self.log(f"Position updated: X{pos[0]:.3f} Y{pos[1]:.3f} Z{pos[2]:.3f}")
        except Exception as e:
            self.position_label.config(text="Position: Error reading")
            self.log(f"Error reading position: {e}", "error")

    def home_machine(self):
        """Home the machine"""
        try:
            self.log("Initiating homing sequence")
            response = self.grbl_controller.home()
            for line in response:
                self.log(f"HOME: {line}")
            self.update_position()
        except Exception as e:
            self.log(f"Homing failed: {e}", "error")
            messagebox.showerror("Error", f"Homing failed: {e}")

    def jog(self, x=0, y=0, z=0):
        """Jog machine in specified direction"""
        try:
            step = float(self.step_size_var.get())
            move_x, move_y, move_z = x * step, y * step, z * step
            self.log(f"Jogging: X{move_x} Y{move_y} Z{move_z}")
            response = self.grbl_controller.move_relative(move_x, move_y, move_z)
            for line in response:
                self.log(f"JOG: {line}")
            self.update_position()
        except Exception as e:
            self.log(f"Jog failed: {e}", "error")
            messagebox.showerror("Error", f"Jog failed: {e}")