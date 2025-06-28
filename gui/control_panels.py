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


class SVGRoutesPanel:
    """SVG Routes overlay control panel"""

    def __init__(self, parent, routes_overlay, logger: Optional[Callable] = None):
        self.routes_overlay = routes_overlay
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="SVG Routes Overlay")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.svg_visible_var = tk.BooleanVar(value=False)
        self.svg_color_var = tk.StringVar(value="yellow")
        self.svg_thickness_var = tk.IntVar(value=2)
        self.svg_use_registration_var = tk.BooleanVar(value=True)
        self.svg_scale_var = tk.DoubleVar(value=1.0)
        self.svg_offset_x_var = tk.IntVar(value=0)
        self.svg_offset_y_var = tk.IntVar(value=0)

        # State
        self.routes_loaded = False

        self._setup_widgets()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def _setup_widgets(self):
        """Setup SVG routes control widgets"""
        # File management
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill=tk.X, pady=2)

        ttk.Button(file_frame, text="Load SVG Routes",
                  command=self.load_svg_routes).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Clear Routes",
                  command=self.clear_svg_routes).pack(side=tk.LEFT, padx=2)

        # Visibility toggle
        self.svg_visibility_check = ttk.Checkbutton(
            self.frame,
            text="Show Routes Overlay",
            variable=self.svg_visible_var,
            command=self.toggle_svg_visibility,
            state='disabled'  # Disabled until routes are loaded
        )
        self.svg_visibility_check.pack(pady=2)

        # Route configuration
        config_frame = ttk.LabelFrame(self.frame, text="Appearance")
        config_frame.pack(fill=tk.X, pady=2)

        # Color and thickness in one row
        style_frame = ttk.Frame(config_frame)
        style_frame.pack(fill=tk.X, pady=2)

        ttk.Label(style_frame, text="Color:").pack(side=tk.LEFT)
        self.svg_color_combo = ttk.Combobox(
            style_frame,
            textvariable=self.svg_color_var,
            values=["yellow", "red", "green", "blue", "cyan", "magenta"],
            width=8,
            state='disabled'
        )
        self.svg_color_combo.pack(side=tk.LEFT, padx=2)
        self.svg_color_combo.bind('<<ComboboxSelected>>', self.change_svg_color)

        ttk.Label(style_frame, text="Thickness:").pack(side=tk.LEFT, padx=(10,0))
        self.svg_thickness_spin = tk.Spinbox(
            style_frame,
            from_=1, to=10,
            width=3,
            textvariable=self.svg_thickness_var,
            command=self.change_svg_thickness,
            state='disabled'
        )
        self.svg_thickness_spin.pack(side=tk.LEFT, padx=2)

        # Transform controls
        transform_frame = ttk.LabelFrame(self.frame, text="Coordinate Transform")
        transform_frame.pack(fill=tk.X, pady=2)

        # Registration vs manual transform
        self.svg_registration_check = ttk.Checkbutton(
            transform_frame,
            text="Use Registration Transform",
            variable=self.svg_use_registration_var,
            command=self.toggle_svg_transform_mode,
            state='disabled'
        )
        self.svg_registration_check.pack()

        # Manual transform controls (initially hidden)
        self.manual_transform_frame = ttk.Frame(transform_frame)

        # Scale control
        scale_frame = ttk.Frame(self.manual_transform_frame)
        scale_frame.pack(fill=tk.X, pady=1)
        ttk.Label(scale_frame, text="Scale:").pack(side=tk.LEFT)
        self.svg_scale_spin = tk.Spinbox(
            scale_frame,
            from_=0.1, to=10.0, increment=0.1,
            width=6,
            textvariable=self.svg_scale_var,
            command=self.update_manual_transform
        )
        self.svg_scale_spin.pack(side=tk.LEFT, padx=2)

        # Offset controls
        offset_frame = ttk.Frame(self.manual_transform_frame)
        offset_frame.pack(fill=tk.X, pady=1)
        ttk.Label(offset_frame, text="Offset X:").pack(side=tk.LEFT)
        self.svg_offset_x_spin = tk.Spinbox(
            offset_frame,
            from_=-1000, to=1000, increment=10,
            width=6,
            textvariable=self.svg_offset_x_var,
            command=self.update_manual_transform
        )
        self.svg_offset_x_spin.pack(side=tk.LEFT, padx=2)

        ttk.Label(offset_frame, text="Y:").pack(side=tk.LEFT, padx=(5,0))
        self.svg_offset_y_spin = tk.Spinbox(
            offset_frame,
            from_=-1000, to=1000, increment=10,
            width=6,
            textvariable=self.svg_offset_y_var,
            command=self.update_manual_transform
        )
        self.svg_offset_y_spin.pack(side=tk.LEFT, padx=2)

        # Routes info display
        self.svg_info_var = tk.StringVar(value="No routes loaded")
        self.svg_info_label = ttk.Label(self.frame, textvariable=self.svg_info_var,
                                       foreground="gray")
        self.svg_info_label.pack(pady=2)

    def load_svg_routes(self):
        """Load SVG routes file"""
        filename = filedialog.askopenfilename(
            title="Load SVG Routes",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )

        if filename:
            try:
                # Load routes into overlay
                self.routes_overlay.load_routes_from_svg(filename)

                # Update state and UI
                self.routes_loaded = True
                self.update_svg_info()
                self.enable_svg_controls()

                self.log(f"Loaded SVG routes from: {filename}")

            except Exception as e:
                self.log(f"Failed to load SVG routes: {e}", "error")
                messagebox.showerror("Error", f"Failed to load SVG routes: {e}")

    def clear_svg_routes(self):
        """Clear all SVG routes"""
        self.routes_overlay.clear_routes()
        self.routes_loaded = False
        self.update_svg_info()
        self.disable_svg_controls()
        self.log("SVG routes cleared")

    def toggle_svg_visibility(self):
        """Toggle SVG routes overlay visibility"""
        visible = self.svg_visible_var.get()
        self.routes_overlay.set_visibility(visible)

        status = "visible" if visible else "hidden"
        self.log(f"SVG routes overlay {status}")

    def change_svg_color(self, event=None):
        """Change SVG routes color"""
        color_name = self.svg_color_var.get()
        color_map = {
            "yellow": (255, 255, 0),
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "blue": (255, 0, 0),
            "cyan": (255, 255, 0),
            "magenta": (255, 0, 255)
        }

        if color_name in color_map:
            try:
                self.routes_overlay.set_route_color(color_map[color_name])
                self.log(f"SVG route color changed to: {color_name}")
            except Exception as e:
                self.log(f"Error changing route color: {e}", "error")

    def change_svg_thickness(self):
        """Change SVG routes line thickness"""
        try:
            thickness = self.svg_thickness_var.get()
            self.routes_overlay.set_route_thickness(thickness)
            self.log(f"SVG route thickness changed to: {thickness}")
        except Exception as e:
            self.log(f"Error changing route thickness: {e}", "error")

    def toggle_svg_transform_mode(self):
        """Toggle between registration and manual transform mode"""
        try:
            use_registration = self.svg_use_registration_var.get()
            self.routes_overlay.set_use_registration_transform(use_registration)

            if use_registration:
                # Hide manual transform controls
                self.manual_transform_frame.pack_forget()
                self.log("SVG overlay using registration transform")
            else:
                # Show manual transform controls
                self.manual_transform_frame.pack(fill=tk.X, pady=2)
                # Apply current manual transform
                self.update_manual_transform()
                self.log("SVG overlay using manual transform")
        except Exception as e:
            self.log(f"Error toggling transform mode: {e}", "error")

    def update_manual_transform(self):
        """Update manual transform parameters"""
        try:
            if not self.svg_use_registration_var.get():
                scale = self.svg_scale_var.get()
                offset_x = self.svg_offset_x_var.get()
                offset_y = self.svg_offset_y_var.get()

                self.routes_overlay.set_manual_transform(scale, (offset_x, offset_y))
                self.log(f"Manual transform: scale={scale:.1f}, offset=({offset_x}, {offset_y})")
        except Exception as e:
            self.log(f"Error updating manual transform: {e}", "error")

    def update_svg_info(self):
        """Update SVG routes information display"""
        try:
            count = self.routes_overlay.get_routes_count()
            bounds = self.routes_overlay.get_route_bounds()

            if count > 0:
                info_text = f"{count} routes loaded"
                if bounds:
                    info_text += f"\nBounds: ({bounds[0]:.1f}, {bounds[1]:.1f}) to ({bounds[2]:.1f}, {bounds[3]:.1f})"
                self.svg_info_var.set(info_text)
                self.svg_info_label.config(foreground="green")
            else:
                self.svg_info_var.set("No routes loaded")
                self.svg_info_label.config(foreground="gray")
        except Exception as e:
            self.log(f"Error updating SVG info: {e}", "error")
            self.svg_info_var.set("Error getting route info")
            self.svg_info_label.config(foreground="red")

    def enable_svg_controls(self):
        """Enable SVG control widgets when routes are loaded"""
        self.svg_visibility_check.config(state='normal')
        self.svg_color_combo.config(state='readonly')
        self.svg_thickness_spin.config(state='normal')
        self.svg_registration_check.config(state='normal')

        # Enable manual transform controls if they exist
        if hasattr(self, 'svg_scale_spin'):
            self.svg_scale_spin.config(state='normal')
        if hasattr(self, 'svg_offset_x_spin'):
            self.svg_offset_x_spin.config(state='normal')
        if hasattr(self, 'svg_offset_y_spin'):
            self.svg_offset_y_spin.config(state='normal')

    def disable_svg_controls(self):
        """Disable SVG control widgets when no routes loaded"""
        self.svg_visible_var.set(False)
        self.routes_overlay.set_visibility(False)

        self.svg_visibility_check.config(state='disabled')
        self.svg_color_combo.config(state='disabled')
        self.svg_thickness_spin.config(state='disabled')
        self.svg_registration_check.config(state='disabled')

        # Disable manual transform controls if they exist
        if hasattr(self, 'svg_scale_spin'):
            self.svg_scale_spin.config(state='disabled')
        if hasattr(self, 'svg_offset_x_spin'):
            self.svg_offset_x_spin.config(state='disabled')
        if hasattr(self, 'svg_offset_y_spin'):
            self.svg_offset_y_spin.config(state='disabled')

        # Hide manual transform controls
        self.manual_transform_frame.pack_forget()

    def get_routes_count(self) -> int:
        """Get number of loaded routes"""
        try:
            return self.routes_overlay.get_routes_count() if self.routes_loaded else 0
        except Exception:
            return 0

    def is_visible(self) -> bool:
        """Check if routes overlay is visible"""
        try:
            return self.svg_visible_var.get() and self.routes_loaded
        except Exception:
            return False
            return float(marker_length_str)
        except ValueError:
            self.marker_length_var.set("20.0")
            if self.logger:
                self.log("Invalid marker length, using default 20.0mm", "error")
            return 20.0
        except Exception as e:
            self.marker_length_var.set("20.0")
            if self.logger:
                self.log(f"Error parsing marker length: {e}, using default 20.0mm", "error")
            return 20.0