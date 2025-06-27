"""
Main Window
Main GUI window that combines all panels and manages application state
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import time
from typing import Optional

from camera_manager import CameraManager
from grbl_controller import GRBLController
from registration.registration_manager import RegistrationManager
from gui.control_panels import ConnectionPanel, MachineControlPanel, RegistrationPanel, CalibrationPanel
from gui.camera_display import CameraDisplay


class RegistrationGUI:
    """Main GUI window for GRBL Camera Registration application"""

    def __init__(self, root):
        self.root = root
        self.root.title("GRBL Camera Registration")
        self.root.geometry("1400x900")

        # Controllers and managers
        self.grbl_controller = GRBLController()
        self.camera_manager = CameraManager()
        self.registration_manager = RegistrationManager()

        # GUI state
        self.debug_enabled = False

        # GUI components
        self.debug_text = None
        self.status_var = None
        self.camera_display = None
        self.connection_panel = None
        self.machine_panel = None
        self.registration_panel = None
        self.calibration_panel = None

        self.setup_gui()

    def setup_gui(self):
        """Setup the main GUI layout"""
        # Create main paned window
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel for controls
        left_panel = ttk.Frame(main_paned)
        main_paned.add(left_panel, weight=0)

        # Right panel with vertical paned window for display and debug
        right_panel = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        main_paned.add(right_panel, weight=1)

        # Display frame (top of right panel)
        display_frame = ttk.LabelFrame(right_panel, text="Camera View")
        right_panel.add(display_frame, weight=1)

        # Debug frame (bottom of right panel)
        debug_frame = ttk.LabelFrame(right_panel, text="Debug Console")
        right_panel.add(debug_frame, weight=0)

        self.setup_control_panel(left_panel)
        self.setup_display_panel(display_frame)
        self.setup_debug_panel(debug_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_control_panel(self, parent):
        """Setup the left control panel with all sub-panels"""
        # Create scrollable frame for controls
        canvas = tk.Canvas(parent, width=300)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Create control panels
        self.connection_panel = ConnectionPanel(
            scrollable_frame, self.grbl_controller, self.camera_manager, self.log
        )

        self.setup_debug_controls(scrollable_frame)

        self.calibration_panel = CalibrationPanel(
            scrollable_frame, self.camera_manager, self.log
        )

        self.machine_panel = MachineControlPanel(
            scrollable_frame, self.grbl_controller, self.log
        )

        self.registration_panel = RegistrationPanel(
            scrollable_frame, self.registration_manager, self.log
        )

        # Set up registration panel callbacks
        self.registration_panel.set_callbacks(
            self.capture_point,
            self.test_position,
            self.set_work_offset
        )

    def setup_debug_controls(self, parent):
        """Setup debug controls section"""
        debug_ctrl_frame = ttk.LabelFrame(parent, text="Debug Controls")
        debug_ctrl_frame.pack(fill=tk.X, pady=5, padx=5)

        self.debug_var = tk.BooleanVar()
        ttk.Checkbutton(debug_ctrl_frame, text="Enable Debug",
                        variable=self.debug_var, command=self.toggle_debug).pack()

        ttk.Button(debug_ctrl_frame, text="Clear Debug", command=self.clear_debug).pack(pady=2)

        # Manual command entry
        ttk.Label(debug_ctrl_frame, text="Manual GRBL Command:").pack()
        self.manual_cmd_var = tk.StringVar()
        cmd_entry = ttk.Entry(debug_ctrl_frame, textvariable=self.manual_cmd_var, width=20)
        cmd_entry.pack()
        cmd_entry.bind('<Return>', self.send_manual_command)
        ttk.Button(debug_ctrl_frame, text="Send Command", command=self.send_manual_command).pack(pady=2)

    def setup_display_panel(self, parent):
        """Setup camera display panel"""
        self.camera_display = CameraDisplay(parent, self.camera_manager, self.log)

    def setup_debug_panel(self, parent):
        """Setup debug console panel"""
        # Debug text area with scrollbar
        self.debug_text = scrolledtext.ScrolledText(parent, height=8, wrap=tk.WORD)
        self.debug_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure text tags for different message types
        self.debug_text.tag_configure("sent", foreground="blue")
        self.debug_text.tag_configure("received", foreground="green")
        self.debug_text.tag_configure("error", foreground="red")
        self.debug_text.tag_configure("info", foreground="gray")

    def log(self, message: str, level: str = "info"):
        """Log message to debug console"""
        if self.debug_enabled:
            timestamp = time.strftime("%H:%M:%S")
            tag_map = {
                "info": "info",
                "error": "error",
                "sent": "sent",
                "received": "received"
            }
            tag = tag_map.get(level, "info")
            self.debug_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
            self.debug_text.see(tk.END)

    def toggle_debug(self):
        """Toggle debug mode on/off"""
        self.debug_enabled = self.debug_var.get()
        if self.debug_enabled:
            self.log("Debug mode enabled", "info")
        else:
            self.log("Debug mode disabled", "info")

    def clear_debug(self):
        """Clear debug console"""
        self.debug_text.delete(1.0, tk.END)

    def send_manual_command(self, event=None):
        """Send manual GRBL command"""
        command = self.manual_cmd_var.get().strip()
        if not command:
            return

        try:
            self.log(f"SENT: {command}", "sent")
            response = self.grbl_controller.send_command(command)
            for line in response:
                self.log(f"RECV: {line}", "received")
            self.manual_cmd_var.set("")  # Clear entry
        except Exception as e:
            self.log(f"ERROR: {e}", "error")

    def capture_point(self):
        """Capture calibration point (callback for registration panel)"""
        try:
            # Get machine position
            machine_pos = self.grbl_controller.get_position()
            self.log(f"Machine position: X{machine_pos[0]:.3f} Y{machine_pos[1]:.3f} Z{machine_pos[2]:.3f}")

            # Get marker position from camera
            rvec, tvec, norm_pos = self.camera_display.capture_marker_pose()

            if tvec is None:
                self.log("No marker detected in current frame", "error")
                return

            # Add to registration manager
            self.registration_manager.add_calibration_point(machine_pos, tvec, norm_pos)

            # Update display
            self.registration_panel.add_point_to_list(machine_pos)

            point_count = self.registration_manager.get_calibration_points_count()
            self.status_var.set(f"Captured point {point_count}")
            self.log(f"Captured calibration point {point_count}")

        except Exception as e:
            self.log(f"Failed to capture point: {e}", "error")

    def test_position(self):
        """Test current position (callback for registration panel)"""
        try:
            if not self.registration_manager.is_registered():
                self.log("Registration not computed", "error")
                return

            # Get current marker pose
            rvec, tvec, norm_pos = self.camera_display.capture_marker_pose()

            if tvec is None:
                self.log("No marker detected", "error")
                return

            # Transform to machine coordinates
            machine_point = self.registration_manager.transform_point(tvec.flatten())

            self.log(f"Position test - Camera: {tvec.flatten()}, Predicted machine: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}")

        except Exception as e:
            self.log(f"Position test failed: {e}", "error")

    def set_work_offset(self):
        """Set work offset (callback for registration panel)"""
        try:
            if not self.registration_manager.is_registered():
                self.log("Registration not computed", "error")
                return

            # Get current marker pose
            rvec, tvec, norm_pos = self.camera_display.capture_marker_pose()

            if tvec is None:
                self.log("No marker detected", "error")
                return

            # Transform to machine coordinates
            machine_point = self.registration_manager.transform_point(tvec.flatten())

            # Set work offset
            response = self.grbl_controller.set_work_offset(machine_point, coordinate_system=1)
            for line in response:
                self.log(f"OFFSET: {line}", "received")

            self.status_var.set("Work offset set")
            self.log(f"Work offset set to: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}")

        except Exception as e:
            self.log(f"Failed to set work offset: {e}", "error")

    def start_camera_feed(self):
        """Start camera feed after connection"""
        if self.camera_display:
            # Update marker length from calibration panel
            marker_length = self.calibration_panel.get_marker_length()
            self.camera_display.set_marker_length(marker_length)
            self.camera_display.start_feed()
            self.log(f"Camera feed started", "started")

    def on_closing(self):
        """Handle application closing"""
        if self.camera_display:
            self.camera_display.stop_feed()
        self.camera_manager.disconnect()
        self.grbl_controller.disconnect()
        self.log("Application closing")
        self.root.destroy()