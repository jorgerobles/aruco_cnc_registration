"""
SVG Exporter Module - Fixed viewBox calculation
Converts routes (list of point lists) back to SVG format
Calculates viewBox after coordinate transformation to ensure all routes are visible
"""

import os
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime


def routes_to_svg(routes: List[List[Tuple[float, float]]],
                  output_file: str,
                  width_mm: float = None,
                  height_mm: float = None,
                  margin_mm: float = 5.0,
                  stroke_width: float = 0.1,
                  stroke_color: str = "black",
                  metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Export routes to SVG file with proper coordinate transformation

    Args:
        routes: List of routes, each route is a list of (x, y) points in mm (machine coordinates)
        output_file: Output SVG file path
        width_mm: SVG width (auto-calculated if None)
        height_mm: SVG height (auto-calculated if None)
        margin_mm: Margin around content
        stroke_width: Line width for paths
        stroke_color: Color for the paths
        metadata: Optional metadata dict

    Returns:
        True if export successful
    """
    try:
        if not routes or len(routes) == 0:
            return False

        # Calculate bounds in machine coordinates
        machine_bounds = _calculate_route_bounds(routes)
        if not machine_bounds:
            return False

        # Auto-size if dimensions not provided
        if width_mm is None or height_mm is None:
            width_mm, height_mm = _calculate_auto_dimensions(machine_bounds, margin_mm)

        # Transform routes to SVG coordinates first
        svg_routes = _transform_routes_to_svg_coords(routes, machine_bounds, width_mm, height_mm, margin_mm)

        # Calculate bounds of SVG coordinates
        svg_bounds = _calculate_route_bounds(svg_routes)
        if not svg_bounds:
            return False

        # Create viewBox that encompasses all SVG coordinates with margin
        viewbox = _calculate_viewbox(svg_bounds, margin_mm / max(width_mm, height_mm) * min(svg_bounds[2] - svg_bounds[0], svg_bounds[3] - svg_bounds[1]))

        # Create SVG content
        svg_content = _create_svg_content(
            svg_routes, viewbox, width_mm, height_mm,
            stroke_width, stroke_color, metadata
        )

        # Write file
        _write_svg_file(output_file, svg_content)
        return True

    except Exception as e:
        # For debugging - you can remove this in production
        print(f"Export error: {e}")
        return False


def _calculate_route_bounds(routes: List[List[Tuple[float, float]]]) -> Optional[List[float]]:
    """Calculate bounding box of all routes"""
    try:
        all_x = []
        all_y = []

        for route in routes:
            for x, y in route:
                all_x.append(x)
                all_y.append(y)

        if not all_x or not all_y:
            return None

        return [min(all_x), min(all_y), max(all_x), max(all_y)]

    except Exception:
        return None


def _calculate_auto_dimensions(bounds: List[float], margin_mm: float) -> Tuple[float, float]:
    """Calculate SVG dimensions with auto-sizing"""
    x_min, y_min, x_max, y_max = bounds
    route_width = x_max - x_min
    route_height = y_max - y_min

    # Add margins
    width_mm = route_width + (2 * margin_mm)
    height_mm = route_height + (2 * margin_mm)

    # Minimum size
    width_mm = max(width_mm, 20.0)
    height_mm = max(height_mm, 20.0)

    return width_mm, height_mm


def _transform_routes_to_svg_coords(routes: List[List[Tuple[float, float]]],
                                   machine_bounds: List[float],
                                   width_mm: float,
                                   height_mm: float,
                                   margin_mm: float) -> List[List[Tuple[float, float]]]:
    """
    Transform routes from machine coordinates to SVG coordinates
    This reverses the transformation from svg_loader.py
    """
    x_min, y_min, x_max, y_max = machine_bounds
    machine_width = x_max - x_min
    machine_height = y_max - y_min

    # Available space after margins
    available_width = width_mm - (2 * margin_mm)
    available_height = height_mm - (2 * margin_mm)

    # Calculate scale to fit machine coordinates in available space
    if machine_width > 0 and machine_height > 0:
        scale_x = available_width / machine_width
        scale_y = available_height / machine_height
        # Use uniform scaling to maintain aspect ratio
        scale = min(scale_x, scale_y)
    else:
        scale = 1.0

    # Calculate SVG coordinate space
    svg_width = machine_width * scale if machine_width > 0 else available_width
    svg_height = machine_height * scale if machine_height > 0 else available_height

    # Calculate centering offset in SVG coordinate space
    center_offset_x = (available_width - svg_width) / 2
    center_offset_y = (available_height - svg_height) / 2

    svg_routes = []

    for route in routes:
        svg_route = []
        for machine_x, machine_y in route:
            # Transform to SVG coordinates
            # 1. Normalize to 0-1 range based on machine bounds
            norm_x = (machine_x - x_min) / machine_width if machine_width > 0 else 0
            norm_y = (machine_y - y_min) / machine_height if machine_height > 0 else 0

            # 2. Scale to SVG coordinate space
            svg_x = norm_x * svg_width + margin_mm + center_offset_x
            # 3. Flip Y coordinate (SVG origin is top-left, machine is bottom-left)
            svg_y = height_mm - (norm_y * svg_height + margin_mm + center_offset_y)

            svg_route.append((svg_x, svg_y))

        svg_routes.append(svg_route)

    return svg_routes


def _calculate_viewbox(svg_bounds: List[float], margin_svg: float) -> Dict[str, float]:
    """Calculate viewBox parameters to contain all SVG coordinates"""
    x_min, y_min, x_max, y_max = svg_bounds

    # Add margin in SVG coordinate space
    vb_x = x_min - margin_svg
    vb_y = y_min - margin_svg
    vb_width = (x_max - x_min) + (2 * margin_svg)
    vb_height = (y_max - y_min) + (2 * margin_svg)

    return {
        'x': vb_x,
        'y': vb_y,
        'width': vb_width,
        'height': vb_height
    }


def _create_svg_content(svg_routes: List[List[Tuple[float, float]]],
                       viewbox: Dict[str, float],
                       width_mm: float, height_mm: float,
                       stroke_width: float, stroke_color: str,
                       metadata: Optional[Dict[str, Any]]) -> str:
    """Create SVG document content with proper viewBox"""

    # SVG header with calculated viewBox
    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg width="{width_mm}mm" height="{height_mm}mm" '
        f'viewBox="{viewbox["x"]:.3f} {viewbox["y"]:.3f} {viewbox["width"]:.3f} {viewbox["height"]:.3f}" '
        f'xmlns="http://www.w3.org/2000/svg">'
    ]

    # Add metadata
    svg_lines.extend([
        '  <!-- Generated by SVG Exporter -->',
        f'  <!-- Export timestamp: {datetime.now().isoformat()} -->',
        f'  <!-- Route count: {len(svg_routes)} -->'
    ])

    if metadata:
        for key, value in metadata.items():
            svg_lines.append(f'  <!-- {key}: {value} -->')

    # Add routes as paths
    svg_lines.append('  <!-- Routes -->')

    for i, route in enumerate(svg_routes):
        if len(route) < 2:
            continue

        path_data = _route_to_svg_path(route)
        svg_lines.append(
            f'  <path d="{path_data}" '
            f'fill="none" stroke="{stroke_color}" stroke-width="{stroke_width}" '
            f'id="route_{i}"/>'
        )

    svg_lines.append('</svg>')
    return '\n'.join(svg_lines)


def _route_to_svg_path(route: List[Tuple[float, float]]) -> str:
    """Convert route points to SVG path data"""
    if not route:
        return ""

    path_parts = []

    # Move to first point
    x, y = route[0]
    path_parts.append(f"M {x:.3f} {y:.3f}")

    # Line to subsequent points
    for x, y in route[1:]:
        path_parts.append(f"L {x:.3f} {y:.3f}")

    return " ".join(path_parts)


def _write_svg_file(output_file: str, svg_content: str):
    """Write SVG content to file"""
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Write SVG content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(svg_content)