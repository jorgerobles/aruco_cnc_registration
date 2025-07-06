"""
Enhanced Hardware Service with Machine Origins and Homing Position
Properly calculates machine bounds based on origin position
"""

from enum import Enum
from typing import Tuple, Dict, Any
from services.event_broker import event_aware, event_handler
from services.grbl_controller import GRBLEvents


class MachineOrigin(Enum):
    """Machine origin positions (where 0,0 is located)"""
    BOTTOM_LEFT = "bottom_left"      # Traditional CNC: 0,0 at bottom-left, positive X right, positive Y back
    BOTTOM_RIGHT = "bottom_right"    # 0,0 at bottom-right, negative X left, positive Y back
    TOP_LEFT = "top_left"            # 0,0 at top-left, positive X right, negative Y front
    TOP_RIGHT = "top_right"          # 0,0 at top-right, negative X left, negative Y front


class HardwareEvents:
    """Hardware events"""
    CAMERA_OFFSET_UPDATED = "hardware.camera_offset_updated"
    MACHINE_SIZE_UPDATED = "hardware.machine_size_updated"
    MACHINE_ORIGIN_UPDATED = "hardware.machine_origin_updated"
    MACHINE_BOUNDS_CALCULATED = "hardware.machine_bounds_calculated"


@event_aware()
class HardwareService:
    """Enhanced hardware service with proper machine origin handling"""

    def __init__(self,
                 machine_size=(450, 450, 80),
                 has_camera=True,
                 camera_offset=(-45, 0, 0),
                 machine_origin=MachineOrigin.BOTTOM_LEFT,
                 homing_position=(-450,-450,0)):

        # Basic hardware info
        self.machine_size = {'x': machine_size[0], 'y': machine_size[1], 'z': machine_size[2]}  # mm
        self.has_camera = has_camera
        self.camera_offset = {'x': camera_offset[0], 'y': camera_offset[1], 'z': camera_offset[2]}  # mm

        # Machine origin configuration (where 0,0 is located)
        self.machine_origin = machine_origin

        # Calculated machine bounds and homing coordinates
        self.homing_position = {'x':homing_position[0], 'y':homing_position[1], 'z':homing_position[2]}
        self.machine_bounds = self._calculate_machine_bounds()

    @event_handler(GRBLEvents.HOMING_POSITION)
    def _set_homing_position(self,evt):
        x,y,z = evt['position'].copy()
        self.homing_position = {'x':x, 'y':y, 'z':z}

    def set_camera_offset(self, x: float, y: float, z: float):
        """Set camera offset and emit event"""
        self.camera_offset = {'x': x, 'y': y, 'z': z}

        self.emit(HardwareEvents.CAMERA_OFFSET_UPDATED, {
            'x': x, 'y': y, 'z': z,
            'offset': self.camera_offset
        })

    def get_camera_offset(self) -> Dict[str, float]:
        """Get camera offset"""
        return self.camera_offset.copy()

    def set_machine_size(self, x: float, y: float, z: float):
        """Set machine size and recalculate bounds"""
        self.machine_size = {'x': x, 'y': y, 'z': z}

        # Recalculate bounds and homing when size changes
        self.machine_bounds = self._calculate_machine_bounds()


        self.emit(HardwareEvents.MACHINE_SIZE_UPDATED, {
            'x': x, 'y': y, 'z': z,
            'size': self.machine_size,
            'bounds': self.machine_bounds,
            'homing_position': self.homing_position
        })

    def get_machine_size(self) -> Dict[str, float]:
        """Get machine size"""
        return self.machine_size.copy()

    def set_machine_origin(self, origin: MachineOrigin):
        """
        Set machine origin position and recalculate bounds

        Args:
            origin: MachineOrigin enum value
        """
        if not isinstance(origin, MachineOrigin):
            raise ValueError(f"Invalid origin type: {origin}. Must be MachineOrigin enum.")

        self.machine_origin = origin

        # Recalculate bounds and homing when origin changes
        self.machine_bounds = self._calculate_machine_bounds()
        self.homing_position = self._calculate_homing_position()

        self.emit(HardwareEvents.MACHINE_ORIGIN_UPDATED, {
            'origin': origin,
            'origin_name': origin.value,
            'bounds': self.machine_bounds,
            'homing_position': self.homing_position
        })

    def get_machine_origin(self) -> MachineOrigin:
        """Get machine origin configuration"""
        return self.machine_origin

    def get_machine_origin_name(self) -> str:
        """Get machine origin name as string"""
        return self.machine_origin.value

    def get_homing_position(self) -> Dict[str, float]:
        """
        Get the actual XY coordinates where the machine homes
        Z is always 0 (assuming Z homes to bottom)

        Returns:
            Dictionary with 'x', 'y', 'z' homing coordinates
        """
        return self.homing_position.copy()



    def _calculate_machine_bounds(self) -> Dict[str, float]:
        """
        Calculate machine coordinate bounds based on origin position

        For a 450x450mm machine:
        - BOTTOM_LEFT: (0,0) to (450,450) - traditional CNC
        - BOTTOM_RIGHT: (-450,0) to (0,450)
        - TOP_LEFT: (0,-450) to (450,0)
        - TOP_RIGHT: (-450,-450) to (0,0)

        Returns bounds as: {'x_min', 'x_max', 'y_min', 'y_max', 'z_min', 'z_max'}
        """
        size = self.machine_size

        # Z bounds are always 0 to max_z (assuming Z homes at bottom)
        z_min = 0.0
        z_max = size['z']

        # XY bounds based on origin position
        if self.machine_origin == MachineOrigin.BOTTOM_LEFT:
            # Traditional CNC: (0,0) at bottom-left, work area extends positive
            x_min = 0.0
            x_max = size['x']
            y_min = 0.0
            y_max = size['y']

        elif self.machine_origin == MachineOrigin.BOTTOM_RIGHT:
            # (0,0) at bottom-right, work area extends negative X, positive Y
            x_min = -size['x']
            x_max = 0.0
            y_min = 0.0
            y_max = size['y']

        elif self.machine_origin == MachineOrigin.TOP_LEFT:
            # (0,0) at top-left, work area extends positive X, negative Y
            x_min = 0.0
            x_max = size['x']
            y_min = -size['y']
            y_max = 0.0

        elif self.machine_origin == MachineOrigin.TOP_RIGHT:
            # (0,0) at top-right, work area extends negative X and Y
            x_min = -size['x']
            x_max = 0.0
            y_min = -size['y']
            y_max = 0.0

        bounds = {
            'x_min': x_min, 'x_max': x_max,
            'y_min': y_min, 'y_max': y_max,
            'z_min': z_min, 'z_max': z_max
        }

        # Emit bounds calculation event
        self.emit(HardwareEvents.MACHINE_BOUNDS_CALCULATED, {
            'bounds': bounds,
            'origin': self.machine_origin,
            'origin_name': self.machine_origin.value,
            'machine_size': self.machine_size,
            'homing_position': self.homing_position
        })

        return bounds

    def get_machine_bounds(self) -> Dict[str, float]:
        """Get calculated machine bounds"""
        return self.machine_bounds.copy()

    def set_has_camera(self, has_camera: bool):
        """Set camera availability"""
        self.has_camera = has_camera

    def get_working_area_info(self) -> Dict[str, Any]:
        """Get comprehensive working area information"""
        return {
            'machine_size': self.machine_size.copy(),
            'machine_origin': self.machine_origin,
            'origin_name': self.machine_origin.value,
            'homing_position': self.homing_position.copy(),
            'machine_bounds': self.machine_bounds.copy(),
            'camera_offset': self.camera_offset.copy(),
            'has_camera': self.has_camera
        }

    def is_coordinate_in_bounds(self, x: float, y: float, z: float) -> bool:
        """Check if coordinates are within machine bounds"""
        bounds = self.machine_bounds
        return (bounds['x_min'] <= x <= bounds['x_max'] and
                bounds['y_min'] <= y <= bounds['y_max'] and
                bounds['z_min'] <= z <= bounds['z_max'])

    def get_coordinate_status(self, x: float, y: float, z: float) -> Dict[str, Any]:
        """Get detailed status of coordinates relative to machine"""
        bounds = self.machine_bounds
        homing_coords = self.homing_position

        return {
            'coordinates': {'x': x, 'y': y, 'z': z},
            'in_bounds': self.is_coordinate_in_bounds(x, y, z),
            'distance_from_home': {
                'x': x - homing_coords['x'],
                'y': y - homing_coords['y'],
                'z': z - homing_coords['z']
            },
            'bounds_violations': {
                'x_under': x < bounds['x_min'],
                'x_over': x > bounds['x_max'],
                'y_under': y < bounds['y_min'],
                'y_over': y > bounds['y_max'],
                'z_under': z < bounds['z_min'],
                'z_over': z > bounds['z_max']
            },
            'origin_info': {
                'origin': self.machine_origin,
                'origin_name': self.machine_origin.value,
                'homing_position': homing_coords
            }
        }

    def get_safe_coordinates(self, x: float, y: float, z: float) -> Dict[str, float]:
        """Clamp coordinates to safe machine bounds"""
        bounds = self.machine_bounds

        safe_x = max(bounds['x_min'], min(bounds['x_max'], x))
        safe_y = max(bounds['y_min'], min(bounds['y_max'], y))
        safe_z = max(bounds['z_min'], min(bounds['z_max'], z))

        return {'x': safe_x, 'y': safe_y, 'z': safe_z}

    def convert_to_machine_coordinates(self, work_x: float, work_y: float, work_z: float = 0.0) -> Dict[str, float]:
        """
        Convert work coordinates to machine coordinates
        Work coordinates are relative to work piece origin
        Machine coordinates are relative to machine origin
        """
        # For now, just return the same coordinates
        # This could be enhanced to handle work coordinate systems
        return {'x': work_x, 'y': work_y, 'z': work_z}

    def get_origin_description(self) -> str:
        """Get human-readable description of the origin configuration"""
        descriptions = {
            MachineOrigin.BOTTOM_LEFT: "Bottom-Left (0,0) - Traditional CNC, positive X→right, positive Y→back",
            MachineOrigin.BOTTOM_RIGHT: "Bottom-Right (0,0) - Negative X→left, positive Y→back",
            MachineOrigin.TOP_LEFT: "Top-Left (0,0) - Positive X→right, negative Y→front",
            MachineOrigin.TOP_RIGHT: "Top-Right (0,0) - Negative X→left, negative Y→front"
        }
        return descriptions.get(self.machine_origin, "Unknown origin")

    def get_all_origins(self) -> Dict[str, str]:
        """Get all available origins with descriptions"""
        return {
            origin.value: f"{origin.value.replace('_', ' ').title()}"
            for origin in MachineOrigin
        }

    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current hardware configuration"""
        issues = []
        warnings = []

        # Check machine size
        if any(size <= 0 for size in self.machine_size.values()):
            issues.append("Machine size must be positive")

        # Check bounds calculation
        bounds = self.machine_bounds
        if bounds['x_min'] >= bounds['x_max'] or bounds['y_min'] >= bounds['y_max']:
            issues.append("Invalid machine bounds calculated")

        # Check camera offset relative to machine size
        offset = self.camera_offset
        if abs(offset['x']) > self.machine_size['x'] or abs(offset['y']) > self.machine_size['y']:
            warnings.append("Camera offset is larger than machine size")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'configuration': {
                'machine_size': self.machine_size,
                'origin': self.machine_origin.value,
                'bounds': self.machine_bounds,
                'homing_position': self.homing_position,
                'camera_offset': self.camera_offset
            }
        }