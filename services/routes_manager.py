"""
Enhanced RouteManager with SVG Export
Uses svg_exporter module following existing architecture pattern
"""

from typing import List, Tuple, Optional, Dict, Any
import numpy as np

from services.event_broker import event_aware
from svg.svg_loader import svg_to_routes
from svg.svg_exporter import routes_to_svg


class RouteEvents:
    """Route-specific events"""
    ROUTES_LOADED = "routes.loaded"
    ROUTES_CLEARED = "routes.cleared"
    ROUTES_TRANSFORMED = "routes.transformed"
    ROUTE_BOUNDS_CHANGED = "routes.bounds_changed"
    ROUTES_EXPORTED = "routes.exported"  # New export event


@event_aware()
class RouteManager:
    """Enhanced RouteManager with SVG export capabilities"""

    def __init__(self, logger=None, skip_display_none=True):
        self.skip_display_none = skip_display_none
        self.logger = logger

        # Route data
        self.routes = []  # List of routes, each route is a list of (x, y) points
        self.route_bounds = None  # [x_min, y_min, x_max, y_max]
        self.routes_loaded = False
        self.current_file = None

        # Transformation data (for registration)
        self.transformation_matrix = None
        self.transformed_routes = []

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

            routes = svg_to_routes(svg_file, angle_threshold, self.skip_display_none)

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

    def export_routes_to_svg(self,
                           output_file: str,
                           use_transformed: bool = False,
                           **kwargs) -> bool:
        """
        Export routes to SVG file using svg_exporter module

        Args:
            output_file: Output SVG file path
            use_transformed: Use transformed routes if available
            **kwargs: Additional arguments passed to routes_to_svg

        Returns:
            True if export successful
        """
        try:
            # Get routes to export
            routes_to_export = self._get_export_routes(use_transformed)

            if not routes_to_export:
                self.log("No routes to export", "warning")
                return False

            self.log(f"Exporting {len(routes_to_export)} routes to: {output_file}")

            # Add metadata
            metadata = self._create_export_metadata()

            # Use svg_exporter module (same pattern as svg_loader)
            success = routes_to_svg(
                routes=routes_to_export,
                output_file=output_file,
                metadata=metadata,
                **kwargs
            )

            if success:
                self.emit(RouteEvents.ROUTES_EXPORTED, {
                    'output_file': output_file,
                    'route_count': len(routes_to_export),
                    'use_transformed': use_transformed
                })
                self.log(f"Successfully exported SVG: {output_file}")
            else:
                self.log("Export failed", "error")

            return success

        except Exception as e:
            error_msg = f"Failed to export SVG: {e}"
            self.log(error_msg, "error")
            return False

    def _get_export_routes(self, use_transformed: bool) -> List[List[Tuple[float, float]]]:
        """Get routes for export (original or transformed)"""
        if use_transformed and self.transformed_routes:
            return self.transformed_routes
        return self.routes

    def _create_export_metadata(self) -> Dict[str, Any]:
        """Create metadata for export"""
        return {
            'source_file': self.current_file or 'unknown',
            'route_count': len(self.routes),
            'point_count': self.point_count,
            'total_length_mm': f"{self.total_length:.2f}",
            'exported_by': 'RouteManager'
        }


    def clear_routes(self):
        """Clear all route data"""
        self.routes = []
        self.route_bounds = None
        self.routes_loaded = False
        self.current_file = None
        self.transformation_matrix = None
        self.transformed_routes = []
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
        }

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