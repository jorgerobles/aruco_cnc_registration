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
        Apply transformation from registration manager to routes.

        The registration manager computes transformation from camera to machine coordinates.
        For routes (which are typically in SVG/world coordinates), we need to transform them
        to align with the machine coordinate system where the registration points were captured.

        Args:
            routes: Original routes in SVG coordinates
            registration_manager: RegistrationManager with computed transformation

        Returns:
            Transformed routes in machine coordinates or None if registration not available
        """
        try:
            if not registration_manager.is_registered():
                error_msg = "Registration not computed - cannot apply transformation"
                self.emit(RouteTransformerEvents.ERROR, error_msg)
                self.log(error_msg, "error")
                return None

            # Get transformation data from registration manager
            # This transforms FROM camera coordinates TO machine coordinates
            transformation_matrix = registration_manager.transformation_matrix  # R matrix
            translation_vector = registration_manager.translation_vector      # t vector

            if transformation_matrix is None or translation_vector is None:
                error_msg = "Invalid transformation data from registration manager"
                self.emit(RouteTransformerEvents.ERROR, error_msg)
                self.log(error_msg, "error")
                return None

            self.log(f"Applying transformation - Matrix shape: {transformation_matrix.shape}, Translation shape: {translation_vector.shape}")

            # For route transformation, we need to treat SVG coordinates as if they were camera coordinates
            # and transform them to machine coordinates using the computed registration
            transformed_routes = []
            total_points = 0

            for route in routes:
                if not route:
                    transformed_routes.append(route)
                    continue

                transformed_route = []

                for point in route:
                    if len(point) >= 2:
                        # Treat route point as camera coordinate (x, y, 0)
                        # This assumes the routes are in the same coordinate system as the camera view
                        camera_point = np.array([point[0], point[1], 0.0])

                        # Transform to machine coordinates: R @ camera_point + t
                        machine_point = transformation_matrix @ camera_point + translation_vector

                        # Use only X,Y for 2D routes
                        transformed_point = (machine_point[0], machine_point[1])
                        transformed_route.append(transformed_point)
                        total_points += 1
                    else:
                        # Keep original point if not enough coordinates
                        transformed_route.append(point)

                transformed_routes.append(transformed_route)

            # Calculate bounds for both original and transformed routes
            original_bounds = self.calculate_route_bounds(routes)
            transformed_bounds = self.calculate_route_bounds(transformed_routes)

            self.log(f"Transformation applied to {len(routes)} routes, {total_points} points")
            self.log(f"Original bounds: {original_bounds}")
            self.log(f"Transformed bounds: {transformed_bounds}")

            self.emit(RouteTransformerEvents.TRANSFORMATION_APPLIED, {
                'source': 'registration_manager',
                'registration_error': registration_manager.get_registration_error(),
                'original_bounds': original_bounds,
                'transformed_bounds': transformed_bounds,
                'route_count': len(routes),
                'total_points': total_points
            })

            return transformed_routes

        except Exception as e:
            error_msg = f"Failed to apply registration transformation: {e}"
            self.emit(RouteTransformerEvents.ERROR, error_msg)
            self.log(error_msg, "error")
            return None

    def calculate_orthogonal_transformation(self, routes: List[List[Tuple[float, float]]],
                                          registration_manager) -> Optional[List[List[Tuple[float, float]]]]:
        """
        Calculate transformation by aligning registration points to form an orthogonal square
        aligned with machine coordinate axes.

        Args:
            routes: Original routes in SVG coordinates
            registration_manager: RegistrationManager with calibration points

        Returns:
            Transformed routes aligned orthogonally to machine coordinates
        """
        try:
            if not registration_manager.is_registered():
                error_msg = "Registration not computed - cannot calculate orthogonal transformation"
                self.emit(RouteTransformerEvents.ERROR, error_msg)
                return None

            # Get registration points in machine coordinates
            machine_positions = registration_manager.get_machine_positions()
            if len(machine_positions) < 3:
                error_msg = "Need at least 3 registration points for orthogonal transformation"
                self.emit(RouteTransformerEvents.ERROR, error_msg)
                return None

            # Convert to 2D points for easier processing
            machine_points_2d = np.array([[pos[0], pos[1]] for pos in machine_positions])

            self.log(f"Registration points: {machine_points_2d}")

            # Calculate the center of registration points
            center = np.mean(machine_points_2d, axis=0)
            self.log(f"Registration center: {center}")

            # Calculate the principal axes using PCA to find the orientation
            centered_points = machine_points_2d - center
            covariance_matrix = np.cov(centered_points.T)
            eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)

            # Sort by eigenvalue magnitude (largest first)
            idx = np.argsort(eigenvalues)[::-1]
            eigenvalues = eigenvalues[idx]
            eigenvectors = eigenvectors[:, idx]

            # Principal axis (direction of maximum variance)
            principal_axis = eigenvectors[:, 0]

            # Calculate rotation angle to align principal axis with X-axis
            angle_to_x_axis = np.arctan2(principal_axis[1], principal_axis[0])

            self.log(f"Principal axis: {principal_axis}")
            self.log(f"Rotation angle to align with X-axis: {np.degrees(angle_to_x_axis):.2f} degrees")

            # Create rotation matrix to align with machine axes
            cos_theta = np.cos(-angle_to_x_axis)  # Negative to rotate back to orthogonal
            sin_theta = np.sin(-angle_to_x_axis)
            rotation_matrix = np.array([
                [cos_theta, -sin_theta],
                [sin_theta,  cos_theta]
            ])

            # Calculate route bounds to determine scale and translation
            route_bounds = self.calculate_route_bounds(routes)
            if not route_bounds:
                error_msg = "Cannot calculate route bounds for orthogonal transformation"
                self.emit(RouteTransformerEvents.ERROR, error_msg)
                return None

            # Route center
            route_center = np.array([route_bounds['center_x'], route_bounds['center_y']])

            self.log(f"Route center: {route_center}")
            self.log(f"Target center (registration): {center}")

            # Apply transformation to all route points
            transformed_routes = []
            total_points = 0

            for route in routes:
                if not route:
                    transformed_routes.append(route)
                    continue

                transformed_route = []
                for point in route:
                    if len(point) >= 2:
                        # Convert point to numpy array
                        point_2d = np.array([point[0], point[1]])

                        # 1. Translate route point relative to route center
                        centered_point = point_2d - route_center

                        # 2. Apply rotation to align with machine axes
                        rotated_point = rotation_matrix @ centered_point

                        # 3. Translate to registration center
                        final_point = rotated_point + center

                        transformed_route.append((final_point[0], final_point[1]))
                        total_points += 1
                    else:
                        transformed_route.append(point)

                transformed_routes.append(transformed_route)

            # Calculate final bounds
            transformed_bounds = self.calculate_route_bounds(transformed_routes)

            self.emit(RouteTransformerEvents.TRANSFORMATION_APPLIED, {
                'source': 'orthogonal_transformation',
                'registration_error': registration_manager.get_registration_error(),
                'original_bounds': route_bounds,
                'transformed_bounds': transformed_bounds,
                'route_count': len(routes),
                'total_points': total_points,
                'rotation_angle_degrees': np.degrees(angle_to_x_axis),
                'principal_axis': principal_axis.tolist(),
                'registration_center': center.tolist(),
                'rotation_matrix': rotation_matrix.tolist()
            })

            self.log(f"Applied orthogonal transformation: {np.degrees(angle_to_x_axis):.2f}° rotation, {total_points} points")
            return transformed_routes

        except Exception as e:
            error_msg = f"Failed to calculate orthogonal transformation: {e}"
            self.emit(RouteTransformerEvents.ERROR, error_msg)
            self.log(error_msg, "error")
            return None

    def debug_transformation_data(self, registration_manager) -> Dict[str, Any]:
        """
        Get detailed debug information about transformation data

        Args:
            registration_manager: RegistrationManager to debug

        Returns:
            Dictionary with debug information
        """
        debug_info = {
            'is_registered': registration_manager.is_registered(),
            'point_count': registration_manager.get_calibration_points_count()
        }

        if registration_manager.is_registered():
            machine_positions = registration_manager.get_machine_positions()
            camera_positions = registration_manager.get_camera_positions()

            debug_info.update({
                'transformation_matrix': registration_manager.transformation_matrix.tolist() if registration_manager.transformation_matrix is not None else None,
                'translation_vector': registration_manager.translation_vector.tolist() if registration_manager.translation_vector is not None else None,
                'registration_error': registration_manager.get_registration_error(),
                'machine_positions': [pos.tolist() for pos in machine_positions],
                'camera_positions': [pos.tolist() for pos in camera_positions],
                'machine_bounds': self._calculate_point_bounds([pos[:2] for pos in machine_positions]),
                'camera_bounds': self._calculate_point_bounds([pos[:2] for pos in camera_positions])
            })

            # Add orthogonal transformation analysis
            if len(machine_positions) >= 3:
                # Analyze the registration points for orthogonal transformation
                machine_points_2d = np.array([[pos[0], pos[1]] for pos in machine_positions])
                center = np.mean(machine_points_2d, axis=0)

                # Calculate PCA
                centered_points = machine_points_2d - center
                covariance_matrix = np.cov(centered_points.T)
                eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
                idx = np.argsort(eigenvalues)[::-1]
                eigenvalues = eigenvalues[idx]
                eigenvectors = eigenvectors[:, idx]

                principal_axis = eigenvectors[:, 0]
                angle_to_x_axis = np.arctan2(principal_axis[1], principal_axis[0])

                debug_info['orthogonal_analysis'] = {
                    'registration_center': center.tolist(),
                    'principal_axis': principal_axis.tolist(),
                    'rotation_angle_degrees': float(np.degrees(angle_to_x_axis)),
                    'eigenvalues': eigenvalues.tolist(),
                    'variance_explained': float(eigenvalues[0] / np.sum(eigenvalues))
                }

        return debug_info

    def _calculate_point_bounds(self, points: List[List[float]]) -> Dict[str, float]:
        """Helper to calculate bounds of a list of 2D points"""
        if not points:
            return {}

        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]

        return {
            'x_min': min(x_coords),
            'y_min': min(y_coords),
            'x_max': max(x_coords),
            'y_max': max(y_coords),
            'center_x': sum(x_coords) / len(x_coords),
            'center_y': sum(y_coords) / len(y_coords)
        }