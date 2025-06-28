"""
Control Panels (Fixed)
Contains all the control panel widgets for the main GUI
Updated to work with new overlay architecture
"""

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

        if self.grbl_controller.connect():
            self.log("GRBL connected successfully")
            return True
        else:
            self.log("Failed to connect to GRBL", "error")
            messagebox.showerror("Error", "Failed to connect to GRBL")
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
            messagebox.showerror("Error", "Invalid camera ID")
            return False


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


class RegistrationPanel:
    """Registration control panel"""

    def __init__(self, parent, registration_manager, logger: Optional[Callable] = None):
        self.registration_manager = registration_manager
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="Registration")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Points listbox
        self.points_listbox = None

        # Callbacks
        self.capture_callback = None
        self.test_callback = None
        self.set_offset_callback = None

        # Camera connection state
        self.camera_connected = False

        self._setup_widgets()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def set_callbacks(self, capture_callback, test_callback, set_offset_callback):
        """Set callback functions for registration operations"""
        self.capture_callback = capture_callback
        self.test_callback = test_callback
        self.set_offset_callback = set_offset_callback

    def _setup_widgets(self):
        """Setup registration control widgets"""
        # Action buttons
        self.capture_btn = ttk.Button(self.frame, text="Capture Point", command=self._capture_point, state='disabled')
        self.capture_btn.pack(pady=2)

        ttk.Button(self.frame, text="Clear Points", command=self.clear_points).pack(pady=2)
        ttk.Button(self.frame, text="Compute Registration", command=self.compute_registration).pack(pady=2)
        ttk.Button(self.frame, text="Save Registration", command=self.save_registration).pack(pady=2)
        ttk.Button(self.frame, text="Load Registration", command=self.load_registration).pack(pady=2)

        # Points list
        self.points_listbox = tk.Listbox(self.frame, height=6)
        self.points_listbox.pack(fill=tk.X, pady=2)

        # Test controls
        test_frame = ttk.LabelFrame(self.frame, text="Test")
        test_frame.pack(fill=tk.X, pady=5)

        self.test_btn = ttk.Button(test_frame, text="Test Current Position", command=self._test_position, state='disabled')
        self.test_btn.pack(pady=2)

        self.offset_btn = ttk.Button(test_frame, text="Set Work Offset", command=self._set_work_offset, state='disabled')
        self.offset_btn.pack(pady=2)

    def on_camera_connected(self):
        """Enable camera-dependent controls when camera connects"""
        self.camera_connected = True
        self.capture_btn.config(state='normal')
        self.test_btn.config(state='normal')
        self.offset_btn.config(state='normal')

    def on_camera_disconnected(self):
        """Disable camera-dependent controls when camera disconnects"""
        self.camera_connected = False
        self.capture_btn.config(state='disabled')
        self.test_btn.config(state='disabled')
        self.offset_btn.config(state='disabled')

    def on_registration_computed(self, error: float):
        """Called when registration is computed successfully"""
        # Could update UI to show registration status
        pass

    def _capture_point(self):
        """Capture calibration point"""
        if self.capture_callback:
            self.capture_callback()

    def _test_position(self):
        """Test current position"""
        if self.test_callback:
            self.test_callback()

    def _set_work_offset(self):
        """Set work offset"""
        if self.set_offset_callback:
            self.set_offset_callback()

    def clear_points(self):
        """Clear all calibration points"""
        self.registration_manager.clear_calibration_points()
        self.points_listbox.delete(0, tk.END)
        self.log("Calibration points cleared")

    def add_point_to_list(self, machine_pos):
        """Add point to the listbox display"""
        point_count = self.registration_manager.get_calibration_points_count()
        point_str = f"Point {point_count}: M({machine_pos[0]:.2f}, {machine_pos[1]:.2f}, {machine_pos[2]:.2f})"
        self.points_listbox.insert(tk.END, point_str)

    def update_point_list(self):
        """Update the points list display"""
        self.points_listbox.delete(0, tk.END)
        try:
            machine_positions = self.registration_manager.get_machine_positions()
            for i, machine_pos in enumerate(machine_positions):
                point_str = f"Point {i + 1}: M({machine_pos[0]:.2f}, {machine_pos[1]:.2f}, {machine_pos[2]:.2f})"
                self.points_listbox.insert(tk.END, point_str)
        except:
            # Handle case where registration manager doesn't have get_machine_positions method
            pass

    def compute_registration(self):
        """Compute camera-to-machine registration"""
        try:
            if self.registration_manager.get_calibration_points_count() < 3:
                messagebox.showerror("Error", "Need at least 3 calibration points")
                return

            self.log(f"Computing registration with {self.registration_manager.get_calibration_points_count()} points")
            self.registration_manager.compute_registration()

            # Show registration error if available
            try:
                error = self.registration_manager.get_registration_error()
                if error is not None:
                    self.log(f"Registration RMS error: {error:.3f}mm")
            except:
                pass  # Method might not exist

            self.log("Camera-to-machine registration computed successfully")
            messagebox.showinfo("Success", "Camera-to-machine registration computed!")

        except Exception as e:
            self.log(f"Registration computation failed: {e}", "error")
            messagebox.showerror("Error", f"Registration failed: {e}")

    def save_registration(self):
        """Save registration data to file"""
        if not self.registration_manager.is_registered():
            messagebox.showerror("Error", "No registration data to save")
            return

        filename = filedialog.asksaveasfilename(
            title="Save Registration",
            defaultextension=".npz",
            filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
        )
        if filename:
            try:
                self.registration_manager.save_registration(filename)
                self.log(f"Registration saved to {filename}")
            except Exception as e:
                self.log(f"Failed to save registration: {e}", "error")
                messagebox.showerror("Error", f"Failed to save registration: {e}")

    def load_registration(self):
        """Load registration data from file"""
        filename = filedialog.askopenfilename(
            title="Load Registration",
            filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
        )
        if filename:
            try:
                self.registration_manager.load_registration(filename)
                self.update_point_list()
                self.log(f"Registration loaded from {filename}")
            except Exception as e:
                self.log(f"Failed to load registration: {e}", "error")
                messagebox.showerror("Error", f"Failed to load registration: {e}")


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
            if self.camera_manager.load_calibration(filename):
                self.log(f"Camera calibration loaded from {filename}")
                self.status_label.config(text="Camera: Connected & Calibrated", foreground="green")
            else:
                self.log(f"Failed to load calibration from {filename}", "error")
                messagebox.showerror("Error", "Failed to load calibration")

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
            self.log("Invalid marker length, using default 20.0mm", "error")
            return 20.0