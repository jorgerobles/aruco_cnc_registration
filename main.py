import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

import cv2
import numpy as np
from PIL import Image, ImageTk

from camera_manager import CameraManager
from grbl_controller import GRBLController


class RegistrationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GRBL Camera Registration")
        self.root.geometry("1400x900")

        # Controllers
        self.grbl = GRBLController()
        self.camera = CameraManager()

        # Registration data
        self.calibration_points = []  # [(machine_pos, camera_tvec, norm_pos), ...]
        self.transformation_matrix = None
        self.translation_vector = None

        # GUI state
        self.camera_running = False
        self.current_frame = None
        self.marker_length = 20.0  # mm
        self.debug_enabled = False

        self.setup_gui()

    def setup_gui(self):
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
        debug_frame = ttk.LabelFrame(right_panel, text="GRBL Debug Console")
        right_panel.add(debug_frame, weight=0)

        self.setup_control_panel(left_panel)
        self.setup_display_panel(display_frame)
        self.setup_debug_panel(debug_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_control_panel(self, parent):
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

        # Connection controls
        conn_frame = ttk.LabelFrame(scrollable_frame, text="Connections")
        conn_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(conn_frame, text="GRBL Port:").pack()
        self.grbl_port_var = tk.StringVar(value="COM3")
        ttk.Entry(conn_frame, textvariable=self.grbl_port_var, width=20).pack()

        ttk.Label(conn_frame, text="Camera ID:").pack()
        self.camera_id_var = tk.StringVar(value="0")
        ttk.Entry(conn_frame, textvariable=self.camera_id_var, width=20).pack()

        ttk.Button(conn_frame, text="Connect GRBL", command=self.connect_grbl).pack(pady=2)
        ttk.Button(conn_frame, text="Connect Camera", command=self.connect_camera).pack(pady=2)

        # Debug controls
        debug_ctrl_frame = ttk.LabelFrame(scrollable_frame, text="Debug Controls")
        debug_ctrl_frame.pack(fill=tk.X, pady=5, padx=5)

        self.debug_var = tk.BooleanVar()
        ttk.Checkbutton(debug_ctrl_frame, text="Enable GRBL Debug",
                        variable=self.debug_var, command=self.toggle_debug).pack()

        ttk.Button(debug_ctrl_frame, text="Clear Debug", command=self.clear_debug).pack(pady=2)

        # Manual command entry
        ttk.Label(debug_ctrl_frame, text="Manual GRBL Command:").pack()
        self.manual_cmd_var = tk.StringVar()
        cmd_entry = ttk.Entry(debug_ctrl_frame, textvariable=self.manual_cmd_var, width=20)
        cmd_entry.pack()
        cmd_entry.bind('<Return>', self.send_manual_command)
        ttk.Button(debug_ctrl_frame, text="Send Command", command=self.send_manual_command).pack(pady=2)

        # Calibration controls
        calib_frame = ttk.LabelFrame(scrollable_frame, text="Calibration")
        calib_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(calib_frame, text="Load Camera Calibration",
                   command=self.load_calibration).pack(pady=2)

        ttk.Label(calib_frame, text="Marker Length (mm):").pack()
        self.marker_length_var = tk.StringVar(value="20.0")
        ttk.Entry(calib_frame, textvariable=self.marker_length_var, width=20).pack()

        # Machine control
        machine_frame = ttk.LabelFrame(scrollable_frame, text="Machine Control")
        machine_frame.pack(fill=tk.X, pady=5, padx=5)

        # Position display
        self.position_label = ttk.Label(machine_frame, text="Position: Not connected")
        self.position_label.pack()

        ttk.Button(machine_frame, text="Home", command=self.home_machine).pack(pady=2)
        ttk.Button(machine_frame, text="Update Position", command=self.update_position).pack(pady=2)

        # Jog controls
        jog_frame = ttk.Frame(machine_frame)
        jog_frame.pack(pady=5)

        # Step size
        ttk.Label(jog_frame, text="Step Size:").pack()
        self.step_size_var = tk.StringVar(value="10")
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

        # Registration controls
        reg_frame = ttk.LabelFrame(scrollable_frame, text="Registration")
        reg_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(reg_frame, text="Capture Point", command=self.capture_point).pack(pady=2)
        ttk.Button(reg_frame, text="Clear Points", command=self.clear_points).pack(pady=2)
        ttk.Button(reg_frame, text="Compute Registration", command=self.compute_registration).pack(pady=2)
        ttk.Button(reg_frame, text="Save Registration", command=self.save_registration).pack(pady=2)
        ttk.Button(reg_frame, text="Load Registration", command=self.load_registration).pack(pady=2)

        # Points list
        self.points_listbox = tk.Listbox(reg_frame, height=6)
        self.points_listbox.pack(fill=tk.X, pady=2)

        # Test controls
        test_frame = ttk.LabelFrame(scrollable_frame, text="Test")
        test_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(test_frame, text="Test Current Position", command=self.test_position).pack(pady=2)
        ttk.Button(test_frame, text="Set Work Offset", command=self.set_work_offset).pack(pady=2)

    def setup_display_panel(self, parent):
        # Camera display canvas
        self.canvas = tk.Canvas(parent, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_debug_panel(self, parent):
        # Debug text area with scrollbar
        self.debug_text = scrolledtext.ScrolledText(parent, height=8, wrap=tk.WORD)
        self.debug_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure text tags for different message types
        self.debug_text.tag_configure("sent", foreground="blue")
        self.debug_text.tag_configure("received", foreground="green")
        self.debug_text.tag_configure("error", foreground="red")
        self.debug_text.tag_configure("info", foreground="gray")

    def log_debug(self, message, tag="info"):
        """Add message to debug console"""
        if self.debug_enabled:
            timestamp = time.strftime("%H:%M:%S")
            self.debug_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
            self.debug_text.see(tk.END)

    def toggle_debug(self):
        """Toggle debug mode on/off"""
        self.debug_enabled = self.debug_var.get()
        if self.debug_enabled:
            self.log_debug("Debug mode enabled", "info")
        else:
            self.log_debug("Debug mode disabled", "info")

    def clear_debug(self):
        """Clear debug console"""
        self.debug_text.delete(1.0, tk.END)

    def send_manual_command(self, event=None):
        """Send manual GRBL command"""
        command = self.manual_cmd_var.get().strip()
        if not command:
            return

        try:
            self.log_debug(f"SENT: {command}", "sent")
            response = self.grbl.send_command(command)
            for line in response:
                self.log_debug(f"RECV: {line}", "received")
            self.manual_cmd_var.set("")  # Clear entry
        except Exception as e:
            self.log_debug(f"ERROR: {e}", "error")

    def connect_grbl(self):
        port = self.grbl_port_var.get()
        self.grbl.port = port
        self.log_debug(f"Attempting to connect to GRBL on {port}", "info")

        if self.grbl.connect():
            self.status_var.set("GRBL connected")
            self.log_debug("GRBL connected successfully", "info")
            self.update_position()
        else:
            self.log_debug("Failed to connect to GRBL", "error")
            messagebox.showerror("Error", "Failed to connect to GRBL")

    def connect_camera(self):
        try:
            camera_id = int(self.camera_id_var.get())
            self.camera.camera_id = camera_id
            self.log_debug(f"Attempting to connect to camera {camera_id}", "info")

            if self.camera.connect():
                self.status_var.set("Camera connected")
                self.log_debug("Camera connected successfully", "info")
                self.start_camera_feed()
            else:
                self.log_debug("Failed to connect to camera", "error")
                messagebox.showerror("Error", "Failed to connect to camera")
        except ValueError:
            messagebox.showerror("Error", "Invalid camera ID")

    def load_calibration(self):
        filename = filedialog.askopenfilename(
            title="Load Camera Calibration",
            filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
        )
        if filename:
            if self.camera.load_calibration(filename):
                self.status_var.set("Calibration loaded")
                self.log_debug(f"Camera calibration loaded from {filename}", "info")
            else:
                self.log_debug(f"Failed to load calibration from {filename}", "error")
                messagebox.showerror("Error", "Failed to load calibration")

    def start_camera_feed(self):
        self.camera_running = True
        self.update_camera_feed()

    def update_camera_feed(self):
        if not self.camera_running:
            return

        frame = self.camera.capture_frame()
        if frame is not None:
            self.current_frame = frame.copy()

            # Try to detect markers
            try:
                marker_length_str = self.marker_length_var.get().strip()
                if not marker_length_str:
                    self.marker_length = 20.0  # Default value
                    self.marker_length_var.set("20.0")  # Update the field
                else:
                    self.marker_length = float(marker_length_str)
            except ValueError:
                self.marker_length = 20.0  # Fallback to default
                self.marker_length_var.set("20.0")  # Reset to valid value
                self.log_debug("Invalid marker length, using default 20.0mm", "error")

            try:
                rvec, tvec, norm_pos, annotated_frame = self.camera.detect_marker_pose(frame, self.marker_length)
                display_frame = annotated_frame

                if tvec is not None:
                    # Draw marker info
                    cv2.putText(display_frame, f"Marker detected", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(display_frame, f"Pos: {tvec.flatten()}", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            except Exception as e:
                display_frame = frame
                cv2.putText(display_frame, "No marker detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                self.log_debug(f"Marker detection error: {e}", "error")

            # Convert to PhotoImage and display with correct aspect ratio
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)

            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                # Calculate aspect ratios
                img_aspect = pil_image.width / pil_image.height
                canvas_aspect = canvas_width / canvas_height

                # Determine scaling to maintain aspect ratio
                if img_aspect > canvas_aspect:
                    # Image is wider than canvas
                    new_width = canvas_width
                    new_height = int(canvas_width / img_aspect)
                else:
                    # Image is taller than canvas
                    new_height = canvas_height
                    new_width = int(canvas_height * img_aspect)

                # Resize image maintaining aspect ratio
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(pil_image)
            self.canvas.delete("all")

            # Center the image on the canvas
            x_offset = (canvas_width - pil_image.width) // 2
            y_offset = (canvas_height - pil_image.height) // 2
            self.canvas.create_image(x_offset + pil_image.width // 2,
                                     y_offset + pil_image.height // 2,
                                     image=photo)
            self.canvas.image = photo  # Keep a reference

        self.root.after(50, self.update_camera_feed)

    def update_position(self):
        try:
            pos = self.grbl.get_position()
            self.position_label.config(text=f"Position: X{pos[0]:.3f} Y{pos[1]:.3f} Z{pos[2]:.3f}")
            self.log_debug(f"Position updated: X{pos[0]:.3f} Y{pos[1]:.3f} Z{pos[2]:.3f}", "info")
        except Exception as e:
            self.position_label.config(text="Position: Error reading")
            self.log_debug(f"Error reading position: {e}", "error")

    def home_machine(self):
        try:
            self.log_debug("Initiating homing sequence", "info")
            response = self.grbl.home()
            for line in response:
                self.log_debug(f"HOME: {line}", "received")
            time.sleep(1)
            self.update_position()
            self.status_var.set("Machine homed")
        except Exception as e:
            self.log_debug(f"Homing failed: {e}", "error")
            messagebox.showerror("Error", f"Homing failed: {e}")

    def jog(self, x=0, y=0, z=0):
        try:
            step = float(self.step_size_var.get())
            move_x, move_y, move_z = x * step, y * step, z * step
            self.log_debug(f"Jogging: X{move_x} Y{move_y} Z{move_z}", "info")
            response = self.grbl.move_relative(move_x, move_y, move_z)
            for line in response:
                self.log_debug(f"JOG: {line}", "received")
            time.sleep(0.1)
            self.update_position()
        except Exception as e:
            self.log_debug(f"Jog failed: {e}", "error")
            messagebox.showerror("Error", f"Jog failed: {e}")

    def capture_point(self):
        try:
            # Get machine position
            machine_pos = self.grbl.get_position()
            self.log_debug(f"Machine position: X{machine_pos[0]:.3f} Y{machine_pos[1]:.3f} Z{machine_pos[2]:.3f}",
                           "info")

            # Get marker position from camera
            if self.current_frame is None:
                messagebox.showerror("Error", "No camera frame available")
                return

            # Validate marker length
            try:
                marker_length_str = self.marker_length_var.get().strip()
                if not marker_length_str:
                    self.marker_length = 20.0
                    self.marker_length_var.set("20.0")
                else:
                    self.marker_length = float(marker_length_str)
            except ValueError:
                self.marker_length = 20.0
                self.marker_length_var.set("20.0")
                self.log_debug("Invalid marker length, using default 20.0mm", "error")

            rvec, tvec, norm_pos, _ = self.camera.detect_marker_pose(self.current_frame, self.marker_length)

            if tvec is None:
                messagebox.showerror("Error", "No marker detected in current frame")
                return

            # Store calibration point
            point_data = (machine_pos, tvec.flatten(), norm_pos)
            self.calibration_points.append(point_data)

            # Update list display
            point_str = f"Point {len(self.calibration_points)}: M({machine_pos[0]:.2f}, {machine_pos[1]:.2f}, {machine_pos[2]:.2f})"
            self.points_listbox.insert(tk.END, point_str)

            self.status_var.set(f"Captured point {len(self.calibration_points)}")
            self.log_debug(
                f"Captured calibration point {len(self.calibration_points)}: Machine({machine_pos[0]:.3f}, {machine_pos[1]:.3f}, {machine_pos[2]:.3f}), Camera({tvec.flatten()})",
                "info")

        except Exception as e:
            self.log_debug(f"Failed to capture point: {e}", "error")
            messagebox.showerror("Error", f"Failed to capture point: {e}")

    def clear_points(self):
        self.calibration_points.clear()
        self.points_listbox.delete(0, tk.END)
        self.status_var.set("Points cleared")
        self.log_debug("Calibration points cleared", "info")

    def compute_registration(self):
        if len(self.calibration_points) < 3:
            messagebox.showerror("Error", "Need at least 3 calibration points")
            return

        try:
            self.log_debug(f"Computing registration with {len(self.calibration_points)} points", "info")

            # Extract points
            machine_points = [point[0] for point in self.calibration_points]
            camera_points = [point[1] for point in self.calibration_points]

            # Compute rigid transformation
            self.transformation_matrix, self.translation_vector = self.compute_rigid_transform(
                camera_points, machine_points)

            self.status_var.set("Registration computed successfully")
            self.log_debug("Camera-to-machine registration computed successfully", "info")
            messagebox.showinfo("Success", "Camera-to-machine registration computed!")

        except Exception as e:
            self.log_debug(f"Registration computation failed: {e}", "error")
            messagebox.showerror("Error", f"Registration failed: {e}")

    def compute_rigid_transform(self, A, B):
        A = np.asarray(A)
        B = np.asarray(B)
        centroid_A = np.mean(A, axis=0)
        centroid_B = np.mean(B, axis=0)

        AA = A - centroid_A
        BB = B - centroid_B

        H = AA.T @ BB
        U, _, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T
        if np.linalg.det(R) < 0:
            Vt[2, :] *= -1
            R = Vt.T @ U.T
        t = centroid_B - R @ centroid_A
        return R, t

    def transform_point(self, point):
        if self.transformation_matrix is None or self.translation_vector is None:
            raise ValueError("Registration not computed")
        return self.transformation_matrix @ point + self.translation_vector

    def save_registration(self):
        if self.transformation_matrix is None:
            messagebox.showerror("Error", "No registration data to save")
            return

        filename = filedialog.asksaveasfilename(
            title="Save Registration",
            defaultextension=".npz",
            filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
        )
        if filename:
            np.savez(filename,
                     rotation_matrix=self.transformation_matrix,
                     translation_vector=self.translation_vector,
                     calibration_points=self.calibration_points)
            self.status_var.set("Registration saved")
            self.log_debug(f"Registration saved to {filename}", "info")

    def load_registration(self):
        filename = filedialog.askopenfilename(
            title="Load Registration",
            filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
        )
        if filename:
            try:
                data = np.load(filename, allow_pickle=True)
                self.transformation_matrix = data["rotation_matrix"]
                self.translation_vector = data["translation_vector"]
                self.calibration_points = data["calibration_points"].tolist()

                # Update points list
                self.points_listbox.delete(0, tk.END)
                for i, (machine_pos, _, _) in enumerate(self.calibration_points):
                    point_str = f"Point {i + 1}: M({machine_pos[0]:.2f}, {machine_pos[1]:.2f}, {machine_pos[2]:.2f})"
                    self.points_listbox.insert(tk.END, point_str)

                self.status_var.set("Registration loaded")
                self.log_debug(f"Registration loaded from {filename}", "info")
            except Exception as e:
                self.log_debug(f"Failed to load registration: {e}", "error")
                messagebox.showerror("Error", f"Failed to load registration: {e}")

    def test_position(self):
        try:
            if self.current_frame is None:
                messagebox.showerror("Error", "No camera frame available")
                return

            # Validate marker length
            try:
                marker_length_str = self.marker_length_var.get().strip()
                if not marker_length_str:
                    self.marker_length = 20.0
                    self.marker_length_var.set("20.0")
                else:
                    self.marker_length = float(marker_length_str)
            except ValueError:
                self.marker_length = 20.0
                self.marker_length_var.set("20.0")
                self.log_debug("Invalid marker length, using default 20.0mm", "error")

            rvec, tvec, norm_pos, _ = self.camera.detect_marker_pose(self.current_frame, self.marker_length)

            if tvec is None:
                messagebox.showerror("Error", "No marker detected")
                return

            # Transform to machine coordinates
            machine_point = self.transform_point(tvec.flatten())

            result = f"Camera position: {tvec.flatten()}\n"
            result += f"Predicted machine position: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}"

            self.log_debug(
                f"Position test - Camera: {tvec.flatten()}, Predicted machine: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}",
                "info")
            messagebox.showinfo("Test Result", result)

        except Exception as e:
            self.log_debug(f"Position test failed: {e}", "error")
            messagebox.showerror("Error", f"Test failed: {e}")

    def set_work_offset(self):
        try:
            if self.current_frame is None:
                messagebox.showerror("Error", "No camera frame available")
                return

            # Validate marker length
            try:
                marker_length_str = self.marker_length_var.get().strip()
                if not marker_length_str:
                    self.marker_length = 20.0
                    self.marker_length_var.set("20.0")
                else:
                    self.marker_length = float(marker_length_str)
            except ValueError:
                self.marker_length = 20.0
                self.marker_length_var.set("20.0")
                self.log_debug("Invalid marker length, using default 20.0mm", "error")

            rvec, tvec, norm_pos, _ = self.camera.detect_marker_pose(self.current_frame, self.marker_length)

            if tvec is None:
                messagebox.showerror("Error", "No marker detected")
                return

            # Transform to machine coordinates
            machine_point = self.transform_point(tvec.flatten())

            # Set work offset
            response = self.grbl.set_work_offset(machine_point, coordinate_system=1)
            for line in response:
                self.log_debug(f"OFFSET: {line}", "received")

            result = f"Work offset set to: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}"
            messagebox.showinfo("Success", result)
            self.status_var.set("Work offset set")
            self.log_debug(
                f"Work offset set to: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}", "info")

        except Exception as e:
            self.log_debug(f"Failed to set work offset: {e}", "error")
            messagebox.showerror("Error", f"Failed to set work offset: {e}")

    def on_closing(self):
        self.camera_running = False
        self.camera.disconnect()
        self.grbl.disconnect()
        self.log_debug("Application closing", "info")
        self.root.destroy()


def main():
    root = tk.Tk()
    app = RegistrationGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()