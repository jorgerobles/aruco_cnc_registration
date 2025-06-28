"""
SVG Routes AR Overlay Component - Augmented Reality Implementation
Routes are fixed to the camera view and move with it as true AR overlay
Routes appear stationary in the real world (machine coordinate system)
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple, Callable
import os
from services.overlays.overlay_interface import FrameOverlay


class SVGRoutesOverlay(FrameOverlay):
    """AR Component for displaying SVG routes fixed to camera view in machine coordinates"""

    def __init__(self, registration_manager=None, logger: Optional[Callable] = None):
        self.registration_manager = registration_manager
        self.logger = logger

        # Routes data - always stored in machine coordinates
        self.routes = []  # List of routes in machine coordinates (mm)
        self.svg_routes_original = []  # Original SVG coordinates for reference

        # Display settings
        self.visible = False
        self.route_color = (255, 255, 0)  # Yellow by default (BGR format)
        self.route_thickness = 2
        self.show_route_points = True
        self.show_start_end_markers = True

        # Transform settings
        self.use_registration_transform = True
        self.manual_scale = 1.0
        self.manual_offset = (0, 0)

        # Camera view state - this is what makes it AR
        self.current_camera_position = None  # Current camera position in machine coordinates
        self.camera_scale_factor = 10.0  # How many pixels per mm at current camera distance
        self.camera_rotation = 0.0  # Camera rotation in degrees (future enhancement)

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def load_routes_from_svg(self, svg_file_path: str, angle_threshold: float = 5.0):
        """
        Load routes from SVG file and convert to machine coordinates using registration

        Args:
            svg_file_path: Path to the SVG file
            angle_threshold: Angle threshold for path conversion
        """
        try:
            # Import svg_loader (assuming it's in the same directory or PYTHONPATH)
            from svg.svg_loader import svg_to_routes, scale_from_svg

            if not os.path.exists(svg_file_path):
                raise FileNotFoundError(f"SVG file not found: {svg_file_path}")

            # Extract SVG scale information to estimate display scale
            try:
                svg_scale_x, svg_scale_y = scale_from_svg(svg_file_path)
                # Use average scale as initial camera scale estimate
                estimated_scale = (svg_scale_x + svg_scale_y) / 2

                # Set a reasonable initial camera scale factor
                if estimated_scale > 0:
                    # Scale down for AR display - we want routes to appear at reasonable size on screen
                    self.camera_scale_factor = min(estimated_scale / 5.0, 20.0)  # Cap at 20 px/mm
                    self.camera_scale_factor = max(self.camera_scale_factor, 2.0)  # Minimum 2 px/mm

                self.log(f"SVG scale: {svg_scale_x:.2f}x{svg_scale_y:.2f} mm/unit, "
                        f"AR display scale: {self.camera_scale_factor:.2f} px/mm")

            except Exception as e:
                self.log(f"Could not extract SVG scale info: {e}", "warning")

            # Load SVG routes in original SVG coordinates
            svg_routes = svg_to_routes(svg_file_path, angle_threshold)
            self.svg_routes_original = svg_routes.copy()

            # Always transform to machine coordinates for AR overlay
            if (self.use_registration_transform and
                self.registration_manager and
                self.registration_manager.is_registered()):

                self.routes = self._transform_svg_routes_to_machine(svg_routes)
                self.log(f"Loaded {len(self.routes)} routes and transformed to machine coordinates for AR")
            else:
                # In manual mode, treat SVG coordinates as machine coordinates
                self.routes = svg_routes
                self.log(f"Loaded {len(self.routes)} routes in manual mode for AR")

        except Exception as e:
            self.log(f"Failed to load routes from SVG: {e}", "error")
            self.routes = []
            self.svg_routes_original = []

    def _transform_svg_routes_to_machine(self, svg_routes: List[List[Tuple[float, float]]]) -> List[List[Tuple[float, float]]]:
        """
        Transform SVG routes to machine coordinates using the registration manager

        Args:
            svg_routes: List of routes in SVG coordinates

        Returns:
            List of routes in machine coordinates
        """
        machine_routes = []

        for route in svg_routes:
            machine_route = []
            for x, y in route:
                # Convert SVG point to machine coordinates
                svg_point_3d = np.array([x, y, 0.0])

                try:
                    # Transform using registration manager
                    machine_point_3d = self.registration_manager.transform_point(svg_point_3d)
                    # Extract x, y for 2D route
                    machine_route.append((machine_point_3d[0], machine_point_3d[1]))
                except Exception as e:
                    self.log(f"Error transforming point {x}, {y}: {e}", "error")
                    # Fallback to original coordinates
                    machine_route.append((x, y))

            if machine_route:
                machine_routes.append(machine_route)

        return machine_routes

    def update_camera_view(self, camera_position_3d: np.ndarray, scale_factor: Optional[float] = None):
        """
        Update the AR overlay based on current camera position in machine coordinates

        Args:
            camera_position_3d: Current camera position as [x, y, z] in machine coordinates (mm)
            scale_factor: Optional override for camera scale factor (pixels per mm)
        """
        # Store camera position (take only x, y for 2D overlay)
        self.current_camera_position = (camera_position_3d[0], camera_position_3d[1])

        if scale_factor is not None:
            self.camera_scale_factor = scale_factor

        self.log(f"AR camera updated: position=({self.current_camera_position[0]:.1f}, "
                f"{self.current_camera_position[1]:.1f}), scale={self.camera_scale_factor:.1f} px/mm")

    def update_camera_from_registration(self):
        """
        Update camera view automatically using current registration manager state
        This should be called when you know the camera has moved
        """
        if not self.registration_manager or not self.registration_manager.is_registered():
            return

        try:
            # Get current camera position from registration manager
            # This would typically come from your camera system or tracking
            # For now, we'll estimate from the registration center point
            calibration_points = self.registration_manager.get_calibration_points_count()
            if calibration_points > 0:
                # Use center of calibration points as approximate camera position
                machine_positions = self.registration_manager.get_machine_positions()
                if machine_positions:
                    center_x = sum(pos[0] for pos in machine_positions) / len(machine_positions)
                    center_y = sum(pos[1] for pos in machine_positions) / len(machine_positions)
                    center_z = sum(pos[2] for pos in machine_positions) / len(machine_positions)

                    estimated_camera_pos = np.array([center_x, center_y, center_z])
                    self.update_camera_view(estimated_camera_pos)

        except Exception as e:
            self.log(f"Error updating camera from registration: {e}", "error")

    def machine_to_camera_pixel(self, machine_x: float, machine_y: float,
                               frame_shape: Tuple[int, int]) -> Tuple[int, int]:
        """
        Convert machine coordinates to camera pixel coordinates for AR overlay

        Args:
            machine_x, machine_y: Point in machine coordinates (mm)
            frame_shape: (height, width) of camera frame

        Returns:
            (pixel_x, pixel_y) coordinates for drawing on camera frame
        """
        frame_height, frame_width = frame_shape

        if self.current_camera_position is None:
            # Fallback: center everything on frame center
            camera_x, camera_y = frame_width / 2, frame_height / 2
        else:
            camera_x, camera_y = self.current_camera_position

        # Calculate relative position from camera viewpoint
        relative_x = machine_x - camera_x
        relative_y = machine_y - camera_y

        # Convert to pixel coordinates
        # Camera is at frame center, positive X goes right, positive Y goes up
        pixel_x = int(frame_width / 2 + relative_x * self.camera_scale_factor)
        pixel_y = int(frame_height / 2 - relative_y * self.camera_scale_factor)  # Y inverted for screen

        return (pixel_x, pixel_y)

    def set_camera_scale_factor(self, scale_factor: float):
        """Set the camera scale factor (pixels per mm)"""
        self.camera_scale_factor = max(0.1, min(scale_factor, 100.0))
        self.log(f"Camera scale factor set to {self.camera_scale_factor:.1f} px/mm")

    def get_camera_info(self) -> dict:
        """Get current camera AR overlay information"""
        return {
            'camera_position': self.current_camera_position,
            'camera_scale_factor': self.camera_scale_factor,
            'camera_rotation': self.camera_rotation,
            'routes_count': len(self.routes),
            'registration_available': (self.registration_manager and
                                     self.registration_manager.is_registered())
        }

    def clear_routes(self):
        """Clear all loaded routes"""
        self.routes = []
        self.svg_routes_original = []
        self.log("AR overlay routes cleared")

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

    def set_display_options(self, show_points: bool = True, show_markers: bool = True):
        """Set display options for routes"""
        self.show_route_points = show_points
        self.show_start_end_markers = show_markers

    def set_use_registration_transform(self, use_registration: bool):
        """
        Toggle between registration-based transform and manual transform

        Args:
            use_registration: If True, use registration manager for coordinate transformation.
                            If False, treat SVG coordinates as machine coordinates directly.
        """
        self.use_registration_transform = use_registration

        # Retransform routes based on the new setting
        if self.svg_routes_original:
            if use_registration and self.registration_manager and self.registration_manager.is_registered():
                # Transform to machine coordinates using registration
                self.routes = self._transform_svg_routes_to_machine(self.svg_routes_original)
                self.log("AR overlay switched to registration-based transformation")
            else:
                # Use SVG coordinates directly as machine coordinates
                self.routes = self.svg_routes_original.copy()
                self.log("AR overlay switched to direct SVG coordinates")

    def get_use_registration_transform(self) -> bool:
        """Get current transformation mode"""
        return self.use_registration_transform

    def set_manual_transform(self, scale: float = 1.0, offset: Tuple[int, int] = (0, 0)):
        """Set manual transformation parameters (affects camera scale in manual mode)"""
        self.manual_scale = scale
        self.manual_offset = offset

        # In manual mode, update camera scale factor
        if not self.use_registration_transform:
            self.camera_scale_factor = scale

        self.log(f"AR manual transform set: scale={scale}, offset={offset}")

    def get_manual_transform(self) -> Tuple[float, Tuple[int, int]]:
        """Get current manual transformation parameters"""
        return (self.manual_scale, self.manual_offset)

    def set_registration_manager(self, registration_manager):
        """Set the registration manager and retransform routes if available"""
        self.registration_manager = registration_manager

        # If we have original SVG routes and are using registration mode, retransform them
        if (self.svg_routes_original and
            self.use_registration_transform and
            registration_manager and
            registration_manager.is_registered()):

            self.routes = self._transform_svg_routes_to_machine(self.svg_routes_original)
            self.log("AR overlay routes retransformed with new registration manager")

            # Update camera view from registration
            self.update_camera_from_registration()

    def get_route_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Get the bounding box of all loaded routes in machine coordinates

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

        margin = 5.0  # 5mm margin
        return (min(all_x) - margin, min(all_y) - margin,
                max(all_x) + margin, max(all_y) + margin)

    def get_total_route_length(self) -> float:
        """Calculate total length of all routes in machine coordinates"""
        if not self.routes:
            return 0.0

        total_distance = 0.0

        try:
            for route in self.routes:
                for i in range(len(route) - 1):
                    x1, y1 = route[i]
                    x2, y2 = route[i + 1]
                    distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    total_distance += distance
        except Exception as e:
            self.log(f"Error calculating route length: {e}", "error")

        return total_distance

    def get_routes(self) -> List[List[Tuple[float, float]]]:
        """Get all routes in machine coordinates"""
        return self.routes.copy() if self.routes else []

    def has_routes(self) -> bool:
        """Check if any routes are loaded"""
        return len(self.routes) > 0

    def refresh_transformation(self):
        """Refresh route transformation if registration manager has been updated"""
        if self.svg_routes_original:
            if (self.use_registration_transform and
                self.registration_manager and
                self.registration_manager.is_registered()):

                self.log("Refreshing AR route transformation with registration...")
                self.routes = self._transform_svg_routes_to_machine(self.svg_routes_original)
                self.update_camera_from_registration()
            else:
                self.log("Refreshing AR route transformation without registration...")
                self.routes = self.svg_routes_original.copy()

            self.log("AR route transformation refreshed")

    def apply_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply AR routes overlay to the given frame
        Routes are rendered based on current camera position and appear fixed in machine space

        Args:
            frame: Input camera frame

        Returns:
            Frame with AR routes overlay applied
        """
        if not self.visible or not self.routes:
            return frame

        return self._draw_ar_routes_overlay(frame)

    def _draw_ar_routes_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Draw routes as AR overlay fixed to camera view

        Args:
            frame: Input camera frame

        Returns:
            Frame with AR routes overlay
        """
        overlay_frame = frame.copy()

        try:
            frame_shape = frame.shape[:2]  # (height, width)
            routes_drawn = 0
            total_points_drawn = 0

            for route_idx, route in enumerate(self.routes):
                if len(route) < 2:
                    continue

                # Convert all route points to camera pixel coordinates
                pixel_points = []
                for machine_x, machine_y in route:
                    pixel_x, pixel_y = self.machine_to_camera_pixel(
                        machine_x, machine_y, frame_shape
                    )

                    # Keep points for drawing (OpenCV handles clipping)
                    pixel_points.append((pixel_x, pixel_y))

                if len(pixel_points) < 2:
                    continue

                # Draw lines connecting the points
                points_visible = 0
                for i in range(len(pixel_points) - 1):
                    pt1 = pixel_points[i]
                    pt2 = pixel_points[i + 1]

                    # Draw line - OpenCV handles clipping automatically
                    cv2.line(overlay_frame, pt1, pt2, self.route_color, self.route_thickness)

                    # Count visible points (roughly)
                    if (0 <= pt1[0] < frame.shape[1] and 0 <= pt1[1] < frame.shape[0]):
                        points_visible += 1

                # Draw individual points if enabled
                if self.show_route_points:
                    for pixel_x, pixel_y in pixel_points:
                        if (0 <= pixel_x < frame.shape[1] and 0 <= pixel_y < frame.shape[0]):
                            cv2.circle(overlay_frame, (pixel_x, pixel_y), 1, self.route_color, -1)

                # Draw start and end markers if enabled
                if self.show_start_end_markers and pixel_points:
                    # Start point (green circle)
                    start_point = pixel_points[0]
                    if (0 <= start_point[0] < frame.shape[1] and 0 <= start_point[1] < frame.shape[0]):
                        cv2.circle(overlay_frame, start_point, 4, (0, 255, 0), -1)
                        cv2.circle(overlay_frame, start_point, 5, (0, 0, 0), 1)  # Black outline

                    # End point (red square)
                    end_point = pixel_points[-1]
                    if (0 <= end_point[0] < frame.shape[1] and 0 <= end_point[1] < frame.shape[0]):
                        cv2.rectangle(overlay_frame,
                                    (end_point[0] - 3, end_point[1] - 3),
                                    (end_point[0] + 3, end_point[1] + 3),
                                    (0, 0, 255), -1)
                        cv2.rectangle(overlay_frame,
                                    (end_point[0] - 4, end_point[1] - 4),
                                    (end_point[0] + 4, end_point[1] + 4),
                                    (0, 0, 0), 1)  # Black outline

                if pixel_points:
                    routes_drawn += 1
                    total_points_drawn += len(pixel_points)

            # Draw AR status information
            self._draw_ar_status(overlay_frame, routes_drawn)

            # Draw camera position indicator
            self._draw_camera_position_indicator(overlay_frame, frame_shape)

            # Draw scale reference
            self._draw_ar_scale_reference(overlay_frame, frame_shape)

        except Exception as e:
            self.log(f"Error drawing AR routes overlay: {e}", "error")
            # Add error indicator
            cv2.putText(overlay_frame, "AR overlay error",
                       (10, frame.shape[0] - 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        return overlay_frame

    def _draw_ar_status(self, frame: np.ndarray, routes_drawn: int):
        """Draw AR status information on the frame"""
        status_lines = [
            f"AR Routes: {routes_drawn}/{len(self.routes)}",
            f"Scale: {self.camera_scale_factor:.1f} px/mm"
        ]

        if self.use_registration_transform:
            if (self.registration_manager and self.registration_manager.is_registered()):
                status_lines.append("Mode: AR Registered")
            else:
                status_lines.append("Mode: AR (Reg. N/A)")
        else:
            status_lines.append("Mode: AR Manual")

        if self.current_camera_position:
            status_lines.append(f"Cam: ({self.current_camera_position[0]:.1f}, {self.current_camera_position[1]:.1f})")

        # Draw status box
        for i, line in enumerate(status_lines):
            y_pos = 20 + (i * 20)
            cv2.putText(frame, line, (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.route_color, 1)

    def _draw_camera_position_indicator(self, frame: np.ndarray, frame_shape: Tuple[int, int]):
        """Draw camera position indicator (crosshair at center)"""
        frame_height, frame_width = frame_shape
        center_x, center_y = frame_width // 2, frame_height // 2

        # Draw crosshair
        cv2.line(frame, (center_x - 10, center_y), (center_x + 10, center_y),
                (255, 255, 255), 2)
        cv2.line(frame, (center_x, center_y - 10), (center_x, center_y + 10),
                (255, 255, 255), 2)
        cv2.circle(frame, (center_x, center_y), 3, (0, 255, 255), -1)

    def _draw_ar_scale_reference(self, frame: np.ndarray, frame_shape: Tuple[int, int]):
        """Draw scale reference for AR overlay"""
        try:
            # Draw a 10mm reference line in the bottom-right corner
            reference_length_mm = 10.0
            reference_length_pixels = int(reference_length_mm * self.camera_scale_factor)

            if reference_length_pixels > 20:  # Only draw if visible
                end_x = frame_shape[1] - 20
                start_x = end_x - reference_length_pixels
                y_pos = frame_shape[0] - 20

                # Draw reference line
                cv2.line(frame, (start_x, y_pos), (end_x, y_pos), (255, 255, 255), 2)

                # Draw end markers
                cv2.line(frame, (start_x, y_pos - 5), (start_x, y_pos + 5), (255, 255, 255), 1)
                cv2.line(frame, (end_x, y_pos - 5), (end_x, y_pos + 5), (255, 255, 255), 1)

                # Draw label
                cv2.putText(frame, f"{reference_length_mm:.0f}mm",
                           (start_x, y_pos - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        except Exception as e:
            self.log(f"Error drawing AR scale reference: {e}", "error")

    def export_routes_info(self) -> dict:
        """Export comprehensive AR route information"""
        info = {
            'routes_count': len(self.routes),
            'original_svg_routes_count': len(self.svg_routes_original),
            'route_bounds': self.get_route_bounds(),
            'total_length_mm': self.get_total_route_length(),
            'camera_info': self.get_camera_info(),
            'display_settings': {
                'visible': self.visible,
                'color': self.route_color,
                'thickness': self.route_thickness,
                'show_points': self.show_route_points,
                'show_markers': self.show_start_end_markers,
                'use_registration_transform': self.use_registration_transform,
                'manual_scale': self.manual_scale,
                'manual_offset': self.manual_offset
            },
            'registration_status': {
                'has_registration_manager': self.registration_manager is not None,
                'is_registered': (self.registration_manager and
                                self.registration_manager.is_registered() if self.registration_manager else False)
            }
        }

        return info