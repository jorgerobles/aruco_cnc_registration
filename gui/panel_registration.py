import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional

from services.event_broker import (event_aware, event_handler, EventPriority,
                                   CameraEvents, RegistrationEvents)


@event_aware()
class RegistrationPanel:
    """Registration control panel with clean event awareness"""

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

    # Event handlers using decorators
    @event_handler(CameraEvents.CONNECTED, EventPriority.HIGH)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection events"""
        if success:
            self.on_camera_connected()
        else:
            self.on_camera_disconnected()

    @event_handler(CameraEvents.DISCONNECTED)
    def _on_camera_disconnected(self):
        """Handle camera disconnection events"""
        self.on_camera_disconnected()

    @event_handler(RegistrationEvents.POINT_ADDED, EventPriority.HIGH)
    def _on_point_added(self, point_data: dict):
        """Handle registration point added events"""
        # Update the points list display
        self.update_point_list()

        point_index = point_data['point_index']
        total_points = point_data['total_points']
        machine_pos = point_data['machine_pos']

        self.log(
            f"Point {point_index + 1} of {total_points} added: X{machine_pos[0]:.3f} Y{machine_pos[1]:.3f} Z{machine_pos[2]:.3f}")

    @event_handler(RegistrationEvents.POINT_REMOVED)
    def _on_point_removed(self, point_data: dict):
        """Handle registration point removed events"""
        self.update_point_list()
        self.log(f"Registration point removed")

    @event_handler(RegistrationEvents.COMPUTED, EventPriority.HIGH)
    def _on_registration_computed(self, computation_data: dict):
        """Handle registration computation events"""
        point_count = computation_data['point_count']
        error = computation_data['error']

        self.on_registration_computed(error)
        self.log(f"Registration computed with {point_count} points, RMS error: {error:.4f}")

        # Update UI to show successful registration
        messagebox.showinfo("Success", f"Registration computed!\nRMS Error: {error:.4f}mm")

    @event_handler(RegistrationEvents.ERROR)
    def _on_registration_error(self, error_message: str):
        """Handle registration errors - only real errors, not success messages"""
        self.log(f"Registration error: {error_message}", "error")
        messagebox.showerror("Registration Error", error_message)

    @event_handler(RegistrationEvents.CLEARED)
    def _on_registration_cleared(self, cleared_data: dict):
        """Handle registration data cleared events"""
        self.update_point_list()
        cleared_count = cleared_data.get('cleared_count', 0)
        self.log(f"Registration data cleared ({cleared_count} points)")

    @event_handler(RegistrationEvents.SAVED)
    def _on_registration_saved(self, save_data: dict):
        """Handle registration saved events"""
        file_path = save_data.get('filename', 'unknown')
        point_count = save_data.get('point_count', 0)
        error = save_data.get('error', 0.0)
        self.log(f"Registration saved to: {file_path} ({point_count} points, error: {error:.4f})")

    @event_handler(RegistrationEvents.LOADED)
    def _on_registration_loaded(self, load_data: dict):
        """Handle registration loaded events"""
        self.update_point_list()
        file_path = load_data.get('filename', 'unknown')
        point_count = load_data.get('point_count', 0)
        error = load_data.get('error', 0.0)
        self.log(f"Registration loaded from: {file_path} ({point_count} points, error: {error:.4f})")

    @event_handler(RegistrationEvents.VALIDATION_PASSED)
    def _on_validation_passed(self, validation_data: dict):
        """Handle registration validation passed events"""
        error = validation_data.get('error', 0.0)
        self.log(f"Registration validation passed with error: {error:.4f}")

    @event_handler(RegistrationEvents.VALIDATION_FAILED)
    def _on_validation_failed(self, validation_data: dict):
        """Handle registration validation failed events"""
        error = validation_data.get('error', 0.0)
        reason = validation_data.get('reason', 'Unknown')
        self.log(f"Registration validation failed: {reason} (error: {error:.4f})", "error")

    @event_handler(RegistrationEvents.DEBUG_INFO)
    def _on_debug_info(self, debug_data: dict):
        """Handle debug information events"""
        total_points = debug_data.get('total_points', 0)
        self.log(f"Debug: {total_points} calibration points registered")

        # Optionally log detailed point information in debug mode
        if self.logger and hasattr(self.logger, '__name__') and 'debug' in str(self.logger.__name__).lower():
            for point_detail in debug_data.get('points_detail', []):
                idx = point_detail['index']
                machine_pos = point_detail['machine_pos']
                self.log(f"  Point {idx}: Machine({machine_pos[0]:.3f}, {machine_pos[1]:.3f}, {machine_pos[2]:.3f})")

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
        points_frame = ttk.LabelFrame(self.frame, text="Calibration Points")
        points_frame.pack(fill=tk.X, pady=5)

        # Listbox with scrollbar
        listbox_frame = ttk.Frame(points_frame)
        listbox_frame.pack(fill=tk.X, padx=5, pady=5)

        self.points_listbox = tk.Listbox(listbox_frame, height=6)
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.points_listbox.yview)
        self.points_listbox.configure(yscrollcommand=scrollbar.set)

        self.points_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Point management buttons
        point_mgmt_frame = ttk.Frame(points_frame)
        point_mgmt_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Button(point_mgmt_frame, text="Remove Selected", command=self._remove_selected_point).pack(side=tk.LEFT,
                                                                                                       padx=2)
        ttk.Button(point_mgmt_frame, text="Refresh List", command=self.update_point_list).pack(side=tk.LEFT, padx=2)

        # Registration status
        status_frame = ttk.LabelFrame(self.frame, text="Registration Status")
        status_frame.pack(fill=tk.X, pady=5)

        self.status_label = ttk.Label(status_frame, text="No registration computed")
        self.status_label.pack(pady=5)

        # Test controls
        test_frame = ttk.LabelFrame(self.frame, text="Test & Apply")
        test_frame.pack(fill=tk.X, pady=5)

        self.test_btn = ttk.Button(test_frame, text="Test Current Position", command=self._test_position,
                                   state='disabled')
        self.test_btn.pack(pady=2)

        self.offset_btn = ttk.Button(test_frame, text="Set Work Offset", command=self._set_work_offset,
                                     state='disabled')
        self.offset_btn.pack(pady=2)

    def on_camera_connected(self):
        """Enable camera-dependent controls when camera connects"""
        self.camera_connected = True
        self.capture_btn.config(state='normal')
        self.test_btn.config(state='normal')
        self.offset_btn.config(state='normal')
        self.log("Camera connected - registration controls enabled")

    def on_camera_disconnected(self):
        """Disable camera-dependent controls when camera disconnects"""
        self.camera_connected = False
        self.capture_btn.config(state='disabled')
        self.test_btn.config(state='disabled')
        self.offset_btn.config(state='disabled')
        self.log("Camera disconnected - registration controls disabled")

    def on_registration_computed(self, error: float):
        """Called when registration is computed successfully"""
        self.status_label.config(text=f"Registration computed - RMS Error: {error:.4f}mm")
        # Enable test/offset buttons if camera is connected
        if self.camera_connected:
            self.test_btn.config(state='normal')
            self.offset_btn.config(state='normal')

    def _capture_point(self):
        """Capture calibration point"""
        if not self.camera_connected:
            messagebox.showerror("Error", "Camera not connected")
            return

        if self.capture_callback:
            try:
                self.log("Capturing calibration point...")
                self.capture_callback()
            except Exception as e:
                self.log(f"Failed to capture point: {e}", "error")
                messagebox.showerror("Error", f"Failed to capture point: {e}")
        else:
            self.log("No capture callback set", "error")

    def _test_position(self):
        """Test current position"""
        if not self.camera_connected:
            messagebox.showerror("Error", "Camera not connected")
            return

        if not self.registration_manager.is_registered():
            messagebox.showerror("Error", "No registration computed")
            return

        if self.test_callback:
            try:
                self.log("Testing current position...")
                self.test_callback()
            except Exception as e:
                self.log(f"Position test failed: {e}", "error")
                messagebox.showerror("Error", f"Position test failed: {e}")
        else:
            self.log("No test callback set", "error")

    def _set_work_offset(self):
        """Set work offset"""
        if not self.camera_connected:
            messagebox.showerror("Error", "Camera not connected")
            return

        if not self.registration_manager.is_registered():
            messagebox.showerror("Error", "No registration computed")
            return

        if self.set_offset_callback:
            try:
                self.log("Setting work offset...")
                self.set_offset_callback()
            except Exception as e:
                self.log(f"Failed to set work offset: {e}", "error")
                messagebox.showerror("Error", f"Failed to set work offset: {e}")
        else:
            self.log("No set offset callback set", "error")

    def _remove_selected_point(self):
        """Remove selected point from the list"""
        selection = self.points_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "No point selected")
            return

        point_index = selection[0]
        try:
            # Check if registration manager has remove method
            if hasattr(self.registration_manager, 'remove_calibration_point'):
                success = self.registration_manager.remove_calibration_point(point_index)
                if success:
                    self.log(f"Removed calibration point {point_index + 1}")
                else:
                    self.log(f"Failed to remove calibration point {point_index + 1}", "error")
            else:
                messagebox.showinfo("Info", "Point removal not supported by registration manager")
        except Exception as e:
            self.log(f"Failed to remove point: {e}", "error")
            messagebox.showerror("Error", f"Failed to remove point: {e}")

    def clear_points(self):
        """Clear all calibration points"""
        try:
            self.registration_manager.clear_calibration_points()
            # Events will handle the UI updates
            self.log("Calibration points cleared")
        except Exception as e:
            self.log(f"Failed to clear points: {e}", "error")
            messagebox.showerror("Error", f"Failed to clear points: {e}")

    def add_point_to_list(self, machine_pos):
        """Add point to the listbox display"""
        try:
            point_count = self.registration_manager.get_calibration_points_count()
            point_str = f"Point {point_count}: M({machine_pos[0]:.2f}, {machine_pos[1]:.2f}, {machine_pos[2]:.2f})"
            self.points_listbox.insert(tk.END, point_str)
        except Exception as e:
            self.log(f"Failed to add point to list: {e}", "error")

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

            # Update status based on point count
            count = self.registration_manager.get_calibration_points_count()
            if count == 0:
                self.status_label.config(text="No calibration points")
            elif count < 3:
                self.status_label.config(text=f"{count} points captured (need 3+ to compute)")
            else:
                # Check if registration is computed
                if self.registration_manager.is_registered():
                    try:
                        if hasattr(self.registration_manager, 'get_registration_error'):
                            error = self.registration_manager.get_registration_error()
                            if error is not None:
                                self.status_label.config(text=f"Registration computed - RMS Error: {error:.4f}mm")
                            else:
                                self.status_label.config(text="Registration computed")
                        else:
                            self.status_label.config(text="Registration computed")
                    except:
                        self.status_label.config(text="Registration computed")
                else:
                    self.status_label.config(text=f"{count} points ready - click Compute Registration")

        except Exception as e:
            self.log(f"Error updating point list: {e}", "error")

    def compute_registration(self):
        """Compute camera-to-machine registration"""
        try:
            point_count = self.registration_manager.get_calibration_points_count()
            if point_count < 3:
                messagebox.showerror("Error", f"Need at least 3 calibration points (have {point_count})")
                return

            self.log(f"Computing registration with {point_count} points...")
            self.status_label.config(text="Computing registration...")

            success = self.registration_manager.compute_registration()

            if not success:
                self.status_label.config(text="Registration computation failed")
                messagebox.showerror("Error", "Registration computation failed")

            # Success case will be handled by event handler

        except Exception as e:
            self.log(f"Registration computation failed: {e}", "error")
            self.status_label.config(text="Registration computation failed")
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
                success = self.registration_manager.save_registration(filename)
                if not success:
                    messagebox.showerror("Error", "Failed to save registration")
                # Success case will be handled by event handler
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
                self.log(f"Loading registration from: {filename}", "info")
                success = self.registration_manager.load_registration(filename)
                if not success:
                    messagebox.showerror("Error", "Failed to load registration")
                # Success case will be handled by event handler automatically
            except Exception as e:
                self.log(f"Failed to load registration from {filename}: {e}", "error")
                messagebox.showerror("Error", f"Failed to load registration: {e}")

    def get_registration_status(self):
        """Get current registration status for external queries"""
        try:
            point_count = self.registration_manager.get_calibration_points_count()
            is_registered = self.registration_manager.is_registered()

            status = {
                'point_count': point_count,
                'is_registered': is_registered,
                'camera_connected': self.camera_connected
            }

            if is_registered and hasattr(self.registration_manager, 'get_registration_error'):
                try:
                    error = self.registration_manager.get_registration_error()
                    status['registration_error'] = error
                except:
                    pass

            return status
        except Exception as e:
            self.log(f"Error getting registration status: {e}", "error")
            return {'error': str(e)}