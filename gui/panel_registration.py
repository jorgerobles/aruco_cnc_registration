import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional


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
            # Try to get machine positions if method exists
            if hasattr(self.registration_manager, 'get_machine_positions'):
                machine_positions = self.registration_manager.get_machine_positions()
                for i, machine_pos in enumerate(machine_positions):
                    point_str = f"Point {i + 1}: M({machine_pos[0]:.2f}, {machine_pos[1]:.2f}, {machine_pos[2]:.2f})"
                    self.points_listbox.insert(tk.END, point_str)
            else:
                # Fallback: just show point count
                count = self.registration_manager.get_calibration_points_count()
                for i in range(count):
                    point_str = f"Point {i + 1}: (Data available)"
                    self.points_listbox.insert(tk.END, point_str)
        except Exception as e:
            self.log(f"Error updating point list: {e}", "error")

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
                if hasattr(self.registration_manager, 'get_registration_error'):
                    error = self.registration_manager.get_registration_error()
                    if error is not None:
                        self.log(f"Registration RMS error: {error:.3f}mm")
            except Exception as e:
                self.log(f"Could not get registration error: {e}", "error")

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