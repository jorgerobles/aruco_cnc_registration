# route_transformer.py

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
        all_points = np.vstack(self.original_paths)
        min_xy = np.min(all_points, axis=0)
        max_xy = np.max(all_points, axis=0)

        q1 = min_xy
        q2 = [max_xy[0], min_xy[1]]
        q3 = [min_xy[0], max_xy[1]]
        return np.array([q1, q2, q3])

    def transform_to(self, destination_points):
        """
        destination_points: lista de 3 tuplas [(x1, y1), (x2, y2), (x3, y3)]
        """
        if len(destination_points) != 3:
            raise ValueError("Se requieren exactamente 3 puntos destino")
        
        src_pts = self._bounding_triangle()
        dst_pts = np.array(destination_points)

        R, t = self._rigid_transform_2d(src_pts, dst_pts)
        self.transformed_paths = [self._apply_transform(p, R, t) for p in self.original_paths]
        return self.transformed_paths
