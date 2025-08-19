"""
Route Transformation Service
Intermediate service that bridges RouteTransformer and GUI components
Handles format conversion and event dispatching following SOLID principles
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any

from services.event_broker import event_aware
from services.route_transformer import RouteTransformer


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

    def __init__(self, logger=None):
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



    def _get_registration_destination_points(self, registration_manager) -> Optional[List[Tuple[float, float]]]:
        """
        Extract 3 destination points from registration manager.
        Reorder them to match the source triangle vertices order:
        [0] -> bottom-left vertex (R7 position)
        [1] -> bottom-right vertex (R8 position)
        [2] -> top-left vertex (R6 position)
        """
        try:
            if not registration_manager.is_registered():
                raise ValueError("Registration not computed")

            machine_positions = registration_manager.get_machine_positions()

            if len(machine_positions) < 3:
                raise ValueError("Need at least 3 calibration points")

            # Get first 3 machine positions as numpy arrays for easier manipulation
            cal_points = []
            for i in range(3):
                pos = machine_positions[i]
                cal_points.append(np.array([float(pos[0]), float(pos[1])]))

            cal_points = np.array(cal_points)

            # Identify which calibration point corresponds to which position
            # by analyzing their relative positions

            # Sort by Y coordinate to separate bottom from top
            y_sorted_indices = np.argsort(cal_points[:, 1])

            # The two points with lowest Y are the bottom points
            bottom_indices = y_sorted_indices[:2]
            top_index = y_sorted_indices[2]

            # Get the bottom points and sort by X to identify left vs right
            bottom_points = cal_points[bottom_indices]
            bottom_x_sorted = np.argsort(bottom_points[:, 0])

            # Identify each point's role
            bottom_left_idx = bottom_indices[bottom_x_sorted[0]]
            bottom_right_idx = bottom_indices[bottom_x_sorted[1]]
            top_left_idx = top_index  # The top point (assuming it's on the left as per R6)

            # Check if the top point is actually on the left
            # If not, we might need to adjust our assumption
            top_point = cal_points[top_left_idx]
            bottom_left_point = cal_points[bottom_left_idx]

            # If top point's X is significantly to the right of bottom-left,
            # we might have a different triangle orientation
            if top_point[0] > bottom_left_point[0] + 10:  # 10mm tolerance
                self.log("Warning: Top calibration point appears to be on the right, not left")

            # Return points in the order matching the source triangle:
            # [0] bottom-left, [1] bottom-right, [2] top-left
            destination_points = [
                (float(cal_points[bottom_left_idx][0]), float(cal_points[bottom_left_idx][1])),
                (float(cal_points[bottom_right_idx][0]), float(cal_points[bottom_right_idx][1])),
                (float(cal_points[top_left_idx][0]), float(cal_points[top_left_idx][1]))
            ]

            self.log(f"Reordered destination points to match source triangle:")
            self.log(f"  Bottom-left (R7): {destination_points[0]}")
            self.log(f"  Bottom-right (R8): {destination_points[1]}")
            self.log(f"  Top-left (R6): {destination_points[2]}")

            return destination_points

        except Exception as e:
            error_msg = f"Failed to get registration destination points: {e}"
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
            destination_points = self._get_registration_destination_points(registration_manager)
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