"""
Camera Display Widget
Handles camera feed display, marker visualization, and routes overlay
"""

import tkinter as tk
import cv2
import numpy as np
from PIL import Image, ImageTk
from typing import Optional, Callable, List, Tuple
import os


class CameraDisplay:
    """Widget for displaying camera feed with marker detection overlay and routes"""

    def __init__(self, parent, camera_manager, registration_manager=None, logger: Optional[Callable] = None):
        self.parent = parent
        self.camera_manager = camera_manager
        self.registration_manager = registration_manager
        self.logger = logger

        # Display state
        self.camera_running = False
        self.current_frame = None
        self.marker_length = 15.0

        # Routes overlay state
        self.routes = []  # List of routes from SVG (in machine coordinates)
        self.show_routes = False
        self.route_color = (255, 255, 0)  # Yellow by default
        self.route_thickness = 2
        self.use_registration_transform = True  # Use registration manager for transformation
        self.manual_scale = 1.0  # Manual scale factor (fallback)
        self.manual_offset = (0, 0)  # Manual offset (fallback)

        # Create canvas
        self.canvas = tk.Canvas(parent, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def load_routes_from_svg(self, svg_file_path: str, angle_threshold: float = 5.0):
        """
        Load routes from SVG file using the svg_loader module

        Args:
            svg_file_path: Path to the SVG file
            angle_threshold: Angle threshold for path conversion
        """
        try:
            # Import svg_loader (assuming it's in the same directory or PYTHONPATH)
            from svg_loader import svg_to_routes

            if not os.path.exists(svg_file_path):
                raise FileNotFoundError(f"SVG file not found: {svg_file_path}")

            self.routes = svg_to_routes(svg_file_path, angle_threshold)
            self.log(f"Loaded {len(self.routes)} routes from {svg_file_path}")

        except Exception as e:
            self.log(f"Failed to load routes from SVG: {e}", "error")
            self.routes = []

    def set_routes_visibility(self, visible: bool):
        """Toggle routes overlay visibility"""
        self.show_routes = visible

    def set_route_color(self, color: Tuple[int, int, int]):
        """Set the color for route overlay (BGR format)"""
        self.route_color = color

    def set_route_thickness(self, thickness: int):
        """Set the thickness of route lines"""
        self.route_thickness = max(1, thickness)

    def set_registration_manager(self, registration_manager):
        """Set the registration manager for coordinate transformation"""
        self.registration_manager = registration_manager

    def set_use_registration_transform(self, use_registration: bool):
        """Toggle between registration-based transform and manual transform"""
        self.use_registration_transform = use_registration

    def set_manual_transform(self, scale: float = 1.0, offset: Tuple[int, int] = (0, 0)):
        """
        Set manual transformation parameters (fallback when registration not available)

        Args:
            scale: Scale factor for routes
            offset: (x, y) offset for routes positioning
        """
        self.manual_scale = scale
        self.manual_offset = offset

    def clear_routes(self):
        """Clear all loaded routes"""
        self.routes = []
        self.log("Routes cleared")

    def start_feed(self):
        """Start camera feed display"""
        self.camera_running = True
        self._update_feed()

    def stop_feed(self):
        """Stop camera feed display"""
        self.camera_running = False

    def set_marker_length(self, length: float):
        """Set marker length for pose detection"""
        self.marker_length = length

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current camera frame"""
        return self.current_frame.copy() if self.current_frame is not None else None

    def _update_feed(self):
        """Update camera feed display"""
        if not self.camera_running:
            return

        frame = self.camera_manager.capture_frame()
        if frame is not None:
            self.log(f"Frame captured: {frame.shape}")
            self.current_frame = frame.copy()

            # Try to detect markers and annotate frame
            display_frame = self._process_frame(frame)

            # Add routes overlay if enabled
            if self.show_routes and self.routes:
                display_frame = self._draw_routes_overlay(display_frame)

            # Display the frame
            self._display_frame(display_frame)
        else:
            self.log("No frame captured", "error")
        # Schedule next update
        self.parent.after(50, self._update_feed)

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process frame with marker detection and annotation"""
        try:
            rvec, tvec, norm_pos, annotated_frame = self.camera_manager.detect_marker_pose(
                frame, self.marker_length)

            if tvec is not None:
                # Draw marker info
                cv2.putText(annotated_frame, "Marker detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(annotated_frame, f"Pos: {tvec.flatten()}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                return annotated_frame
            else:
                cv2.putText(frame, "No marker detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                return frame

        except Exception as e:
            self.log(f"Marker detection error: {e}", "error")
            cv2.putText(frame, "Detection error", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return frame

    def _machine_to_camera_coordinates(self, machine_point: Tuple[float, float]) -> Optional[Tuple[int, int]]:
        """
        Transform a point from machine coordinates to camera pixel coordinates

        Args:
            machine_point: (x, y) point in machine coordinates

        Returns:
            (x, y) point in camera pixel coordinates, or None if transformation fails
        """
        try:
            if (self.use_registration_transform and
                self.registration_manager and
                self.registration_manager.is_registered()):

                # Use registration manager for inverse transformation
                # Note: We need to solve for camera coordinates from machine coordinates
                # This requires inverting the transformation

                # Create 3D point (assume z=0 for 2D routes)
                machine_3d = np.array([machine_point[0], machine_point[1], 0.0])

                # Get transformation matrices
                R = self.registration_manager.transformation_matrix
                t = self.registration_manager.translation_vector

                # Inverse transform: camera_point = R^-1 * (machine_point - t)
                R_inv = np.linalg.inv(R)
                camera_3d = R_inv @ (machine_3d - t)

                # Project to camera pixel coordinates
                # This is a simplified projection - you might need to adjust based on your camera setup
                return self._camera_3d_to_pixel(camera_3d)

            else:
                # Fallback to manual transformation
                screen_x = int((machine_point[0] * self.manual_scale) + self.manual_offset[0])
                screen_y = int((machine_point[1] * self.manual_scale) + self.manual_offset[1])
                return (screen_x, screen_y)

        except Exception as e:
            self.log(f"Error transforming coordinates: {e}", "error")
            return None

    def _camera_3d_to_pixel(self, camera_3d: np.ndarray) -> Tuple[int, int]:
        """
        Convert 3D camera coordinates to 2D pixel coordinates
        This is a simplified projection - adjust based on your camera calibration

        Args:
            camera_3d: 3D point in camera coordinate system

        Returns:
            (x, y) pixel coordinates
        """
        if self.current_frame is None:
            return (0, 0)

        # Simple orthographic projection (you may need perspective projection)
        # Scale factor to convert from camera units to pixels
        pixels_per_unit = getattr(self, '_pixels_per_unit', 10.0)  # Default or calibrated value

        frame_height, frame_width = self.current_frame.shape[:2]

        # Convert to pixel coordinates with origin at frame center
        pixel_x = int(frame_width/2 + camera_3d[0] * pixels_per_unit)
        pixel_y = int(frame_height/2 - camera_3d[1] * pixels_per_unit)  # Y-axis inverted

        return (pixel_x, pixel_y)
    def _draw_routes_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Draw routes overlay on the frame using registration-based coordinate transformation

        Args:
            frame: Input frame to draw on

        Returns:
            Frame with routes overlay
        """
        overlay_frame = frame.copy()

        try:
            routes_drawn = 0

            for route in self.routes:
                if len(route) < 2:
                    continue

                # Convert route points from machine to camera coordinates
                screen_points = []
                for machine_x, machine_y in route:
                    screen_coords = self._machine_to_camera_coordinates((machine_x, machine_y))
                    if screen_coords is not None:
                        screen_points.append(screen_coords)

                if len(screen_points) < 2:
                    continue

                # Draw lines connecting the points
                valid_lines = 0
                for i in range(len(screen_points) - 1):
                    pt1 = screen_points[i]
                    pt2 = screen_points[i + 1]

                    # Check if points are within frame bounds
                    if (0 <= pt1[0] < frame.shape[1] and 0 <= pt1[1] < frame.shape[0] and
                        0 <= pt2[0] < frame.shape[1] and 0 <= pt2[1] < frame.shape[0]):

                        cv2.line(overlay_frame, pt1, pt2, self.route_color, self.route_thickness)
                        valid_lines += 1

                # Draw start point as a small circle
                if screen_points and valid_lines > 0:
                    start_point = screen_points[0]
                    if (0 <= start_point[0] < frame.shape[1] and
                        0 <= start_point[1] < frame.shape[0]):
                        cv2.circle(overlay_frame, start_point, 3, (0, 255, 0), -1)  # Green start

                # Draw end point as a small square
                if len(screen_points) > 1 and valid_lines > 0:
                    end_point = screen_points[-1]
                    if (0 <= end_point[0] < frame.shape[1] and
                        0 <= end_point[1] < frame.shape[0]):
                        # Draw small square for end point
                        cv2.rectangle(overlay_frame,
                                    (end_point[0]-2, end_point[1]-2),
                                    (end_point[0]+2, end_point[1]+2),
                                    (0, 0, 255), -1)  # Red end

                if valid_lines > 0:
                    routes_drawn += 1

            # Add status text
            status_text = f"Routes: {routes_drawn}/{len(self.routes)}"
            if (self.use_registration_transform and
                self.registration_manager and
                self.registration_manager.is_registered()):
                status_text += " (Registered)"
            else:
                status_text += " (Manual)"

            cv2.putText(overlay_frame, status_text,
                      (10, frame.shape[0] - 20),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.route_color, 1)

        except Exception as e:
            self.log(f"Error drawing routes overlay: {e}", "error")
            # Add error indicator
            cv2.putText(overlay_frame, "Route overlay error",
                      (10, frame.shape[0] - 40),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        return overlay_frame

    def _display_frame(self, frame: np.ndarray):
        """Display frame on canvas with proper scaling"""
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)

        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width > 1 and canvas_height > 1:
            # Scale image to fit canvas while maintaining aspect ratio
            pil_image = self._scale_image(pil_image, canvas_width, canvas_height)

        # Convert to PhotoImage and display
        photo = ImageTk.PhotoImage(pil_image)
        self.canvas.delete("all")

        # Center the image on the canvas
        x_offset = (canvas_width - pil_image.width) // 2
        y_offset = (canvas_height - pil_image.height) // 2
        self.canvas.create_image(
            x_offset + pil_image.width // 2,
            y_offset + pil_image.height // 2,
            image=photo
        )

        # Keep a reference to prevent garbage collection
        self.canvas.image = photo

    def _scale_image(self, image: Image.Image, canvas_width: int, canvas_height: int) -> Image.Image:
        """Scale image to fit canvas while maintaining aspect ratio"""
        img_aspect = image.width / image.height
        canvas_aspect = canvas_width / canvas_height

        if img_aspect > canvas_aspect:
            # Image is wider than canvas
            new_width = canvas_width
            new_height = int(canvas_width / img_aspect)
        else:
            # Image is taller than canvas
            new_height = canvas_height
            new_width = int(canvas_height * img_aspect)

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def capture_marker_pose(self) -> tuple:
        """
        Capture current marker pose
        Returns (rvec, tvec, norm_pos) or (None, None, None) if no marker detected
        """
        if self.current_frame is None:
            return None, None, None

        try:
            return self.camera_manager.detect_marker_pose(self.current_frame, self.marker_length)[:3]
        except Exception as e:
            self.log(f"Failed to capture marker pose: {e}", "error")
            return None, None, None

    def calibrate_camera_projection(self, known_points: List[Tuple[Tuple[float, float], Tuple[int, int]]]):
        """
        Calibrate the camera projection parameters based on known point correspondences

        Args:
            known_points: List of ((machine_x, machine_y), (pixel_x, pixel_y)) correspondences
        """
        if len(known_points) < 2:
            self.log("Need at least 2 point correspondences for camera projection calibration", "error")
            return

        try:
            # Simple calibration for pixels_per_unit
            total_ratio = 0
            valid_points = 0

            for i in range(len(known_points) - 1):
                machine_p1, pixel_p1 = known_points[i]
                machine_p2, pixel_p2 = known_points[i + 1]

                # Calculate distances
                machine_dist = np.sqrt((machine_p2[0] - machine_p1[0])**2 +
                                     (machine_p2[1] - machine_p1[1])**2)
                pixel_dist = np.sqrt((pixel_p2[0] - pixel_p1[0])**2 +
                                   (pixel_p2[1] - pixel_p1[1])**2)

                if machine_dist > 0:
                    ratio = pixel_dist / machine_dist
                    total_ratio += ratio
                    valid_points += 1

            if valid_points > 0:
                # Update the pixels_per_unit in the projection function
                self._pixels_per_unit = total_ratio / valid_points
                self.log(f"Camera projection calibrated: {self._pixels_per_unit:.2f} pixels/unit")

        except Exception as e:
            self.log(f"Failed to calibrate camera projection: {e}", "error")

    def get_route_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Get the bounding box of all loaded routes

        Returns:
            (min_x, min_y, max_x, max_y) or None if no routes loaded
        """
        if not self.routes:
            return None

        all_x = []
        all_y = []

        for route in self.routes:
            for x, y in route:
                all_x.append(x)
                all_y.append(y)

        if not all_x:
            return None

        return (min(all_x), min(all_y), max(all_x), max(all_y))