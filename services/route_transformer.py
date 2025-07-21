"""
Route Transformer Service
Handles rigid transformations of route data for CNC registration alignment
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from services.event_broker import event_aware


class RouteTransformerEvents:
    """Route transformer specific events"""
    ROUTES_TRANSFORMED = "route_transformer.routes_transformed"
    TRANSFORMATION_APPLIED = "route_transformer.transformation_applied"
    BOUNDS_CALCULATED = "route_transformer.bounds_calculated"
    ERROR = "route_transformer.error"


@event_aware()
class RouteTransformer:
    """Service for applying rigid transformations to route data"""

    def __init__(self, logger=None):
        self.logger = logger
        self.log("RouteTransformer service initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[RouteTransformer] {message}", level)

    def calculate_route_bounds(self, routes: List[List[Tuple[float, float]]]) -> Optional[Dict[str, float]]:
        """
        Calculate outer bounds of all routes

        Args:
            routes: List of routes, each route is a list of (x, y) points

        Returns:
            Dict with keys: x_min, y_min, x_max, y_max, center_x, center_y, width, height
        """
        if not routes or not any(routes):
            return None

        try:
            all_points = []
            for route in routes:
                if route:  # Skip empty routes
                    all_points.extend(route)

            if not all_points:
                return None

            x_coords = [point[0] for point in all_points]
            y_coords = [point[1] for point in all_points]

            bounds = {
                'x_min': min(x_coords),
                'y_min': min(y_coords),
                'x_max': max(x_coords),
                'y_max': max(y_coords)
            }

            bounds.update({
                'center_x': (bounds['x_min'] + bounds['x_max']) / 2,
                'center_y': (bounds['y_min'] + bounds['y_max']) / 2,
                'width': bounds['x_max'] - bounds['x_min'],
                'height': bounds['y_max'] - bounds['y_min']
            })

            self.emit(RouteTransformerEvents.BOUNDS_CALCULATED, {
                'bounds': bounds,
                'point_count': len(all_points),
                'route_count': len([r for r in routes if r])
            })

            return bounds

        except Exception as e:
            error_msg = f"Failed to calculate route bounds: {e}"
            self.emit(RouteTransformerEvents.ERROR, error_msg)
            self.log(error_msg, "error")
            return None

    def apply_rigid_transformation(self, routes: List[List[Tuple[float, float]]],
                                  transformation_matrix: np.ndarray,
                                  translation_vector: np.ndarray) -> List[List[Tuple[float, float]]]:
        """
        Apply rigid transformation (rotation + translation) to routes

        Args:
            routes: Original routes
            transformation_matrix: 3x3 or 2x2 rotation matrix
            translation_vector: Translation vector

        Returns:
            Transformed routes
        """
        try:
            if not routes:
                return routes

            transformed_routes = []
            total_points = 0

            for route in routes:
                if not route:
                    transformed_routes.append(route)
                    continue

                transformed_route = []

                for point in route:
                    # Convert to homogeneous coordinates for 2D transformation
                    if len(point) >= 2:
                        # Create 3D point (x, y, 0) for 2D transformation
                        point_3d = np.array([point[0], point[1], 0.0])

                        # Apply transformation: R @ point + t
                        if transformation_matrix.shape == (3, 3):
                            # 3D transformation matrix
                            transformed_3d = transformation_matrix @ point_3d + translation_vector
                            transformed_point = (transformed_3d[0], transformed_3d[1])
                        else:
                            # 2D transformation matrix - extend to 3D
                            point_2d = np.array([point[0], point[1]])
                            if transformation_matrix.shape == (2, 2):
                                transformed_2d = transformation_matrix @ point_2d + translation_vector[:2]
                                transformed_point = (transformed_2d[0], transformed_2d[1])
                            else:
                                raise ValueError(f"Unsupported transformation matrix shape: {transformation_matrix.shape}")

                        transformed_route.append(transformed_point)
                        total_points += 1
                    else:
                        # Keep original point if not enough coordinates
                        transformed_route.append(point)

                transformed_routes.append(transformed_route)

            self.emit(RouteTransformerEvents.ROUTES_TRANSFORMED, {
                'original_route_count': len(routes),
                'transformed_route_count': len(transformed_routes),
                'total_points_transformed': total_points,
                'transformation_matrix_shape': transformation_matrix.shape,
                'translation_vector_shape': translation_vector.shape
            })

            self.log(f"Applied rigid transformation to {len(routes)} routes with {total_points} total points")
            return transformed_routes

        except Exception as e:
            error_msg = f"Failed to apply rigid transformation: {e}"
            self.emit(RouteTransformerEvents.ERROR, error_msg)
            self.log(error_msg, "error")
            return routes  # Return original routes on error

    def apply_registration_transformation(self, routes: List[List[Tuple[float, float]]],
                                        registration_manager) -> Optional[List[List[Tuple[float, float]]]]:
        """
        Apply transformation from registration manager to routes

        Args:
            routes: Original routes
            registration_manager: RegistrationManager with computed transformation

        Returns:
            Transformed routes or None if registration not available
        """
        try:
            if not registration_manager.is_registered():
                error_msg = "Registration not computed - cannot apply transformation"
                self.emit(RouteTransformerEvents.ERROR, error_msg)
                self.log(error_msg, "error")
                return None

            # Get transformation data from registration manager
            transformation_matrix = registration_manager.transformation_matrix
            translation_vector = registration_manager.translation_vector

            if transformation_matrix is None or translation_vector is None:
                error_msg = "Invalid transformation data from registration manager"
                self.emit(RouteTransformerEvents.ERROR, error_msg)
                self.log(error_msg, "error")
                return None

            # Apply the transformation
            transformed_routes = self.apply_rigid_transformation(
                routes, transformation_matrix, translation_vector
            )

            # Calculate bounds for both original and transformed routes
            original_bounds = self.calculate_route_bounds(routes)
            transformed_bounds = self.calculate_route_bounds(transformed_routes)

            self.emit(RouteTransformerEvents.TRANSFORMATION_APPLIED, {
                'source': 'registration_manager',
                'registration_error': registration_manager.get_registration_error(),
                'original_bounds': original_bounds,
                'transformed_bounds': transformed_bounds,
                'route_count': len(routes)
            })

            self.log(f"Applied registration transformation to {len(routes)} routes")
            return transformed_routes

        except Exception as e:
            error_msg = f"Failed to apply registration transformation: {e}"
            self.emit(RouteTransformerEvents.ERROR, error_msg)
            self.log(error_msg, "error")
            return None

    def transform_bounds_to_machine_coordinates(self, route_bounds: Dict[str, float],
                                              registration_manager) -> Optional[Dict[str, float]]:
        """
        Transform route bounds to machine coordinates using registration

        Args:
            route_bounds: Route bounds dictionary
            registration_manager: RegistrationManager with computed transformation

        Returns:
            Transformed bounds in machine coordinates
        """
        try:
            if not registration_manager.is_registered():
                return None

            # Transform corner points
            corners = [
                (route_bounds['x_min'], route_bounds['y_min']),
                (route_bounds['x_max'], route_bounds['y_min']),
                (route_bounds['x_max'], route_bounds['y_max']),
                (route_bounds['x_min'], route_bounds['y_max'])
            ]

            transformed_corners = []
            for corner in corners:
                # Convert to 3D camera coordinates (assuming z=0)
                camera_point = np.array([corner[0], corner[1], 0.0])
                machine_point = registration_manager.transform_point(camera_point)
                transformed_corners.append((machine_point[0], machine_point[1]))

            # Calculate new bounds
            x_coords = [corner[0] for corner in transformed_corners]
            y_coords = [corner[1] for corner in transformed_corners]

            machine_bounds = {
                'x_min': min(x_coords),
                'y_min': min(y_coords),
                'x_max': max(x_coords),
                'y_max': max(y_coords)
            }

            machine_bounds.update({
                'center_x': (machine_bounds['x_min'] + machine_bounds['x_max']) / 2,
                'center_y': (machine_bounds['y_min'] + machine_bounds['y_max']) / 2,
                'width': machine_bounds['x_max'] - machine_bounds['x_min'],
                'height': machine_bounds['y_max'] - machine_bounds['y_min']
            })

            return machine_bounds

        except Exception as e:
            error_msg = f"Failed to transform bounds to machine coordinates: {e}"
            self.emit(RouteTransformerEvents.ERROR, error_msg)
            self.log(error_msg, "error")
            return None