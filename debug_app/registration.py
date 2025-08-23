"""
Registration - Handle registration points (NPZ loading, YAML export)
Clean implementation referencing registration_manager.py data structures
"""

import numpy as np
import yaml
import os
from typing import List, Dict, Any, Optional, Tuple


class Registration:
    """Handle registration point data"""

    def load_npz_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load registration points from NPZ file

        Args:
            file_path: Path to NPZ file

        Returns:
            List of registration points: [{'machine_pos': [x, y], 'camera_pos': [x, y], 'norm_pos': (u, v)}]
        """
        try:
            data = np.load(file_path, allow_pickle=True)

            # Try different formats
            points = self._extract_from_format_1(data)  # machine_positions, camera_positions
            if points:
                return points

            points = self._extract_from_format_2(data)  # calibration_points array
            if points:
                return points

            points = self._extract_from_format_3(data)  # individual point_X entries
            if points:
                return points

            raise Exception("No recognized registration data format found")

        except Exception as e:
            raise Exception(f"Failed to load NPZ registration file: {e}")

    def _extract_from_format_1(self, data) -> Optional[List[Dict[str, Any]]]:
        """Format: machine_positions, camera_positions arrays"""
        try:
            if 'machine_positions' not in data or 'camera_positions' not in data:
                return None

            machine_positions = data['machine_positions']
            camera_positions = data['camera_positions']
            norm_positions = data.get('norm_positions', None)

            points = []
            for i in range(len(machine_positions)):
                machine_pos = np.asarray(machine_positions[i])[:2]  # Ensure 2D
                camera_pos = np.asarray(camera_positions[i])[:2]  # Ensure 2D

                if norm_positions is not None:
                    norm_pos = tuple(norm_positions[i])
                else:
                    norm_pos = (0.5, 0.5)  # Default

                points.append({
                    'machine_pos': [float(machine_pos[0]), float(machine_pos[1])],
                    'camera_pos': [float(camera_pos[0]), float(camera_pos[1])],
                    'norm_pos': norm_pos
                })

            return points

        except Exception:
            return None

    def _extract_from_format_2(self, data) -> Optional[List[Dict[str, Any]]]:
        """Format: calibration_points array of tuples"""
        try:
            if 'calibration_points' not in data:
                return None

            calibration_data = data['calibration_points']
            points = []

            for point_data in calibration_data:
                if isinstance(point_data, (list, tuple)) and len(point_data) >= 2:
                    machine_pos = np.asarray(point_data[0])[:2]
                    camera_pos = np.asarray(point_data[1])[:2]
                    norm_pos = point_data[2] if len(point_data) > 2 else (0.5, 0.5)

                    points.append({
                        'machine_pos': [float(machine_pos[0]), float(machine_pos[1])],
                        'camera_pos': [float(camera_pos[0]), float(camera_pos[1])],
                        'norm_pos': norm_pos
                    })

            return points

        except Exception:
            return None

    def _extract_from_format_3(self, data) -> Optional[List[Dict[str, Any]]]:
        """Format: individual point_0, point_1, point_2, ... entries"""
        try:
            point_keys = [key for key in data.keys() if key.startswith('point_')]
            if not point_keys:
                return None

            points = []
            for key in sorted(point_keys):
                point_data = data[key].item() if data[key].shape == () else data[key]

                if isinstance(point_data, dict):
                    machine_pos = np.asarray(point_data.get('machine_pos', [0, 0]))[:2]
                    camera_pos = np.asarray(point_data.get('camera_pos', [0, 0]))[:2]
                    norm_pos = tuple(point_data.get('norm_pos', [0.5, 0.5]))

                    points.append({
                        'machine_pos': [float(machine_pos[0]), float(machine_pos[1])],
                        'camera_pos': [float(camera_pos[0]), float(camera_pos[1])],
                        'norm_pos': norm_pos
                    })

            return points

        except Exception:
            return None

    def export_yaml(self, registration_points: List[Dict[str, Any]], file_path: str) -> bool:
        """
        Export registration points to human-readable YAML file

        Args:
            registration_points: List of registration points
            file_path: Output YAML file path

        Returns:
            True if successful
        """
        try:
            if not registration_points:
                raise Exception("No registration points to export")

            # Create YAML structure
            yaml_data = {
                'registration_info': {
                    'point_count': len(registration_points),
                    'format': '2D',
                    'coordinate_system': 'machine_coordinates',
                    'description': 'Registration points for SVG route transformation debugging'
                },
                'points': []
            }

            for i, point in enumerate(registration_points):
                point_data = {
                    'point_id': i + 1,
                    'machine_position': {
                        'x': point['machine_pos'][0],
                        'y': point['machine_pos'][1]
                    },
                    'camera_position': {
                        'x': point['camera_pos'][0],
                        'y': point['camera_pos'][1]
                    },
                    'normalized_position': {
                        'u': point['norm_pos'][0],
                        'v': point['norm_pos'][1]
                    }
                }
                yaml_data['points'].append(point_data)

            # Ensure output directory exists
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Write YAML file
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, indent=2, sort_keys=False)

            return True

        except Exception as e:
            raise Exception(f"Failed to export YAML: {e}")

    def get_triangle_points(self, registration_points: List[Dict[str, Any]]) -> Optional[List[Tuple[float, float]]]:
        """
        Get triangle points for transformation (first 3 machine positions)

        Args:
            registration_points: List of registration points

        Returns:
            List of 3 (x, y) tuples for triangle vertices
        """
        try:
            if len(registration_points) < 3:
                raise Exception("Need at least 3 registration points for triangle")

            # Use first 3 machine positions as triangle vertices
            triangle_points = []
            for i in range(3):
                machine_pos = registration_points[i]['machine_pos']
                triangle_points.append((float(machine_pos[0]), float(machine_pos[1])))

            return triangle_points

        except Exception as e:
            raise Exception(f"Failed to extract triangle points: {e}")

    def calculate_registration_stats(self, registration_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate basic statistics about registration points"""
        try:
            if not registration_points:
                return {'point_count': 0}

            machine_positions = [p['machine_pos'] for p in registration_points]
            camera_positions = [p['camera_pos'] for p in registration_points]

            # Calculate bounds
            machine_x = [pos[0] for pos in machine_positions]
            machine_y = [pos[1] for pos in machine_positions]
            camera_x = [pos[0] for pos in camera_positions]
            camera_y = [pos[1] for pos in camera_positions]

            stats = {
                'point_count': len(registration_points),
                'machine_bounds': {
                    'x_min': min(machine_x),
                    'x_max': max(machine_x),
                    'y_min': min(machine_y),
                    'y_max': max(machine_y)
                },
                'camera_bounds': {
                    'x_min': min(camera_x),
                    'x_max': max(camera_x),
                    'y_min': min(camera_y),
                    'y_max': max(camera_y)
                }
            }

            return stats

        except Exception:
            return {'error': 'Failed to calculate stats'}