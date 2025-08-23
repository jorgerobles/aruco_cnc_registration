"""
RouteLoader - Load SVG files using svgpathtools (copied from svg_loader.py)
Clean implementation using the proven svg_loader.py approach
"""

import math
import os
from xml.dom import minidom
from typing import List, Tuple, Optional

from svgpathtools import svg2paths2


class RouteLoader:
    """Load routes from SVG files using svgpathtools"""

    def load_svg_file(self, file_path: str, angle_threshold: float = 5.0,
                      skip_display_none: bool = True) -> List[List[Tuple[float, float]]]:
        """
        Load routes from SVG file (copied from svg_loader.py)

        Args:
            file_path: Path to SVG file
            angle_threshold: Angle threshold for path conversion
            skip_display_none: Skip elements with display:none

        Returns:
            List of routes, each route is list of (x, y) tuples
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"SVG file not found: {file_path}")

            return self._svg_to_routes(file_path, angle_threshold, skip_display_none)

        except Exception as e:
            raise Exception(f"Failed to load SVG file: {e}")

    def _svg_to_routes(self, svg_file: str, angle_threshold: float = 5.0,
                       skip_display_none: bool = True) -> List[List[Tuple[float, float]]]:
        """
        Convert SVG file to routes (copied from svg_loader.py)
        """
        # Read SVG to extract viewBox, width and height
        doc = minidom.parse(svg_file)
        svg_tag = doc.getElementsByTagName('svg')[0]

        view_box = svg_tag.getAttribute('viewBox')
        width_attr = svg_tag.getAttribute('width')
        height_attr = svg_tag.getAttribute('height')

        if not view_box or not width_attr or not height_attr:
            raise ValueError("SVG must have 'viewBox', 'width' and 'height' defined.")

        # Parse viewBox and dimensions
        vb_x, vb_y, vb_width, vb_height = map(float, view_box.strip().split())
        width = float(width_attr.replace("mm", "").strip())
        height = float(height_attr.replace("mm", "").strip())

        scale_x = width / vb_width
        scale_y = height / vb_height

        # Get all path elements from DOM to check visibility
        path_elements = doc.getElementsByTagName('path')
        visible_path_elements = []

        if skip_display_none:
            for path_elem in path_elements:
                if not self._is_element_hidden(path_elem, skip_display_none):
                    visible_path_elements.append(path_elem)
        else:
            visible_path_elements = path_elements

        # Extract paths using svg2paths2
        paths, attributes, svg_attributes = svg2paths2(svg_file)

        # Filter paths to only include visible ones
        routes = []
        for i, path in enumerate(paths):
            # If we're skipping hidden elements, we need to match this path with DOM elements
            if skip_display_none and i < len(path_elements):
                path_elem = path_elements[i]
                if self._is_element_hidden(path_elem, skip_display_none):
                    continue

            points_raw = self._convert_paths(path, angle_threshold=angle_threshold)

            # Apply scale + translation from viewBox
            # Transform coordinates so origin is bottom-left corner
            # Therefore, invert Y axis (height - y) to change direction
            points_trans = [
                ((x - vb_x) * scale_x, height - (y - vb_y) * scale_y) for x, y in points_raw
            ]

            if points_trans and len(points_trans) >= 2:  # Need at least 2 points
                routes.append(points_trans)

        return routes

    def _convert_paths(self, path, num_points: int = 50, angle_threshold: float = 5.0) -> List[Tuple[float, float]]:
        """
        Convert path segments to points, dividing only when there's angle variation (copied from svg_loader.py)

        Args:
            path: SVG path to convert
            num_points: Number of points per segment for sampling
            angle_threshold: Angle threshold in degrees for significant change

        Returns:
            List of points where each point is a (x, y) tuple
        """
        points = []

        # Extract all points first
        all_points = []
        for segment in path:
            for t in [i / num_points for i in range(num_points + 1)]:
                point = segment.point(t)
                all_points.append((point.real, point.imag))

        # If not enough points, return as-is
        if len(all_points) <= 2:
            return all_points

        # First point always goes in sequence
        points.append(all_points[0])
        last_angle = None

        # Analyze direction changes
        for i in range(len(all_points) - 1):
            p1 = all_points[i]
            p2 = all_points[i + 1]

            # Calculate vector direction
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]

            # Avoid division by zero in very small segments
            if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                continue

            # Calculate angle in degrees (0-360)
            current_angle = math.degrees(math.atan2(dy, dx)) % 360

            # For first point, just set initial angle
            if last_angle is None:
                last_angle = current_angle
                continue

            # Calculate angle difference (handle circular 0-360 case)
            diff = min(abs(current_angle - last_angle), 360 - abs(current_angle - last_angle))

            # If significant angle change, mark this point
            if diff > angle_threshold:
                # Mark this point as direction change point
                points.append(p1)
                last_angle = current_angle

        # Ensure last point is always included
        if all_points and points[-1] != all_points[-1]:
            points.append(all_points[-1])

        return points

    def _is_element_hidden(self, element, skip_display_none: bool = True) -> bool:
        """
        Check if SVG element should be skipped based on display attributes (copied from svg_loader.py)
        Checks element and all parent elements for display:none
        """
        if not skip_display_none:
            return False

        current = element
        while current and current.nodeType == current.ELEMENT_NODE:
            # Check for display:none in style attribute
            style = current.getAttribute('style') if current.hasAttribute('style') else ''
            if 'display:none' in style.replace(' ', ''):
                return True

            # Check for direct display attribute
            display = current.getAttribute('display') if current.hasAttribute('display') else ''
            if display.strip() == 'none':
                return True

            # Move to parent element
            current = current.parentNode

        return False

    def get_route_bounds(self, routes: List[List[Tuple[float, float]]]) -> Optional[dict]:
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
                'height': max(all_y) - min(all_y),
                'center_x': (min(all_x) + max(all_x)) / 2,
                'center_y': (min(all_y) + max(all_y)) / 2
            }

        except Exception:
            return None

    def get_route_statistics(self, routes: List[List[Tuple[float, float]]]) -> dict:
        """Get comprehensive route statistics"""
        try:
            if not routes:
                return {
                    'route_count': 0,
                    'total_points': 0,
                    'bounds': None
                }

            total_points = sum(len(route) for route in routes)
            bounds = self.get_route_bounds(routes)

            # Calculate total length
            total_length = 0.0
            for route in routes:
                for i in range(len(route) - 1):
                    dx = route[i + 1][0] - route[i][0]
                    dy = route[i + 1][1] - route[i][1]
                    total_length += (dx * dx + dy * dy) ** 0.5

            return {
                'route_count': len(routes),
                'total_points': total_points,
                'total_length': total_length,
                'average_points_per_route': total_points / len(routes) if routes else 0,
                'average_route_length': total_length / len(routes) if routes else 0,
                'bounds': bounds
            }

        except Exception as e:
            return {'error': str(e)}