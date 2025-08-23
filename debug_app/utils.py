"""
Debug Utilities - Common utilities for the debugging application
"""

import os
import sys
from typing import Any, Callable


class DebugLogger:
    """Simple logger wrapper for consistent logging across debug components"""

    def __init__(self, logger):
        self.logger = logger

    def info(self, message: str):
        """Log info message"""
        if self.logger:
            self.logger.info(f"[DEBUG] {message}")
        else:
            print(f"[DEBUG INFO] {message}")

    def warning(self, message: str):
        """Log warning message"""
        if self.logger:
            self.logger.warning(f"[DEBUG] {message}")
        else:
            print(f"[DEBUG WARNING] {message}")

    def error(self, message: str):
        """Log error message"""
        if self.logger:
            self.logger.error(f"[DEBUG] {message}")
        else:
            print(f"[DEBUG ERROR] {message}")


def validate_file_path(file_path: str, extensions: list = None) -> bool:
    """
    Validate file path exists and has correct extension

    Args:
        file_path: Path to validate
        extensions: List of allowed extensions (e.g., ['.svg', '.npz'])

    Returns:
        True if valid
    """
    try:
        if not file_path:
            return False

        if not os.path.exists(file_path):
            return False

        if not os.path.isfile(file_path):
            return False

        if extensions:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in [ext.lower() for ext in extensions]:
                return False

        return True

    except Exception:
        return False


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with fallback"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """Safely convert value to int with fallback"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def format_coordinate(x: float, y: float, precision: int = 2) -> str:
    """Format coordinate pair for display"""
    return f"({x:.{precision}f}, {y:.{precision}f})"


def format_distance(distance: float, unit: str = "mm") -> str:
    """Format distance for display"""
    if distance < 1.0:
        return f"{distance:.3f}{unit}"
    elif distance < 10.0:
        return f"{distance:.2f}{unit}"
    else:
        return f"{distance:.1f}{unit}"


def calculate_distance(p1: tuple, p2: tuple) -> float:
    """Calculate Euclidean distance between two points"""
    try:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return (dx * dx + dy * dy) ** 0.5
    except (IndexError, TypeError):
        return 0.0


def calculate_triangle_area(triangle: list) -> float:
    """Calculate area of triangle given 3 points"""
    try:
        if len(triangle) != 3:
            return 0.0

        p1, p2, p3 = triangle
        # Using cross product formula: |AB × AC| / 2
        ab = (p2[0] - p1[0], p2[1] - p1[1])
        ac = (p3[0] - p1[0], p3[1] - p1[1])

        cross_product = ab[0] * ac[1] - ab[1] * ac[0]
        return abs(cross_product) / 2.0

    except (IndexError, TypeError):
        return 0.0


def ensure_directory_exists(file_path: str):
    """Ensure directory for file path exists"""
    try:
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
    except Exception as e:
        print(f"Warning: Could not create directory for {file_path}: {e}")


def get_application_directory() -> str:
    """Get the directory where the application is located"""
    try:
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            return os.path.dirname(sys.executable)
        else:
            # Running as script
            return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def get_default_file_locations() -> dict:
    """Get default locations for various file types"""
    app_dir = get_application_directory()

    return {
        'svg_files': os.path.join(app_dir, 'test_data', 'svg'),
        'registration_files': os.path.join(app_dir, 'test_data', 'registration'),
        'output_files': os.path.join(app_dir, 'output')
    }


class CoordinateConverter:
    """Utility class for coordinate system conversions"""

    def __init__(self, machine_bounds: dict):
        """
        Initialize coordinate converter

        Args:
            machine_bounds: Dict with 'x_min', 'x_max', 'y_min', 'y_max', 'width', 'height'
        """
        self.machine_bounds = machine_bounds

    def machine_to_normalized(self, x: float, y: float) -> tuple:
        """Convert machine coordinates to 0-1 normalized coordinates"""
        try:
            norm_x = (x - self.machine_bounds['x_min']) / self.machine_bounds['width']
            norm_y = (y - self.machine_bounds['y_min']) / self.machine_bounds['height']
            return norm_x, norm_y
        except (KeyError, ZeroDivisionError):
            return 0.0, 0.0

    def normalized_to_machine(self, norm_x: float, norm_y: float) -> tuple:
        """Convert 0-1 normalized coordinates to machine coordinates"""
        try:
            x = self.machine_bounds['x_min'] + norm_x * self.machine_bounds['width']
            y = self.machine_bounds['y_min'] + norm_y * self.machine_bounds['height']
            return x, y
        except KeyError:
            return 0.0, 0.0

    def machine_to_display(self, x: float, y: float, display_width: int, display_height: int, margin: int = 0) -> tuple:
        """Convert machine coordinates to display coordinates (for UI)"""
        try:
            # Normalize
            norm_x, norm_y = self.machine_to_normalized(x, y)

            # Convert to display coordinates
            available_width = display_width - 2 * margin
            available_height = display_height - 2 * margin

            display_x = margin + norm_x * available_width
            display_y = margin + (1 - norm_y) * available_height  # Flip Y axis for display

            return int(display_x), int(display_y)
        except (KeyError, ZeroDivisionError):
            return margin, margin

    def display_to_machine(self, display_x: int, display_y: int, display_width: int, display_height: int,
                           margin: int = 0) -> tuple:
        """Convert display coordinates to machine coordinates"""
        try:
            # Remove margins
            available_width = display_width - 2 * margin
            available_height = display_height - 2 * margin

            norm_x = (display_x - margin) / available_width
            norm_y = 1 - (display_y - margin) / available_height  # Flip Y axis

            # Convert to machine coordinates
            return self.normalized_to_machine(norm_x, norm_y)
        except ZeroDivisionError:
            return 0.0, 0.0


def validate_svg_file(file_path: str) -> dict:
    """Validate SVG file and return info"""
    result = {
        'valid': False,
        'error': None,
        'file_size': 0,
        'readable': False
    }

    try:
        if not validate_file_path(file_path, ['.svg']):
            result['error'] = "Invalid file path or not an SVG file"
            return result

        result['file_size'] = os.path.getsize(file_path)

        # Try to read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(100)  # Read first 100 characters
            if '<svg' in content.lower():
                result['readable'] = True
                result['valid'] = True
            else:
                result['error'] = "File doesn't appear to contain SVG content"

    except Exception as e:
        result['error'] = str(e)

    return result


def validate_npz_file(file_path: str) -> dict:
    """Validate NPZ file and return info"""
    result = {
        'valid': False,
        'error': None,
        'file_size': 0,
        'keys': [],
        'loadable': False
    }

    try:
        import numpy as np

        if not validate_file_path(file_path, ['.npz']):
            result['error'] = "Invalid file path or not an NPZ file"
            return result

        result['file_size'] = os.path.getsize(file_path)

        # Try to load NPZ file
        data = np.load(file_path, allow_pickle=True)
        result['keys'] = list(data.keys())
        result['loadable'] = True
        result['valid'] = True

    except Exception as e:
        result['error'] = str(e)

    return result