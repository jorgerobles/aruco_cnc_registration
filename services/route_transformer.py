# Fixed route_transformer.py - Use actual outermost vertices instead of bounding box corners

import numpy as np
from typing import List, Tuple


class RouteTransformer:
    def __init__(self, paths):
        """
        paths: lista de np.arrays Nx2, cada uno representa una forma 2D
        """
        self.original_paths = paths
        self.transformed_paths = None

    def _rigid_transform_2d(self, A, B):
        assert A.shape == B.shape
        centroid_A = np.mean(A, axis=0)
        centroid_B = np.mean(B, axis=0)

        AA = A - centroid_A
        BB = B - centroid_B

        H = AA.T @ BB
        U, _, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T

        if np.linalg.det(R) < 0:
            Vt[-1, :] *= -1
            R = Vt.T @ U.T

        t = centroid_B - R @ centroid_A
        return R, t

    def _apply_transform(self, points, R, t):
        return (R @ points.T).T + t

    def _find_actual_outermost_vertices(self):
        """
        Find the actual outermost vertices from the routes.
        These correspond to R7 (bottom-left), R8 (bottom-right), and R6 (top).

        Instead of using bounding box corners, find the actual vertices
        that are furthest in each direction.
        """
        # Collect all points from all paths
        all_points = np.vstack(self.original_paths)

        # Find the actual extreme points (not just bounding box corners)
        # These should correspond to the outermost vertices of R6, R7, R8

        # Find bottom-left vertex (R7): minimize x+y (closest to origin in that quadrant)
        bottom_left_idx = np.argmin(all_points[:, 0] + all_points[:, 1])
        bottom_left = all_points[bottom_left_idx]

        # Find bottom-right vertex (R8): maximize x, minimize y
        # First find points in the bottom 25% by Y
        y_threshold = np.percentile(all_points[:, 1], 25)
        bottom_points = all_points[all_points[:, 1] <= y_threshold]
        # Among bottom points, find the rightmost
        bottom_right_idx = np.argmax(bottom_points[:, 0])
        bottom_right = bottom_points[bottom_right_idx]

        # Find top-left vertex (R6): minimize x, maximize y
        # First find points in the top 25% by Y
        y_threshold = np.percentile(all_points[:, 1], 75)
        top_points = all_points[all_points[:, 1] >= y_threshold]
        # Among top points, find the leftmost
        top_left_idx = np.argmin(top_points[:, 0])
        top_left = top_points[top_left_idx]

        return np.array([bottom_left, bottom_right, top_left])

    def _bounding_triangle_alternative(self):
        """
        Alternative method: Find the three vertices that form the largest triangle.
        This should naturally find R6, R7, R8's outermost vertices.
        """
        all_points = np.vstack(self.original_paths)

        # For a right triangle aligned with axes, we want:
        # - One point at bottom-left
        # - One point at bottom-right
        # - One point at top (could be left or right)

        # Find the convex hull first to reduce search space
        # (only outermost points can form the largest triangle)
        from scipy.spatial import ConvexHull
        try:
            hull = ConvexHull(all_points)
            hull_points = all_points[hull.vertices]
        except:
            # If convex hull fails, use all points
            hull_points = all_points

        # Now find the three points that best match a right triangle pattern
        # where two points share similar Y (bottom edge) and one is higher

        # Sort points by Y coordinate
        sorted_points = hull_points[np.argsort(hull_points[:, 1])]

        # Take bottom third and top third
        n = len(sorted_points)
        bottom_third = sorted_points[:n // 3]
        top_third = sorted_points[2 * n // 3:]

        # From bottom third, find leftmost and rightmost
        bottom_left = bottom_third[np.argmin(bottom_third[:, 0])]
        bottom_right = bottom_third[np.argmax(bottom_third[:, 0])]

        # From top third, find the point that forms the best right angle
        # For a right triangle, we typically want the top point to align with
        # either the left or right bottom point
        top_left = top_third[np.argmin(top_third[:, 0])]

        return np.array([bottom_left, bottom_right, top_left])

    def _bounding_triangle(self):
        """
        Create source triangle from the actual outermost vertices of the routes.
        This ensures we use the real vertices from R6, R7, R8, not just bbox corners.
        """
        # Try the actual vertices method first
        try:
            return self._find_actual_outermost_vertices()
        except:
            # Fallback to alternative method
            try:
                return self._bounding_triangle_alternative()
            except:
                # Last resort: use simple bounding box corners
                all_points = np.vstack(self.original_paths)
                min_xy = np.min(all_points, axis=0)
                max_xy = np.max(all_points, axis=0)

                q1 = min_xy  # Bottom-left
                q2 = [max_xy[0], min_xy[1]]  # Bottom-right
                q3 = [min_xy[0], max_xy[1]]  # Top-left

                return np.array([q1, q2, q3])

    def transform_to(self, destination_points):
        """
        destination_points: lista de 3 tuplas [(x1, y1), (x2, y2), (x3, y3)]
        These are the calibration points in machine coordinates.
        """
        if len(destination_points) != 3:
            raise ValueError("Se requieren exactamente 3 puntos destino")

        # Get source points (actual outermost vertices from R6, R7, R8)
        src_pts = self._bounding_triangle()
        dst_pts = np.array(destination_points)

        # Apply rigid transformation
        R, t = self._rigid_transform_2d(src_pts, dst_pts)
        self.transformed_paths = [self._apply_transform(p, R, t) for p in self.original_paths]
        return self.transformed_paths