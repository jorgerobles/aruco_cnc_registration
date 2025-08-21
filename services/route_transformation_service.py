"""
Route Transformation Service
Intermediate service that bridges RouteTransformer and GUI components
Handles format conversion and event dispatching following SOLID principles
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any

from services.event_broker import event_aware
from services.registration_manager import RegistrationManager
from services.route_transformer import RouteTransformer
from services.routes_manager import RouteManager


class RouteTransformationEvents:
    """Events dispatched by the route transformation service"""
    BOUNDS_CALCULATED = "route_transform.bounds_calculated"
    TRANSFORMATION_APPLIED = "route_transform.transformation_applied"
    TRANSFORMATION_CLEARED = "route_transform.transformation_cleared"
    ERROR = "route_transform.error"


@event_aware()
class RouteTransformationService:
    """
    Intermediate service for route transformations
    Bridges RouteTransformer and GUI components with proper event handling
    """

    def __init__(self, route_manager: RouteManager, registration_manager: RegistrationManager, logger=None):
        self.registration_manager = registration_manager
        self.route_manager = route_manager
        self.logger = logger
        self.log("Route Transformation Service initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[RouteTransformService] {message}", level)

    def _routes_to_numpy_paths(self, routes: List[List[Tuple[float, float]]]) -> List[np.ndarray]:
        """Convert route manager format to RouteTransformer format"""
        try:
            numpy_paths = []
            for route in routes:
                if len(route) > 0:
                    # Convert list of tuples to numpy array Nx2
                    path_array = np.array(route, dtype=np.float64)
                    numpy_paths.append(path_array)
            return numpy_paths
        except Exception as e:
            error_msg = f"Failed to convert routes to numpy format: {e}"
            self.emit(RouteTransformationEvents.ERROR, error_msg)
            raise ValueError(error_msg)

    def _numpy_paths_to_routes(self, numpy_paths: List[np.ndarray]) -> List[List[Tuple[float, float]]]:
        """Convert RouteTransformer format back to route manager format"""
        try:
            routes = []
            for path_array in numpy_paths:
                # Convert numpy array back to list of tuples
                route = [(float(point[0]), float(point[1])) for point in path_array]
                routes.append(route)
            return routes
        except Exception as e:
            error_msg = f"Failed to convert numpy paths to routes format: {e}"
            self.emit(RouteTransformationEvents.ERROR, error_msg)
            raise ValueError(error_msg)

    def calculate_route_bounds(self, routes: List[List[Tuple[float, float]]]) -> Optional[Dict[str, float]]:
        """
        Calculate bounding box of routes

        Args:
            routes: List of routes in (x, y) tuple format

        Returns:
            Dictionary with bounds information or None on error
        """
        try:
            if not routes or len(routes) == 0:
                self.emit(RouteTransformationEvents.ERROR, "No routes provided for bounds calculation")
                return None

            # Collect all points
            all_x = []
            all_y = []

            for route in routes:
                for x, y in route:
                    all_x.append(x)
                    all_y.append(y)

            if not all_x or not all_y:
                self.emit(RouteTransformationEvents.ERROR, "No valid points found in routes")
                return None

            # Calculate bounds
            x_min, x_max = min(all_x), max(all_x)
            y_min, y_max = min(all_y), max(all_y)
            width = x_max - x_min
            height = y_max - y_min
            center_x = x_min + width / 2
            center_y = y_min + height / 2

            bounds = {
                'x_min': x_min,
                'y_min': y_min,
                'x_max': x_max,
                'y_max': y_max,
                'width': width,
                'height': height,
                'center_x': center_x,
                'center_y': center_y,
                'point_count': len(all_x)
            }

            # Emit bounds calculated event
            self.emit(RouteTransformationEvents.BOUNDS_CALCULATED, {
                'bounds': bounds,
                'route_count': len(routes)
            })

            self.log(f"Calculated bounds: {width:.1f}x{height:.1f}mm at ({center_x:.1f}, {center_y:.1f})")
            return bounds

        except Exception as e:
            error_msg = f"Error calculating route bounds: {e}"
            self.log(error_msg, "error")
            self.emit(RouteTransformationEvents.ERROR, error_msg)
            return None





    def apply_registration_transformation(self, routes: List[List[Tuple[float, float]]],
                                          registration_manager) -> Optional[List[List[Tuple[float, float]]]]:
        """
        Apply registration-based transformation to routes

        Args:
            routes: Input routes in (x, y) tuple format
            registration_manager: Registration manager with calibration data

        Returns:
            Transformed routes or None on error
        """
        try:
            if not routes or len(routes) == 0:
                self.emit(RouteTransformationEvents.ERROR, "No routes provided for transformation")
                return None

            # Get destination points from registration
            destination_points = self.get_destination_triangle_from_calibration()
            if not destination_points:
                return None

            # Convert routes to numpy format
            numpy_paths = self._routes_to_numpy_paths(routes)

            # Create RouteTransformer instance
            transformer = RouteTransformer(numpy_paths)

            # Apply transformation
            transformed_numpy_paths = transformer.transform_to(destination_points)

            # Convert back to routes format
            transformed_routes = self._numpy_paths_to_routes(transformed_numpy_paths)

            # Calculate bounds of transformed routes
            transformed_bounds = self.calculate_route_bounds(transformed_routes)

            # Get registration error
            reg_error = registration_manager.get_registration_error() or 0.0

            # Emit transformation applied event
            self.emit(RouteTransformationEvents.TRANSFORMATION_APPLIED, {
                'source': 'registration_transformation',
                'route_count': len(transformed_routes),
                'original_route_count': len(routes),
                'registration_error': reg_error,
                'destination_points': destination_points,
                'transformed_bounds': transformed_bounds
            })

            self.log(f"Applied registration transformation to {len(routes)} routes")
            return transformed_routes

        except Exception as e:
            error_msg = f"Failed to apply registration transformation: {e}"
            self.log(error_msg, "error")
            self.emit(RouteTransformationEvents.ERROR, error_msg)
            return None

    def apply_manual_transformation(self, routes: List[List[Tuple[float, float]]],
                                    destination_points: List[Tuple[float, float]]) -> Optional[
        List[List[Tuple[float, float]]]]:
        """
        Apply manual transformation with specific destination points

        Args:
            routes: Input routes in (x, y) tuple format
            destination_points: List of 3 destination points [(x1, y1), (x2, y2), (x3, y3)]

        Returns:
            Transformed routes or None on error
        """
        try:
            if not routes or len(routes) == 0:
                self.emit(RouteTransformationEvents.ERROR, "No routes provided for transformation")
                return None

            if len(destination_points) != 3:
                self.emit(RouteTransformationEvents.ERROR, "Exactly 3 destination points required")
                return None

            # Convert routes to numpy format
            numpy_paths = self._routes_to_numpy_paths(routes)

            # Create RouteTransformer instance
            transformer = RouteTransformer(numpy_paths)

            # Apply transformation
            transformed_numpy_paths = transformer.transform_to(destination_points)

            # Convert back to routes format
            transformed_routes = self._numpy_paths_to_routes(transformed_numpy_paths)

            # Calculate bounds of transformed routes
            transformed_bounds = self.calculate_route_bounds(transformed_routes)

            # Emit transformation applied event
            self.emit(RouteTransformationEvents.TRANSFORMATION_APPLIED, {
                'source': 'manual_transformation',
                'route_count': len(transformed_routes),
                'original_route_count': len(routes),
                'destination_points': destination_points,
                'transformed_bounds': transformed_bounds
            })

            self.log(f"Applied manual transformation to {len(routes)} routes")
            return transformed_routes

        except Exception as e:
            error_msg = f"Failed to apply manual transformation: {e}"
            self.log(error_msg, "error")
            self.emit(RouteTransformationEvents.ERROR, error_msg)
            return None

    def get_route_statistics(self, routes: List[List[Tuple[float, float]]]) -> Dict[str, Any]:
        """
        Get comprehensive statistics about routes

        Args:
            routes: Input routes in (x, y) tuple format

        Returns:
            Dictionary with route statistics
        """
        try:
            if not routes:
                return {
                    'route_count': 0,
                    'total_points': 0,
                    'total_length': 0.0,
                    'average_route_length': 0.0,
                    'bounds': None
                }

            total_points = 0
            total_length = 0.0
            route_lengths = []

            # Calculate statistics for each route
            for route in routes:
                route_length = 0.0
                total_points += len(route)

                # Calculate route length
                for i in range(len(route) - 1):
                    x1, y1 = route[i]
                    x2, y2 = route[i + 1]
                    segment_length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    route_length += segment_length

                route_lengths.append(route_length)
                total_length += route_length

            # Calculate bounds
            bounds = self.calculate_route_bounds(routes)

            return {
                'route_count': len(routes),
                'total_points': total_points,
                'total_length': total_length,
                'average_route_length': total_length / len(routes) if routes else 0.0,
                'route_lengths': route_lengths,
                'bounds': bounds
            }

        except Exception as e:
            error_msg = f"Error calculating route statistics: {e}"
            self.log(error_msg, "error")
            self.emit(RouteTransformationEvents.ERROR, error_msg)
            return {'error': error_msg}
        
    def get_source_triangle_from_routes(self):
        """
        Extract source triangle from route bounding box.
        Uses the actual bounding box corners, not searching for nearest vertices.
        FIXED: Now uses top-LEFT to match route transformer and destination triangle
        """
        try:
            routes = self.route_manager.get_routes()
           
            all_points = []
            for route in routes:
                all_points.extend(route)

            if not all_points:
                return None

            all_points = np.array(all_points)

            # Calculate the actual bounding box
            min_x = np.min(all_points[:, 0])
            max_x = np.max(all_points[:, 0])
            min_y = np.min(all_points[:, 1])
            max_y = np.max(all_points[:, 1])

            # Create triangle using actual bounding box corners
            # FIXED: Use top-LEFT instead of top-RIGHT to match system convention
            bottom_left = (min_x, min_y)  # Bottom-left corner
            bottom_right = (max_x, min_y)  # Bottom-right corner
            top_left = (min_x, max_y)  # Top-LEFT corner (FIXED: was max_x, now min_x)

            # Return in consistent order: [bottom-left, bottom-right, top-left]
            return [bottom_left, bottom_right, top_left]

        except Exception as e:
            self.log(f"Error getting source triangle: {e}", "error")
            return None

    def get_destination_triangle_from_calibration(self):
        """
        Extract destination triangle from calibration points.
        FIXED: Orders them to match the corrected source triangle pattern (bottom-left, bottom-right, top-left).
        """
        calibration_points = [(pos[0], pos[1]) for pos in self.registration_manager.get_machine_positions()]
        
        try:
            if not calibration_points or len(calibration_points) < 3:
                return None

            # Get first 3 calibration points
            points = np.array(calibration_points[:3])

            # Sort points to identify their positions
            # First separate by Y coordinate (bottom vs top)
            y_sorted_indices = np.argsort(points[:, 1])

            # If we have a clear top point (significantly higher Y)
            y_values = points[:, 1]
            y_range = np.max(y_values) - np.min(y_values)

            if y_range > 10:  # Significant Y difference
                # Identify bottom points (lower Y values)
                bottom_mask = points[:, 1] < (np.min(y_values) + y_range * 0.5)
                bottom_indices = np.where(bottom_mask)[0]
                top_indices = np.where(~bottom_mask)[0]

                if len(bottom_indices) >= 2 and len(top_indices) >= 1:
                    # Get bottom points and sort by X
                    bottom_points = points[bottom_indices]
                    bottom_x_sorted = np.argsort(bottom_points[:, 0])

                    bottom_left = bottom_points[bottom_x_sorted[0]]
                    bottom_right = bottom_points[bottom_x_sorted[1]]

                    # Get top point - should be the leftmost top point for consistency
                    top_point = points[top_indices[0]]

                    # FIXED: Return in order matching corrected source triangle
                    # [bottom-left, bottom-right, top-left]
                    return [tuple(bottom_left), tuple(bottom_right), tuple(top_point)]

            # Fallback: use simple sorting
            # Sort all points by Y, then by X
            sorted_indices = np.lexsort((points[:, 0], points[:, 1]))
            sorted_points = points[sorted_indices]

            # Assume first two are bottom points
            if sorted_points[0, 0] < sorted_points[1, 0]:
                bottom_left = sorted_points[0]
                bottom_right = sorted_points[1]
            else:
                bottom_left = sorted_points[1]
                bottom_right = sorted_points[0]

            top_point = sorted_points[2]

            # FIXED: Return consistent order [bottom-left, bottom-right, top-left]
            return [tuple(bottom_left), tuple(bottom_right), tuple(top_point)]

        except Exception as e:
            self.log(f"Error getting destination triangle: {e}", "error")
            return None
        
        
        
        