"""
Routes Service Manager
Centralized management of route data for the application
"""

from typing import List, Tuple, Optional, Dict, Any

import numpy as np

from services.event_broker import event_aware
from svg.svg_loader import svg_to_routes


class RouteEvents:
    """Route-specific events"""
    ROUTES_LOADED = "routes.loaded"
    ROUTES_CLEARED = "routes.cleared"
    ROUTES_TRANSFORMED = "routes.transformed"
    ROUTE_BOUNDS_CHANGED = "routes.bounds_changed"


@event_aware()
class RouteManager:
    """Centralized routes management service"""

    def __init__(self, logger=None):
        self.logger = logger

        # Route data
        self.routes = []  # List of routes, each route is a list of (x, y) points
        self.route_bounds = None  # [x_min, y_min, x_max, y_max]
        self.routes_loaded = False
        self.current_file = None

        # Transformation data (for camera registration)
        self.transformation_matrix = None
        self.transformed_routes = []
        self.camera_position = None  # Camera position in machine coordinates

        # Statistics
        self.total_length = 0.0
        self.point_count = 0

        self.log("Routes service initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[RoutesService] {message}", level)

    def load_routes_from_svg(self, svg_file: str, angle_threshold: float = 5.0) -> bool:
        """Load routes from SVG file"""
        try:
            self.log(f"Loading routes from SVG: {svg_file}")

            # Use your existing svg_loader
            routes = svg_to_routes(svg_file, angle_threshold)

            if not routes:
                self.log("No routes found in SVG file", "warning")
                return False

            # Store routes data
            self.routes = routes
            self.current_file = svg_file
            self.routes_loaded = True

            # Calculate bounds and statistics
            self._calculate_bounds()
            self._calculate_statistics()

            # Clear any existing transformations
            self.transformation_matrix = None
            self.transformed_routes = []

            self.log(f"Loaded {len(self.routes)} routes with {self.point_count} total points")
            self.log(f"Route bounds: {self.route_bounds}")

            # Emit event
            self.emit(RouteEvents.ROUTES_LOADED, {
                'file': svg_file,
                'route_count': len(self.routes),
                'point_count': self.point_count,
                'bounds': self.route_bounds,
                'total_length': self.total_length
            })

            return True

        except Exception as e:
            self.log(f"Error loading SVG routes: {e}", "error")
            self.clear_routes()
            return False

    def clear_routes(self):
        """Clear all route data"""
        self.routes = []
        self.route_bounds = None
        self.routes_loaded = False
        self.current_file = None
        self.transformation_matrix = None
        self.transformed_routes = []
        self.camera_position = None
        self.total_length = 0.0
        self.point_count = 0

        self.log("Routes cleared")
        self.emit(RouteEvents.ROUTES_CLEARED)

    def get_routes(self) -> List[List[Tuple[float, float]]]:
        """Get current routes data"""
        return self.routes.copy() if self.routes else []

    def get_route_bounds(self) -> Optional[List[float]]:
        """Get route bounds [x_min, y_min, x_max, y_max]"""
        return self.route_bounds.copy() if self.route_bounds else None

    def get_routes_count(self) -> int:
        """Get number of loaded routes"""
        return len(self.routes) if self.routes else 0

    def get_total_route_length(self) -> float:
        """Get total length of all routes"""
        return self.total_length

    def get_point_count(self) -> int:
        """Get total number of points in all routes"""
        return self.point_count

    def is_loaded(self) -> bool:
        """Check if routes are loaded"""
        return self.routes_loaded and len(self.routes) > 0

    def get_route_info(self) -> Dict[str, Any]:
        """Get comprehensive route information"""
        return {
            'loaded': self.routes_loaded,
            'file': self.current_file,
            'route_count': len(self.routes) if self.routes else 0,
            'point_count': self.point_count,
            'bounds': self.route_bounds.copy() if self.route_bounds else None,
            'total_length': self.total_length,
            'has_transformation': self.transformation_matrix is not None,
            'camera_position': self.camera_position.copy() if self.camera_position else None
        }

    def set_camera_position(self, position: List[float]):
        """Set camera position for visualization"""
        self.camera_position = position[:2] if position else None  # Only X, Y
        self.log(f"Camera position set to: {self.camera_position}")

    def get_camera_position(self) -> Optional[List[float]]:
        """Get camera position"""
        return self.camera_position.copy() if self.camera_position else None

    def set_transformation_matrix(self, matrix: np.ndarray):
        """Set transformation matrix for camera registration"""
        try:
            self.transformation_matrix = matrix.copy()
            self._apply_transformation()
            self.log("Transformation matrix applied to routes")

            self.emit(RouteEvents.ROUTES_TRANSFORMED, {
                'route_count': len(self.transformed_routes),
                'transformation_applied': True
            })

        except Exception as e:
            self.log(f"Error applying transformation: {e}", "error")

    def get_transformed_routes(self) -> List[List[Tuple[float, float]]]:
        """Get transformed routes (if transformation is applied)"""
        return self.transformed_routes.copy() if self.transformed_routes else self.get_routes()

    def _calculate_bounds(self):
        """Calculate bounding box of all routes"""
        if not self.routes:
            self.route_bounds = None
            return

        try:
            all_x = []
            all_y = []

            for route in self.routes:
                for x, y in route:
                    all_x.append(x)
                    all_y.append(y)

            if all_x and all_y:
                self.route_bounds = [
                    min(all_x),  # x_min
                    min(all_y),  # y_min
                    max(all_x),  # x_max
                    max(all_y)  # y_max
                ]
            else:
                self.route_bounds = None

        except Exception as e:
            self.log(f"Error calculating bounds: {e}", "error")
            self.route_bounds = None

    def _calculate_statistics(self):
        """Calculate route statistics"""
        if not self.routes:
            self.total_length = 0.0
            self.point_count = 0
            return

        try:
            total_length = 0.0
            point_count = 0

            for route in self.routes:
                point_count += len(route)

                # Calculate route length
                for i in range(len(route) - 1):
                    x1, y1 = route[i]
                    x2, y2 = route[i + 1]
                    segment_length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    total_length += segment_length

            self.total_length = total_length
            self.point_count = point_count

        except Exception as e:
            self.log(f"Error calculating statistics: {e}", "error")
            self.total_length = 0.0
            self.point_count = 0

    def _apply_transformation(self):
        """Apply transformation matrix to routes"""
        if not self.routes or self.transformation_matrix is None:
            self.transformed_routes = []
            return

        try:
            self.transformed_routes = []

            for route in self.routes:
                transformed_route = []

                for x, y in route:
                    # Apply transformation matrix
                    point = np.array([x, y, 1])  # Homogeneous coordinates
                    transformed_point = self.transformation_matrix @ point
                    transformed_route.append((transformed_point[0], transformed_point[1]))

                self.transformed_routes.append(transformed_route)

        except Exception as e:
            self.log(f"Error applying transformation: {e}", "error")
            self.transformed_routes = []

    def export_routes_to_gcode(self, output_file: str, feed_rate: float = 1000.0) -> bool:
        """Export routes to G-code file"""
        try:
            routes_to_export = self.get_transformed_routes() if self.transformation_matrix else self.routes

            if not routes_to_export:
                self.log("No routes to export", "warning")
                return False

            with open(output_file, 'w') as f:
                # G-code header
                f.write("; Generated by GRBL Camera Registration\n")
                f.write(f"; Routes from: {self.current_file}\n")
                f.write(f"; {len(routes_to_export)} routes, {self.point_count} points\n")
                f.write("\n")

                # Initialize
                f.write("G90 ; Absolute positioning\n")
                f.write("G21 ; Units in mm\n")
                f.write(f"F{feed_rate:.0f} ; Set feed rate\n")
                f.write("\n")

                # Process each route
                for route_idx, route in enumerate(routes_to_export):
                    f.write(f"; Route {route_idx + 1}\n")

                    if route:
                        # Move to start position (rapid)
                        x, y = route[0]
                        f.write(f"G0 X{x:.3f} Y{y:.3f} ; Move to start\n")

                        # Draw route (linear moves)
                        for x, y in route[1:]:
                            f.write(f"G1 X{x:.3f} Y{y:.3f}\n")

                        f.write("\n")

                # Footer
                f.write("; End of routes\n")
                f.write("M30 ; Program end\n")

            self.log(f"Routes exported to G-code: {output_file}")
            return True

        except Exception as e:
            self.log(f"Error exporting G-code: {e}", "error")
            return False

    def get_service_status(self) -> Dict[str, Any]:
        """Get service status for debugging"""
        return {
            'routes_loaded': self.routes_loaded,
            'route_count': len(self.routes) if self.routes else 0,
            'point_count': self.point_count,
            'total_length': self.total_length,
            'bounds': self.route_bounds,
            'current_file': self.current_file,
            'has_transformation': self.transformation_matrix is not None,
            'transformed_routes_count': len(self.transformed_routes) if self.transformed_routes else 0,
            'camera_position': self.camera_position
        }