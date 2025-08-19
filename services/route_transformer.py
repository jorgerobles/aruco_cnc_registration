# Simplified route_transformer.py - ONLY use bounding box corners, no complex methods

import numpy as np


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

    def _bounding_triangle(self):
        """
        SIMPLIFIED: Only use the theoretical bounding box corners.
        No searching for actual vertices, no complex methods.
        """
        # Get all points from all paths
        all_points = np.vstack(self.original_paths)

        # Calculate the bounding box
        min_x = np.min(all_points[:, 0])
        max_x = np.max(all_points[:, 0])
        min_y = np.min(all_points[:, 1])
        max_y = np.max(all_points[:, 1])

        # Create triangle using EXACT bounding box corners
        # Bottom-left corner
        q1 = np.array([min_x, min_y])

        # Bottom-right corner
        q2 = np.array([max_x, min_y])

        # Top-LEFT corner (not top-right!)
        q3 = np.array([min_x, max_y])  # This MUST be min_x, not max_x!

        print(f"DEBUG: Bounding box: X[{min_x:.1f}, {max_x:.1f}] Y[{min_y:.1f}, {max_y:.1f}]")
        print(f"DEBUG: Triangle vertices:")
        print(f"  q1 (bottom-left): ({q1[0]:.1f}, {q1[1]:.1f})")
        print(f"  q2 (bottom-right): ({q2[0]:.1f}, {q2[1]:.1f})")
        print(f"  q3 (top-left): ({q3[0]:.1f}, {q3[1]:.1f})")

        return np.array([q1, q2, q3])

    def transform_to(self, destination_points):
        """
        destination_points: lista de 3 tuplas [(x1, y1), (x2, y2), (x3, y3)]
        """
        if len(destination_points) != 3:
            raise ValueError("Se requieren exactamente 3 puntos destino")

        # Get source triangle (bounding box corners)
        src_pts = self._bounding_triangle()
        dst_pts = np.array(destination_points)

        print(f"DEBUG: Destination points:")
        for i, pt in enumerate(dst_pts):
            print(f"  d{i + 1}: ({pt[0]:.1f}, {pt[1]:.1f})")

        # Apply transformation
        R, t = self._rigid_transform_2d(src_pts, dst_pts)
        self.transformed_paths = [self._apply_transform(p, R, t) for p in self.original_paths]
        return self.transformed_paths