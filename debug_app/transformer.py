"""
Transformer - Handle route transformation using triangle matching
Clean implementation referencing route_transformer.py algorithms with both rigid and affine methods
"""

import numpy as np
from typing import List, Tuple, Optional


class Transformer:
    """Handle route transformation using triangle matching with rigid and affine methods"""

    def get_source_triangle(self, routes: List[List[Tuple[float, float]]]) -> Optional[List[Tuple[float, float]]]:
        """
        Get source triangle from route bounding box
        Uses same approach as RouteTransformer: bottom-left, bottom-right, top-left corners

        Args:
            routes: List of routes

        Returns:
            List of 3 (x, y) tuples for triangle vertices
        """
        try:
            if not routes:
                return None

            # Get all points from all routes
            all_points = []
            for route in routes:
                all_points.extend(route)

            if not all_points:
                return None

            # Calculate bounding box
            all_x = [p[0] for p in all_points]
            all_y = [p[1] for p in all_points]

            min_x = min(all_x)
            max_x = max(all_x)
            min_y = min(all_y)
            max_y = max(all_y)

            # Create triangle using EXACT bounding box corners (same as RouteTransformer)
            # Bottom-left corner
            q1 = (min_x, min_y)

            # Bottom-right corner
            q2 = (max_x, min_y)

            # Top-LEFT corner (not top-right!)
            q3 = (min_x, max_y)

            return [q1, q2, q3]

        except Exception as e:
            raise Exception(f"Failed to compute source triangle: {e}")

    def transform_routes(self, routes: List[List[Tuple[float, float]]],
                        destination_triangle: List[Tuple[float, float]],
                        method: str = "rigid") -> Optional[List[List[Tuple[float, float]]]]:
        """
        Transform routes using triangle transformation

        Args:
            routes: List of routes to transform
            destination_triangle: List of 3 destination triangle points
            method: "rigid" for rigid transformation or "affine" for affine transformation

        Returns:
            List of transformed routes
        """
        try:
            if not routes or not destination_triangle:
                return None

            if len(destination_triangle) != 3:
                raise Exception("Destination triangle must have exactly 3 points")

            # Get source triangle
            source_triangle = self.get_source_triangle(routes)
            if not source_triangle:
                raise Exception("Failed to compute source triangle")

            # Choose transformation method
            if method == "affine":
                transform_matrix = self._compute_affine_transform(source_triangle, destination_triangle)
                return self._apply_affine_transform(routes, transform_matrix)
            else:  # rigid (default)
                R, t = self._compute_rigid_transform(source_triangle, destination_triangle)
                return self._apply_rigid_transform(routes, R, t)

        except Exception as e:
            raise Exception(f"Failed to transform routes: {e}")

    def _compute_rigid_transform(self, source_points: List[Tuple[float, float]],
                                destination_points: List[Tuple[float, float]]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute rigid transformation (rotation + translation) between two sets of points
        References the _rigid_transform_2d method from RouteTransformer

        Args:
            source_points: List of 3 source points
            destination_points: List of 3 destination points

        Returns:
            Tuple of (rotation_matrix, translation_vector)
        """
        try:
            # Convert to numpy arrays
            A = np.array(source_points, dtype=np.float64)
            B = np.array(destination_points, dtype=np.float64)

            if A.shape != B.shape or A.shape[0] != 3:
                raise Exception("Source and destination must have exactly 3 points each")

            # Compute centroids
            centroid_A = np.mean(A, axis=0)
            centroid_B = np.mean(B, axis=0)

            # Center the points
            AA = A - centroid_A
            BB = B - centroid_B

            # Compute covariance matrix
            H = AA.T @ BB

            # Singular Value Decomposition
            U, _, Vt = np.linalg.svd(H)

            # Compute rotation matrix
            R = Vt.T @ U.T

            # Ensure proper rotation (det(R) = 1)
            if np.linalg.det(R) < 0:
                Vt[-1, :] *= -1
                R = Vt.T @ U.T

            # Compute translation
            t = centroid_B - R @ centroid_A

            return R, t

        except Exception as e:
            raise Exception(f"Failed to compute rigid transform: {e}")

    def _apply_rigid_transform(self, routes: List[List[Tuple[float, float]]],
                              R: np.ndarray, t: np.ndarray) -> List[List[Tuple[float, float]]]:
        """Apply rigid transformation (rotation + translation) to routes"""
        transformed_routes = []
        for route in routes:
            if not route:
                continue

            transformed_route = []
            for x, y in route:
                # Apply transformation: new_point = R * old_point + t
                old_point = np.array([x, y])
                new_point = R @ old_point + t
                transformed_route.append((float(new_point[0]), float(new_point[1])))

            transformed_routes.append(transformed_route)

        return transformed_routes

    def _compute_affine_transform(self, source_points: List[Tuple[float, float]],
                                 destination_points: List[Tuple[float, float]]) -> np.ndarray:
        """
        Compute affine transformation matrix from source to destination triangle
        Affine transformation allows scaling, rotation, translation, and shearing

        Args:
            source_points: List of 3 source points
            destination_points: List of 3 destination points

        Returns:
            3x3 affine transformation matrix
        """
        try:
            if len(source_points) != 3 or len(destination_points) != 3:
                raise Exception("Need exactly 3 points for affine transformation")

            # Convert to numpy arrays
            src = np.array(source_points, dtype=np.float64)
            dst = np.array(destination_points, dtype=np.float64)

            # Create homogeneous coordinate matrices
            # Source points in homogeneous coordinates [x, y, 1]
            src_homo = np.ones((3, 3))
            src_homo[:2, :] = src.T  # Transpose to get columns

            # Destination points
            dst_homo = np.ones((3, 3))
            dst_homo[:2, :] = dst.T

            # Solve for transformation matrix: dst_homo = T @ src_homo
            # Therefore: T = dst_homo @ inv(src_homo)
            transform_matrix = dst_homo @ np.linalg.inv(src_homo)

            return transform_matrix

        except Exception as e:
            raise Exception(f"Failed to compute affine transform: {e}")

    def _apply_affine_transform(self, routes: List[List[Tuple[float, float]]],
                               transform_matrix: np.ndarray) -> List[List[Tuple[float, float]]]:
        """
        Apply affine transformation matrix to routes

        Args:
            routes: List of routes to transform
            transform_matrix: 3x3 affine transformation matrix

        Returns:
            List of transformed routes
        """
        try:
            transformed_routes = []

            for route in routes:
                if not route:
                    continue

                transformed_route = []
                for x, y in route:
                    # Convert to homogeneous coordinates [x, y, 1]
                    point_homo = np.array([x, y, 1.0])

                    # Apply transformation
                    transformed_homo = transform_matrix @ point_homo

                    # Convert back to 2D coordinates
                    if transformed_homo[2] != 0:
                        new_x = transformed_homo[0] / transformed_homo[2]
                        new_y = transformed_homo[1] / transformed_homo[2]
                    else:
                        new_x, new_y = transformed_homo[0], transformed_homo[1]

                    transformed_route.append((float(new_x), float(new_y)))

                transformed_routes.append(transformed_route)

            return transformed_routes

        except Exception as e:
            raise Exception(f"Failed to apply affine transform: {e}")

    def calculate_transform_error(self, source_points: List[Tuple[float, float]],
                                 destination_points: List[Tuple[float, float]]) -> float:
        """
        Calculate RMS error of rigid transformation

        Args:
            source_points: Source triangle points
            destination_points: Destination triangle points

        Returns:
            RMS error in same units as input coordinates
        """
        try:
            if len(source_points) != len(destination_points):
                return float('inf')

            R, t = self._compute_rigid_transform(source_points, destination_points)

            errors = []
            for i, (x, y) in enumerate(source_points):
                # Transform source point
                source_point = np.array([x, y])
                transformed_point = R @ source_point + t

                # Compare with destination point
                dest_point = np.array(destination_points[i])
                error = np.linalg.norm(transformed_point - dest_point)
                errors.append(error)

            # Calculate RMS error
            rms_error = np.sqrt(np.mean(np.square(errors)))
            return float(rms_error)

        except Exception:
            return float('inf')

    def calculate_affine_transform_error(self, source_points: List[Tuple[float, float]],
                                        destination_points: List[Tuple[float, float]]) -> float:
        """
        Calculate RMS error of affine transformation

        Args:
            source_points: Source triangle points
            destination_points: Destination triangle points

        Returns:
            RMS error in same units as input coordinates
        """
        try:
            if len(source_points) != len(destination_points):
                return float('inf')

            transform_matrix = self._compute_affine_transform(source_points, destination_points)

            errors = []
            for i, (x, y) in enumerate(source_points):
                # Transform source point
                point_homo = np.array([x, y, 1.0])
                transformed_homo = transform_matrix @ point_homo

                # Convert back to 2D
                if transformed_homo[2] != 0:
                    transformed_x = transformed_homo[0] / transformed_homo[2]
                    transformed_y = transformed_homo[1] / transformed_homo[2]
                else:
                    transformed_x, transformed_y = transformed_homo[0], transformed_homo[1]

                # Compare with destination point
                dest_point = np.array(destination_points[i])
                transformed_point = np.array([transformed_x, transformed_y])
                error = np.linalg.norm(transformed_point - dest_point)
                errors.append(error)

            # Calculate RMS error
            rms_error = np.sqrt(np.mean(np.square(errors)))
            return float(rms_error)

        except Exception:
            return float('inf')

    def get_transformation_info(self, source_triangle: List[Tuple[float, float]],
                               destination_triangle: List[Tuple[float, float]],
                               method: str = "rigid") -> dict:
        """
        Get detailed transformation information for debugging

        Args:
            source_triangle: Source triangle points
            destination_triangle: Destination triangle points
            method: "rigid" or "affine" transformation method

        Returns:
            Dictionary with transformation details
        """
        try:
            if not source_triangle or not destination_triangle:
                return {'error': 'Missing triangle data'}

            info = {
                'method': method,
                'source_triangle': source_triangle,
                'destination_triangle': destination_triangle
            }

            if method == "affine":
                transform_matrix = self._compute_affine_transform(source_triangle, destination_triangle)
                error = self.calculate_affine_transform_error(source_triangle, destination_triangle)

                # Extract scaling and rotation from affine matrix
                # For 2D affine: [[a, b, tx], [c, d, ty], [0, 0, 1]]
                a, b = transform_matrix[0, 0], transform_matrix[0, 1]
                c, d = transform_matrix[1, 0], transform_matrix[1, 1]
                tx, ty = transform_matrix[0, 2], transform_matrix[1, 2]

                # Calculate scale factors
                scale_x = np.sqrt(a*a + c*c)
                scale_y = np.sqrt(b*b + d*d)

                # Calculate rotation (from the a,c components)
                rotation_angle = np.degrees(np.arctan2(c, a))

                info.update({
                    'transformation_matrix': transform_matrix.tolist(),
                    'translation': [float(tx), float(ty)],
                    'scale_x': float(scale_x),
                    'scale_y': float(scale_y),
                    'rotation_angle_degrees': float(rotation_angle),
                    'rms_error': float(error),
                    'determinant': float(np.linalg.det(transform_matrix[:2, :2]))  # 2x2 part for scaling factor
                })

            else:  # rigid
                R, t = self._compute_rigid_transform(source_triangle, destination_triangle)
                error = self.calculate_transform_error(source_triangle, destination_triangle)

                # Calculate rotation angle in degrees
                rotation_angle = np.degrees(np.arctan2(R[1, 0], R[0, 0]))

                info.update({
                    'rotation_matrix': R.tolist(),
                    'translation_vector': t.tolist(),
                    'rotation_angle_degrees': float(rotation_angle),
                    'translation_distance': float(np.linalg.norm(t)),
                    'scale_factor_x': 1.0,  # Rigid transform has no scaling
                    'scale_factor_y': 1.0,
                    'rms_error': float(error)
                })

            return info

        except Exception as e:
            return {'error': f'Failed to compute transformation info: {e}'}

    def calculate_transformation_statistics(self, original_routes: List[List[Tuple[float, float]]],
                                          transformed_routes: List[List[Tuple[float, float]]]) -> dict:
        """
        Calculate statistics comparing original and transformed routes
        """
        try:
            if not original_routes or not transformed_routes:
                return {'error': 'No routes provided'}

            # Calculate bounds for both sets
            original_bounds = self._calculate_bounds(original_routes)
            transformed_bounds = self._calculate_bounds(transformed_routes)

            stats = {
                'original_bounds': original_bounds,
                'transformed_bounds': transformed_bounds,
                'route_count': len(original_routes),
                'total_original_points': sum(len(route) for route in original_routes),
                'total_transformed_points': sum(len(route) for route in transformed_routes),
            }

            if original_bounds and transformed_bounds:
                stats['bounds_comparison'] = {
                    'original_center': (
                        original_bounds['x_min'] + original_bounds['width'] / 2,
                        original_bounds['y_min'] + original_bounds['height'] / 2
                    ),
                    'transformed_center': (
                        transformed_bounds['x_min'] + transformed_bounds['width'] / 2,
                        transformed_bounds['y_min'] + transformed_bounds['height'] / 2
                    ),
                    'scale_factor_x': transformed_bounds['width'] / original_bounds['width'] if original_bounds['width'] > 0 else 1.0,
                    'scale_factor_y': transformed_bounds['height'] / original_bounds['height'] if original_bounds['height'] > 0 else 1.0
                }

            return stats

        except Exception as e:
            return {'error': str(e)}

    def _calculate_bounds(self, routes: List[List[Tuple[float, float]]]) -> Optional[dict]:
        """Calculate bounding box of routes"""
        try:
            if not routes:
                return None

            all_x = []
            all_y = []

            for route in routes:
                for x, y in route:
                    all_x.append(x)
                    all_y.append(y)

            if not all_x:
                return None

            return {
                'x_min': min(all_x),
                'x_max': max(all_x),
                'y_min': min(all_y),
                'y_max': max(all_y),
                'width': max(all_x) - min(all_x),
                'height': max(all_y) - min(all_y)
            }

        except Exception:
            return None