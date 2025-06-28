"""
SVG Routes Overlay Component
Handles SVG route loading, coordinate transformation, and overlay rendering
Implements RoutesOverlay interface for dependency injection
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple, Callable
import os
from services.overlays.overlay_interface import FrameOverlay


class SVGRoutesOverlay(FrameOverlay):
    """Component for handling SVG routes overlay on camera frames"""

    def __init__(self, registration_manager=None, logger: Optional[Callable] = None):
        self.registration_manager = registration_manager
        self.logger = logger

        # Routes data
        self.routes = []  # List of routes from SVG (in machine coordinates)

        # Display settings
        self.visible = False
        self.route_color = (255, 255, 0)  # Yellow by default (BGR format)
        self.route_thickness = 2

        # Transformation settings
        self.use_registration_transform = True
        self.manual_scale = 1.0
        self.manual_offset = (0, 0)
        self._pixels_per_unit = 10.0  # Default projection scale

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
            from svg.svg_loader import svg_to_routes

            if not os.path.exists(svg_file_path):
                raise FileNotFoundError(f"SVG file not found: {svg_file_path}")

            self.routes = svg_to_routes(svg_file_path, angle_threshold)
            self.log(f"Loaded {len(self.routes)} routes from {svg_file_path}")

        except Exception as e:
            self.log(f"Failed to load routes from SVG: {e}", "error")
            self.routes = []

    def clear_routes(self):
        """Clear all loaded routes"""
        self.routes = []
        self.log("Routes cleared")

    def set_visibility(self, visible: bool):
        """Toggle routes overlay visibility"""
        self.visible = visible

    def is_visible(self) -> bool:
        """Check if overlay is visible"""
        return self.visible

    def get_routes_count(self) -> int:
        """Get number of loaded routes"""
        return len(self.routes)

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

    def calibrate_projection(self, known_points: List[Tuple[Tuple[float, float], Tuple[int, int]]]):
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
                machine_dist = np.sqrt((machine_p2[0] - machine_p1[0]) ** 2 +
                                       (machine_p2[1] - machine_p1[1]) ** 2)
                pixel_dist = np.sqrt((pixel_p2[0] - pixel_p1[0]) ** 2 +
                                     (pixel_p2[1] - pixel_p1[1]) ** 2)

                if machine_dist > 0:
                    ratio = pixel_dist / machine_dist
                    total_ratio += ratio
                    valid_points += 1

            if valid_points > 0:
                self._pixels_per_unit = total_ratio / valid_points
                self.log(f"Route overlay projection calibrated: {self._pixels_per_unit:.2f} pixels/unit")

        except Exception as e:
            self.log(f"Failed to calibrate route overlay projection: {e}", "error")

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

    def apply_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply routes overlay to the given frame

        Args:
            frame: Input frame to draw on

        Returns:
            Frame with routes overlay applied (if visible and routes available)
        """
        if not self.visible or not self.routes:
            return frame

        return self._draw_routes_overlay(frame)

    def _machine_to_camera_coordinates(self, machine_point: Tuple[float, float],
                                       frame_shape: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """
        Transform a point from machine coordinates to camera pixel coordinates

        Args:
            machine_point: (x, y) point in machine coordinates
            frame_shape: (height, width) of the current frame

        Returns:
            (x, y) point in camera pixel coordinates, or None if transformation fails
        """
        try:
            if (self.use_registration_transform and
                    self.registration_manager and
                    self.registration_manager.is_registered()):

                # Use registration manager for inverse transformation
                machine_3d = np.array([machine_point[0], machine_point[1], 0.0])

                # Get transformation matrices
                R = self.registration_manager.transformation_matrix
                t = self.registration_manager.translation_vector

                # Inverse transform: camera_point = R^-1 * (machine_point - t)
                R_inv = np.linalg.inv(R)
                camera_3d = R_inv @ (machine_3d - t)

                # Project to camera pixel coordinates
                return self._camera_3d_to_pixel(camera_3d, frame_shape)

            else:
                # Fallback to manual transformation
                screen_x = int((machine_point[0] * self.manual_scale) + self.manual_offset[0])
                screen_y = int((machine_point[1] * self.manual_scale) + self.manual_offset[1])
                return (screen_x, screen_y)

        except Exception as e:
            self.log(f"Error transforming coordinates: {e}", "error")
            return None

    def _camera_3d_to_pixel(self, camera_3d: np.ndarray, frame_shape: Tuple[int, int]) -> Tuple[int, int]:
        """
        Convert 3D camera coordinates to 2D pixel coordinates

        Args:
            camera_3d: 3D point in camera coordinate system
            frame_shape: (height, width) of the current frame

        Returns:
            (x, y) pixel coordinates
        """
        frame_height, frame_width = frame_shape

        # Convert to pixel coordinates with origin at frame center
        pixel_x = int(frame_width / 2 + camera_3d[0] * self._pixels_per_unit)
        pixel_y = int(frame_height / 2 - camera_3d[1] * self._pixels_per_unit)  # Y-axis inverted

        return (pixel_x, pixel_y)

    def _draw_routes_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Draw routes overlay on the frame using coordinate transformation

        Args:
            frame: Input frame to draw on

        Returns:
            Frame with routes overlay
        """
        overlay_frame = frame.copy()

        try:
            routes_drawn = 0
            frame_shape = frame.shape[:2]  # (height, width)

            for route in self.routes:
                if len(route) < 2:
                    continue

                # Convert route points from machine to camera coordinates
                screen_points = []
                for machine_x, machine_y in route:
                    screen_coords = self._machine_to_camera_coordinates(
                        (machine_x, machine_y), frame_shape)
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
                                      (end_point[0] - 2, end_point[1] - 2),
                                      (end_point[0] + 2, end_point[1] + 2),
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