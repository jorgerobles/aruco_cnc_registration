"""
SVG Routes AR Overlay Component - Enhanced with Debug Information
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

        # Debug settings
        self.show_debug_info = True
        self.show_route_bounds = True
        self.show_coordinate_grid = False
        self.debug_text_size = 0.4
        self.debug_line_spacing = 15

        # Transform settings
        self.use_registration_transform = True
        self.manual_scale = 1.0
        self.manual_offset = (0, 0)

        # Camera view state - this is what makes it AR
        self.current_camera_position = None  # Current camera position in machine coordinates
        self.camera_scale_factor = 10.0  # How many pixels per mm at current camera distance
        self.camera_rotation = 0.0  # Camera rotation in degrees (future enhancement)

        # Debug data storage
        self.route_debug_info = {}
        self.last_load_timestamp = None

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def enable_debug_display(self, enabled: bool = True):
        """Enable or disable debug information display"""
        self.show_debug_info = enabled
        self.log(f"Debug display {'enabled' if enabled else 'disabled'}")

    def enable_route_bounds_display(self, enabled: bool = True):
        """Enable or disable route bounds display"""
        self.show_route_bounds = enabled
        self.log(f"Route bounds display {'enabled' if enabled else 'disabled'}")

    def enable_coordinate_grid(self, enabled: bool = True):
        """Enable or disable coordinate grid display"""
        self.show_coordinate_grid = enabled
        self.log(f"Coordinate grid {'enabled' if enabled else 'disabled'}")

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
            import time

            if not os.path.exists(svg_file_path):
                raise FileNotFoundError(f"SVG file not found: {svg_file_path}")

            self.last_load_timestamp = time.time()

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

            # Store original SVG bounds for debug
            svg_bounds = self._calculate_bounds(svg_routes)

            # Always transform to machine coordinates for AR overlay
            if (self.use_registration_transform and
                self.registration_manager and
                self.registration_manager.is_registered()):

                self.routes = self._transform_svg_routes_to_machine(svg_routes)
                transform_mode = "registration"
                self.log(f"Loaded {len(self.routes)} routes and transformed to machine coordinates for AR")
            else:
                # In manual mode, treat SVG coordinates as machine coordinates
                self.routes = svg_routes
                transform_mode = "manual"
                self.log(f"Loaded {len(self.routes)} routes in manual mode for AR")

            # Calculate machine coordinate bounds
            machine_bounds = self._calculate_bounds(self.routes)

            # Store comprehensive debug information
            self._store_route_debug_info(svg_file_path, svg_bounds, machine_bounds, transform_mode)

            # Log detailed coordinate information
            self._log_route_coordinate_debug()

        except Exception as e:
            self.log(f"Failed to load routes from SVG: {e}", "error")
            self.routes = []
            self.svg_routes_original = []
            self.route_debug_info = {}

    def _calculate_bounds(self, routes: List[List[Tuple[float, float]]]) -> dict:
        """Calculate bounds and statistics for a set of routes"""
        if not routes:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0,
                   "width": 0, "height": 0, "center_x": 0, "center_y": 0, "total_points": 0}

        all_x = []
        all_y = []
        total_points = 0

        for route in routes:
            for x, y in route:
                all_x.append(x)
                all_y.append(y)
                total_points += 1

        if not all_x:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0,
                   "width": 0, "height": 0, "center_x": 0, "center_y": 0, "total_points": 0}

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        width = max_x - min_x
        height = max_y - min_y
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        return {
            "min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y,
            "width": width, "height": height, "center_x": center_x, "center_y": center_y,
            "total_points": total_points
        }

    def _store_route_debug_info(self, svg_file: str, svg_bounds: dict, machine_bounds: dict, transform_mode: str):
        """Store comprehensive debug information about loaded routes"""

        # Calculate route statistics
        route_lengths = []
        route_point_counts = []

        for route in self.routes:
            route_length = 0.0
            point_count = len(route)
            route_point_counts.append(point_count)

            for i in range(len(route) - 1):
                x1, y1 = route[i]
                x2, y2 = route[i + 1]
                route_length += np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            route_lengths.append(route_length)

        # Store individual route details (first 5 routes for brevity)
        individual_routes = []
        for i, route in enumerate(self.routes[:5]):
            route_info = {
                "index": i,
                "point_count": len(route),
                "length_mm": route_lengths[i] if i < len(route_lengths) else 0,
                "start_point": route[0] if route else None,
                "end_point": route[-1] if route else None,
                "bounds": self._calculate_bounds([route])
            }
            individual_routes.append(route_info)

        self.route_debug_info = {
            "file_path": svg_file,
            "load_timestamp": self.last_load_timestamp,
            "transform_mode": transform_mode,
            "route_count": len(self.routes),
            "svg_bounds": svg_bounds,
            "machine_bounds": machine_bounds,
            "total_length_mm": sum(route_lengths),
            "average_route_length_mm": np.mean(route_lengths) if route_lengths else 0,
            "total_points": sum(route_point_counts),
            "average_points_per_route": np.mean(route_point_counts) if route_point_counts else 0,
            "individual_routes": individual_routes,
            "registration_info": self._get_registration_debug_info() if self.registration_manager else None
        }

    def _get_registration_debug_info(self) -> dict:
        """Get debug information about registration status"""
        if not self.registration_manager:
            return {"available": False}

        try:
            reg_stats = self.registration_manager.get_registration_stats()
            return {
                "available": True,
                "is_registered": reg_stats["is_registered"],
                "point_count": reg_stats["point_count"],
                "registration_error": reg_stats.get("registration_error"),
                "has_sufficient_points": reg_stats["has_sufficient_points"]
            }
        except Exception as e:
            return {"available": True, "error": str(e)}

    def _log_route_coordinate_debug(self):
        """Log detailed coordinate debug information"""
        if not self.route_debug_info:
            return

        info = self.route_debug_info

        self.log("="*60, "info")
        self.log("ROUTE COORDINATE DEBUG INFORMATION", "info")
        self.log("="*60, "info")

        # Basic information
        self.log(f"File: {os.path.basename(info['file_path'])}", "info")
        self.log(f"Transform Mode: {info['transform_mode']}", "info")
        self.log(f"Routes Loaded: {info['route_count']}", "info")
        self.log(f"Total Points: {info['total_points']}", "info")
        self.log(f"Total Length: {info['total_length_mm']:.2f} mm", "info")

        # SVG coordinate space
        svg = info['svg_bounds']
        self.log(f"\nSVG Coordinate Space:", "info")
        self.log(f"  Bounds: X({svg['min_x']:.2f} to {svg['max_x']:.2f}) Y({svg['min_y']:.2f} to {svg['max_y']:.2f})", "info")
        self.log(f"  Size: {svg['width']:.2f} x {svg['height']:.2f} units", "info")
        self.log(f"  Center: ({svg['center_x']:.2f}, {svg['center_y']:.2f})", "info")

        # Machine coordinate space
        machine = info['machine_bounds']
        self.log(f"\nMachine Coordinate Space:", "info")
        self.log(f"  Bounds: X({machine['min_x']:.2f} to {machine['max_x']:.2f}) Y({machine['min_y']:.2f} to {machine['max_y']:.2f})", "info")
        self.log(f"  Size: {machine['width']:.2f} x {machine['height']:.2f} mm", "info")
        self.log(f"  Center: ({machine['center_x']:.2f}, {machine['center_y']:.2f}) mm", "info")

        # Registration information
        if info['registration_info'] and info['registration_info']['available']:
            reg = info['registration_info']
            self.log(f"\nRegistration Status:", "info")
            self.log(f"  Registered: {reg.get('is_registered', False)}", "info")
            self.log(f"  Calibration Points: {reg.get('point_count', 0)}", "info")
            if reg.get('registration_error') is not None:
                self.log(f"  Registration Error: {reg['registration_error']:.3f} mm", "info")

        # Individual route details
        self.log(f"\nFirst {len(info['individual_routes'])} Routes:", "info")
        for route_info in info['individual_routes']:
            self.log(f"  Route {route_info['index']}: {route_info['point_count']} points, "
                    f"{route_info['length_mm']:.2f}mm", "info")
            if route_info['start_point'] and route_info['end_point']:
                start = route_info['start_point']
                end = route_info['end_point']
                self.log(f"    Start: ({start[0]:.2f}, {start[1]:.2f}) -> End: ({end[0]:.2f}, {end[1]:.2f})", "info")

        # Camera settings
        self.log(f"\nCamera AR Settings:", "info")
        self.log(f"  Scale Factor: {self.camera_scale_factor:.2f} pixels/mm", "info")
        if self.current_camera_position:
            pos = self.current_camera_position
            self.log(f"  Camera Position: ({pos[0]:.2f}, {pos[1]:.2f}) mm", "info")
        else:
            self.log(f"  Camera Position: Not set", "info")

        self.log("="*60, "info")

    def _transform_svg_routes_to_machine(self, svg_routes: List[List[Tuple[float, float]]]) -> List[List[Tuple[float, float]]]:
        """
        Transform SVG routes to machine coordinates using the registration manager

        Args:
            svg_routes: List of routes in SVG coordinates

        Returns:
            List of routes in machine coordinates
        """
        machine_routes = []
        transform_errors = []

        for route_idx, route in enumerate(svg_routes):
            machine_route = []
            route_errors = 0

            for point_idx, (x, y) in enumerate(route):
                # Convert SVG point to machine coordinates
                svg_point_3d = np.array([x, y, 0.0])

                try:
                    # Transform using registration manager
                    machine_point_3d = self.registration_manager.transform_point(svg_point_3d)
                    # Extract x, y for 2D route
                    machine_route.append((machine_point_3d[0], machine_point_3d[1]))
                except Exception as e:
                    self.log(f"Error transforming route {route_idx} point {point_idx} ({x}, {y}): {e}", "error")
                    # Fallback to original coordinates
                    machine_route.append((x, y))
                    route_errors += 1

            if machine_route:
                machine_routes.append(machine_route)
                transform_errors.append(route_errors)

        # Log transformation summary
        total_errors = sum(transform_errors)
        if total_errors > 0:
            self.log(f"Transform completed with {total_errors} errors across {len(transform_errors)} routes", "warning")
        else:
            self.log(f"Transform completed successfully for {len(machine_routes)} routes", "info")

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

        # Update debug info with new camera position
        if self.route_debug_info:
            self.route_debug_info["current_camera_position"] = self.current_camera_position
            self.route_debug_info["current_scale_factor"] = self.camera_scale_factor

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
        self.route_debug_info = {}
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

            # Update debug info with new transformation
            machine_bounds = self._calculate_bounds(self.routes)
            svg_bounds = self._calculate_bounds(self.svg_routes_original)
            transform_mode = "registration" if use_registration else "manual"

            if hasattr(self, 'route_debug_info') and self.route_debug_info:
                self.route_debug_info["machine_bounds"] = machine_bounds
                self.route_debug_info["transform_mode"] = transform_mode
                self._log_route_coordinate_debug()

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

            # Update debug info
            machine_bounds = self._calculate_bounds(self.routes)
            if hasattr(self, 'route_debug_info') and self.route_debug_info:
                self.route_debug_info["machine_bounds"] = machine_bounds
                self.route_debug_info["registration_info"] = self._get_registration_debug_info()
                self._log_route_coordinate_debug()

    def get_route_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Get the bounding box of all loaded routes in machine coordinates

        Returns:
            (min_x, min_y, max_x, max_y) or None if no routes loaded
        """
        if not self.routes:
            return None

        bounds = self._calculate_bounds(self.routes)
        margin = 5.0  # 5mm margin
        return (bounds["min_x"] - margin, bounds["min_y"] - margin,
                bounds["max_x"] + margin, bounds["max_y"] + margin)

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

            # Update debug info
            machine_bounds = self._calculate_bounds(self.routes)
            if hasattr(self, 'route_debug_info') and self.route_debug_info:
                self.route_debug_info["machine_bounds"] = machine_bounds
                self._log_route_coordinate_debug()

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

            # Draw coordinate grid if enabled
            if self.show_coordinate_grid:
                self._draw_coordinate_grid(overlay_frame, frame_shape)

            # Draw route bounds if enabled
            if self.show_route_bounds and self.routes:
                self._draw_route_bounds(overlay_frame, frame_shape)

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

            # Draw debug information
            if self.show_debug_info:
                self._draw_debug_info(overlay_frame, routes_drawn, total_points_drawn)

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

    def _draw_coordinate_grid(self, frame: np.ndarray, frame_shape: Tuple[int, int]):
        """Draw coordinate grid in machine coordinates"""
        if not self.current_camera_position:
            return

        frame_height, frame_width = frame_shape
        camera_x, camera_y = self.current_camera_position

        # Grid spacing in mm (adapt based on scale)
        if self.camera_scale_factor > 10:
            grid_spacing = 10  # 10mm grid for high zoom
        elif self.camera_scale_factor > 5:
            grid_spacing = 20  # 20mm grid for medium zoom
        else:
            grid_spacing = 50  # 50mm grid for low zoom

        # Calculate grid range
        view_range_x = frame_width / (2 * self.camera_scale_factor)
        view_range_y = frame_height / (2 * self.camera_scale_factor)

        # Find grid lines within view
        start_x = int((camera_x - view_range_x) // grid_spacing) * grid_spacing
        end_x = int((camera_x + view_range_x) // grid_spacing + 1) * grid_spacing
        start_y = int((camera_y - view_range_y) // grid_spacing) * grid_spacing
        end_y = int((camera_y + view_range_y) // grid_spacing + 1) * grid_spacing

        # Draw vertical lines
        for x in range(start_x, end_x + 1, grid_spacing):
            pixel_x1, pixel_y1 = self.machine_to_camera_pixel(x, start_y, frame_shape)
            pixel_x2, pixel_y2 = self.machine_to_camera_pixel(x, end_y, frame_shape)

            if 0 <= pixel_x1 < frame_width:
                cv2.line(frame, (pixel_x1, 0), (pixel_x1, frame_height), (64, 64, 64), 1)
                # Add coordinate label
                if x % (grid_spacing * 2) == 0:  # Every other grid line
                    cv2.putText(frame, f"{x}", (pixel_x1 + 2, 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (128, 128, 128), 1)

        # Draw horizontal lines
        for y in range(start_y, end_y + 1, grid_spacing):
            pixel_x1, pixel_y1 = self.machine_to_camera_pixel(start_x, y, frame_shape)
            pixel_x2, pixel_y2 = self.machine_to_camera_pixel(end_x, y, frame_shape)

            if 0 <= pixel_y1 < frame_height:
                cv2.line(frame, (0, pixel_y1), (frame_width, pixel_y1), (64, 64, 64), 1)
                # Add coordinate label
                if y % (grid_spacing * 2) == 0:  # Every other grid line
                    cv2.putText(frame, f"{y}", (5, pixel_y1 - 2),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (128, 128, 128), 1)

    def _draw_route_bounds(self, frame: np.ndarray, frame_shape: Tuple[int, int]):
        """Draw bounding box around all routes"""
        bounds = self.get_route_bounds()
        if not bounds:
            return

        min_x, min_y, max_x, max_y = bounds

        # Convert corners to pixel coordinates
        corners = [
            (min_x, min_y),  # Bottom-left
            (max_x, min_y),  # Bottom-right
            (max_x, max_y),  # Top-right
            (min_x, max_y),  # Top-left
        ]

        pixel_corners = []
        for machine_x, machine_y in corners:
            pixel_x, pixel_y = self.machine_to_camera_pixel(machine_x, machine_y, frame_shape)
            pixel_corners.append((pixel_x, pixel_y))

        # Draw bounding rectangle
        if len(pixel_corners) == 4:
            # Draw the rectangle
            pts = np.array(pixel_corners, np.int32)
            pts = pts.reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], True, (128, 255, 128), 2)

            # Add bounds text
            center_x = int(np.mean([p[0] for p in pixel_corners]))
            center_y = int(np.mean([p[1] for p in pixel_corners]))

            if (0 <= center_x < frame_shape[1] and 0 <= center_y < frame_shape[0]):
                bounds_text = f"Bounds: {max_x - min_x:.1f}x{max_y - min_y:.1f}mm"
                cv2.putText(frame, bounds_text, (center_x - 50, center_y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 255, 128), 1)

    def _draw_debug_info(self, frame: np.ndarray, routes_drawn: int, total_points_drawn: int):
        """Draw comprehensive debug information on the frame"""
        if not self.route_debug_info:
            return

        info = self.route_debug_info
        y_offset = 20

        # Prepare debug lines
        debug_lines = []

        # Basic route information
        debug_lines.append(f"Routes: {routes_drawn}/{info['route_count']} visible")
        debug_lines.append(f"Points: {total_points_drawn}/{info['total_points']}")
        debug_lines.append(f"Length: {info['total_length_mm']:.1f}mm")

        # Transform mode and coordinates
        debug_lines.append(f"Mode: {info['transform_mode'].title()}")

        machine = info['machine_bounds']
        debug_lines.append(f"Machine Bounds:")
        debug_lines.append(f"  X: {machine['min_x']:.1f} to {machine['max_x']:.1f}mm")
        debug_lines.append(f"  Y: {machine['min_y']:.1f} to {machine['max_y']:.1f}mm")
        debug_lines.append(f"  Size: {machine['width']:.1f}x{machine['height']:.1f}mm")
        debug_lines.append(f"  Center: ({machine['center_x']:.1f}, {machine['center_y']:.1f})mm")

        # Camera information
        if self.current_camera_position:
            cam_x, cam_y = self.current_camera_position
            debug_lines.append(f"Camera: ({cam_x:.1f}, {cam_y:.1f})mm")
        else:
            debug_lines.append("Camera: Not set")

        debug_lines.append(f"Scale: {self.camera_scale_factor:.1f} px/mm")

        # Registration information
        if info.get('registration_info') and info['registration_info']['available']:
            reg = info['registration_info']
            if reg.get('is_registered'):
                debug_lines.append(f"Registration: OK")
                if reg.get('registration_error') is not None:
                    debug_lines.append(f"  Error: {reg['registration_error']:.3f}mm")
                debug_lines.append(f"  Points: {reg.get('point_count', 0)}")
            else:
                debug_lines.append("Registration: Not calibrated")

        # Individual route information (first few routes)
        if info.get('individual_routes'):
            debug_lines.append("First Routes:")
            for route_info in info['individual_routes'][:3]:  # Show first 3 routes
                debug_lines.append(f"  {route_info['index']}: {route_info['point_count']}pts, {route_info['length_mm']:.1f}mm")
                if route_info['start_point']:
                    start = route_info['start_point']
                    debug_lines.append(f"    Start: ({start[0]:.1f}, {start[1]:.1f})")

        # Draw debug background
        max_width = max([len(line) for line in debug_lines]) * 6
        debug_height = len(debug_lines) * self.debug_line_spacing + 10

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (max_width + 10, debug_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Draw debug text
        for i, line in enumerate(debug_lines):
            y_pos = y_offset + (i * self.debug_line_spacing)
            cv2.putText(frame, line, (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, self.debug_text_size, (0, 255, 255), 1)

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

        # Add coordinate text if camera position is known
        if self.current_camera_position:
            cam_x, cam_y = self.current_camera_position
            coord_text = f"({cam_x:.1f}, {cam_y:.1f})"
            cv2.putText(frame, coord_text, (center_x + 15, center_y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

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

    def get_debug_info(self) -> dict:
        """Get comprehensive debug information"""
        return self.route_debug_info.copy() if self.route_debug_info else {}

    def print_route_summary(self):
        """Print a summary of route coordinates to console/log"""
        if not self.route_debug_info:
            self.log("No route debug information available", "warning")
            return

        info = self.route_debug_info

        print("\n" + "="*80)
        print("ROUTE COORDINATE SUMMARY")
        print("="*80)

        print(f"File: {os.path.basename(info['file_path'])}")
        print(f"Transform Mode: {info['transform_mode']}")
        print(f"Total Routes: {info['route_count']}")
        print(f"Total Points: {info['total_points']}")
        print(f"Total Length: {info['total_length_mm']:.2f} mm")

        print(f"\nMachine Coordinate Bounds:")
        machine = info['machine_bounds']
        print(f"  X: {machine['min_x']:.2f} to {machine['max_x']:.2f} mm (width: {machine['width']:.2f} mm)")
        print(f"  Y: {machine['min_y']:.2f} to {machine['max_y']:.2f} mm (height: {machine['height']:.2f} mm)")
        print(f"  Center: ({machine['center_x']:.2f}, {machine['center_y']:.2f}) mm")

        if self.current_camera_position:
            cam_x, cam_y = self.current_camera_position
            print(f"\nCamera Position: ({cam_x:.2f}, {cam_y:.2f}) mm")

            # Calculate distances from camera to route bounds
            dist_to_center = np.sqrt((machine['center_x'] - cam_x)**2 + (machine['center_y'] - cam_y)**2)
            print(f"Distance to Route Center: {dist_to_center:.2f} mm")

        if info.get('individual_routes'):
            print(f"\nIndividual Routes:")
            for route_info in info['individual_routes']:
                print(f"  Route {route_info['index']}: {route_info['point_count']} points, {route_info['length_mm']:.1f} mm")
                if route_info['start_point'] and route_info['end_point']:
                    start = route_info['start_point']
                    end = route_info['end_point']
                    print(f"    Start: ({start[0]:.2f}, {start[1]:.2f}) -> End: ({end[0]:.2f}, {end[1]:.2f})")

        print("="*80)

    def export_routes_info(self) -> dict:
        """Export comprehensive AR route information"""
        base_info = {
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
                'manual_offset': self.manual_offset,
                'show_debug_info': self.show_debug_info,
                'show_route_bounds': self.show_route_bounds,
                'show_coordinate_grid': self.show_coordinate_grid
            },
            'registration_status': {
                'has_registration_manager': self.registration_manager is not None,
                'is_registered': (self.registration_manager and
                                self.registration_manager.is_registered() if self.registration_manager else False)
            }
        }

        # Add debug information if available
        if self.route_debug_info:
            base_info['debug_info'] = self.route_debug_info.copy()

        return base_info