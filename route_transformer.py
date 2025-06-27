"""
Route Transformer
Transforms SVG routes to machine coordinates using registration data
"""

import numpy as np
from typing import List, Tuple, Optional
from svg.svg_loader import svg_to_routes
from registration.registration_manager import RegistrationManager


class RouteTransformer:
    """Transforms SVG routes to machine coordinates using camera registration"""

    def __init__(self, registration_manager: RegistrationManager):
        """
        Initialize with a RegistrationManager instance

        Args:
            registration_manager: Configured RegistrationManager with computed registration
        """
        self.registration_manager = registration_manager

    def load_and_transform_svg(self, svg_file: str, angle_threshold: float = 5.0) -> List[List[Tuple[float, float]]]:
        """
        Load SVG routes and transform them to machine coordinates

        Args:
            svg_file: Path to SVG file
            angle_threshold: Angle threshold for path conversion

        Returns:
            List of transformed routes, where each route is a list of (x, y) machine coordinates
        """
        if not self.registration_manager.is_registered():
            raise ValueError("Registration manager must be registered before transforming routes")

        # Load SVG routes
        svg_routes = svg_to_routes(svg_file, angle_threshold=angle_threshold)

        # Transform each route
        transformed_routes = []
        for route in svg_routes:
            transformed_route = self.transform_route(route)
            transformed_routes.append(transformed_route)

        return transformed_routes

    def transform_route(self, route: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Transform a single route from SVG coordinates to machine coordinates

        Args:
            route: List of (x, y) coordinates in SVG space

        Returns:
            List of (x, y) coordinates in machine space
        """
        if not self.registration_manager.is_registered():
            raise ValueError("Registration manager must be registered before transforming routes")

        transformed_points = []

        for x, y in route:
            # Convert 2D SVG point to 3D for transformation (assuming z=0)
            svg_point = np.array([x, y, 0.0])

            # Transform to machine coordinates
            machine_point = self.registration_manager.transform_point(svg_point)

            # Extract x, y coordinates (assuming we only need 2D output)
            transformed_points.append((machine_point[0], machine_point[1]))

        return transformed_points

    def transform_single_point(self, x: float, y: float, z: float = 0.0) -> Tuple[float, float, float]:
        """
        Transform a single point from SVG coordinates to machine coordinates

        Args:
            x, y: SVG coordinates
            z: Z coordinate (default 0.0)

        Returns:
            (x, y, z) machine coordinates
        """
        if not self.registration_manager.is_registered():
            raise ValueError("Registration manager must be registered before transforming points")

        svg_point = np.array([x, y, z])
        machine_point = self.registration_manager.transform_point(svg_point)

        return (machine_point[0], machine_point[1], machine_point[2])

    def get_route_bounds(self, routes: List[List[Tuple[float, float]]]) -> Tuple[float, float, float, float]:
        """
        Get bounding box of all transformed routes

        Args:
            routes: List of transformed routes

        Returns:
            (min_x, min_y, max_x, max_y) bounding box
        """
        if not routes:
            return (0, 0, 0, 0)

        all_x = []
        all_y = []

        for route in routes:
            for x, y in route:
                all_x.append(x)
                all_y.append(y)

        return (min(all_x), min(all_y), max(all_x), max(all_y))

    def get_total_route_length(self, routes: List[List[Tuple[float, float]]]) -> float:
        """
        Calculate total length of all routes

        Args:
            routes: List of transformed routes

        Returns:
            Total length in mm
        """
        total_distance = 0.0

        for route in routes:
            for i in range(len(route) - 1):
                x1, y1 = route[i]
                x2, y2 = route[i + 1]
                distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                total_distance += distance

        return total_distance


def example_usage():
    """Example of how to use the RouteTransformer"""

    # Create and configure registration manager
    reg_manager = RegistrationManager()

    # Add calibration points (example data)
    # In practice, these would come from your calibration process
    machine_pos1 = np.array([10.0, 10.0, 0.0])
    camera_tvec1 = np.array([100.0, 100.0, 0.0])
    norm_pos1 = np.array([0.1, 0.1])
    reg_manager.add_calibration_point(machine_pos1, camera_tvec1, norm_pos1)

    machine_pos2 = np.array([50.0, 10.0, 0.0])
    camera_tvec2 = np.array([500.0, 100.0, 0.0])
    norm_pos2 = np.array([0.5, 0.1])
    reg_manager.add_calibration_point(machine_pos2, camera_tvec2, norm_pos2)

    machine_pos3 = np.array([30.0, 40.0, 0.0])
    camera_tvec3 = np.array([300.0, 400.0, 0.0])
    norm_pos3 = np.array([0.3, 0.4])
    reg_manager.add_calibration_point(machine_pos3, camera_tvec3, norm_pos3)

    # Compute registration
    try:
        reg_manager.compute_registration()
        print(f"Registration successful! Error: {reg_manager.get_registration_error():.3f}mm")
    except Exception as e:
        print(f"Registration failed: {e}")
        return

    # Create route transformer
    transformer = RouteTransformer(reg_manager)

    # Transform SVG routes
    try:
        svg_file = "data/test_registro.svg"  # Replace with your SVG file
        transformed_routes = transformer.load_and_transform_svg(svg_file)

        print(f"Loaded {len(transformed_routes)} routes")

        # Get bounds
        bounds = transformer.get_route_bounds(transformed_routes)
        print(f"Route bounds: X({bounds[0]:.2f}, {bounds[2]:.2f}) Y({bounds[1]:.2f}, {bounds[3]:.2f})")

        # Calculate total route length
        total_length = transformer.get_total_route_length(transformed_routes)
        print(f"Total route length: {total_length:.2f} mm")

    except Exception as e:
        print(f"Error processing SVG: {e}")


if __name__ == "__main__":
    example_usage()