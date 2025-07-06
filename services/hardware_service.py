"""
Corrected Hardware Service
Properly separates origin position from homing coordinates
Origin = where (0,0) is located in coordinate system
Homing = where machine physically moves when homing
"""

from enum import Enum
from typing import Dict, Any, Tuple
from services.event_broker import event_aware


class MachineOrigin(Enum):
    """Machine origin positions (where 0,0 is located in coordinate system)"""
    BOTTOM_LEFT = "bottom_left"      # (0,0) at bottom-left of work area
    BOTTOM_RIGHT = "bottom_right"    # (0,0) at bottom-right of work area
    TOP_LEFT = "top_left"            # (0,0) at top-left of work area
    TOP_RIGHT = "top_right"          # (0,0) at top-right of work area


class HardwareEvents:
    """Hardware events"""
    CAMERA_OFFSET_UPDATED = "hardware.camera_offset_updated"
    MACHINE_SIZE_UPDATED = "hardware.machine_size_updated"
    MACHINE_ORIGIN_UPDATED = "hardware.machine_origin_updated"
    HOMING_POSITION_UPDATED = "hardware.homing_position_updated"


@event_aware()
class HardwareService:
    """Hardware service with proper origin vs homing separation"""

    def __init__(self,
                 machine_size=(450, 450, 80),
                 has_camera=True,
                 camera_offset=(-45, 0, 0),
                 machine_origin=MachineOrigin.BOTTOM_LEFT,
                 homing_position=(-450,-450,0)):  # NEW: separate homing position

        # Basic hardware info
        self.machine_size = {'x': machine_size[0], 'y': machine_size[1], 'z': machine_size[2]}
        self.has_camera = has_camera
        self.camera_offset = {'x': camera_offset[0], 'y': camera_offset[1], 'z': camera_offset[2]}
        self.machine_origin = machine_origin

        # Homing position - where machine physically goes when homing
        # Default: same as origin, but can be overridden
        if homing_position is None:
            self.homing_position = self._calculate_default_homing_position()
        else:
            self.homing_position = {'x': homing_position[0], 'y': homing_position[1], 'z': homing_position[2]}

        # Calculate derived values
        self.machine_bounds = self._calculate_machine_bounds()

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

        # Recalculate derived values
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
        """Set machine origin position and recalculate bounds"""
        if not isinstance(origin, MachineOrigin):
            raise ValueError(f"Invalid origin type: {origin}. Must be MachineOrigin enum.")

        self.machine_origin = origin

        # Recalculate bounds when origin changes
        self.machine_bounds = self._calculate_machine_bounds()

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

    def set_homing_position(self, x: float, y: float, z: float):
        """Set where machine physically homes to (independent of origin)"""
        self.homing_position = {'x': x, 'y': y, 'z': z}

        self.emit(HardwareEvents.HOMING_POSITION_UPDATED, {
            'x': x, 'y': y, 'z': z,
            'homing_position': self.homing_position,
            'origin': self.machine_origin,
            'bounds': self.machine_bounds
        })

    def get_homing_position(self) -> Dict[str, float]:
        """Get where machine physically homes to"""
        return self.homing_position.copy()

    def get_machine_bounds(self) -> Dict[str, float]:
        """Get calculated machine coordinate bounds based on origin"""
        return self.machine_bounds.copy()

    def set_has_camera(self, has_camera: bool):
        """Set camera availability"""
        self.has_camera = has_camera

    def _calculate_default_homing_position(self) -> Dict[str, float]:
        """Calculate default homing position - usually bottom-left corner physically"""
        # Most machines home to bottom-left corner physically, regardless of origin
        # This can be overridden for machines that home elsewhere
        size = self.machine_size

        if self.machine_origin == MachineOrigin.BOTTOM_LEFT:
            # Origin at bottom-left (0,0), home to same place
            return {'x': 0.0, 'y': 0.0, 'z': 0.0}
        elif self.machine_origin == MachineOrigin.BOTTOM_RIGHT:
            # Origin at bottom-right (0,0), but home to bottom-left corner physically
            return {'x': -size['x'], 'y': 0.0, 'z': 0.0}
        elif self.machine_origin == MachineOrigin.TOP_LEFT:
            # Origin at top-left (0,0), but home to bottom-left corner physically
            return {'x': 0.0, 'y': -size['y'], 'z': 0.0}
        elif self.machine_origin == MachineOrigin.TOP_RIGHT:
            # Origin at top-right (0,0), but home to bottom-left corner physically
            return {'x': -size['x'], 'y': -size['y'], 'z': 0.0}

    def _calculate_machine_bounds(self) -> Dict[str, float]:
        """Calculate machine coordinate bounds based on origin position"""
        size = self.machine_size

        # Z bounds are always 0 to max_z
        z_min = 0.0
        z_max = size['z']

        # XY bounds based on origin position (where 0,0 is located)
        if self.machine_origin == MachineOrigin.BOTTOM_LEFT:
            # (0,0) at bottom-left, work area extends positive
            x_min, x_max = 0.0, size['x']
            y_min, y_max = 0.0, size['y']

        elif self.machine_origin == MachineOrigin.BOTTOM_RIGHT:
            # (0,0) at bottom-right, work area extends negative X, positive Y
            x_min, x_max = -size['x'], 0.0
            y_min, y_max = 0.0, size['y']

        elif self.machine_origin == MachineOrigin.TOP_LEFT:
            # (0,0) at top-left, work area extends positive X, negative Y
            x_min, x_max = 0.0, size['x']
            y_min, y_max = -size['y'], 0.0

        elif self.machine_origin == MachineOrigin.TOP_RIGHT:
            # (0,0) at top-right, work area extends negative X and Y
            x_min, x_max = -size['x'], 0.0
            y_min, y_max = -size['y'], 0.0

        return {
            'x_min': x_min, 'x_max': x_max,
            'y_min': y_min, 'y_max': y_max,
            'z_min': z_min, 'z_max': z_max
        }

    def is_coordinate_in_bounds(self, x: float, y: float, z: float) -> bool:
        """Check if coordinates are within machine bounds"""
        bounds = self.machine_bounds
        return (bounds['x_min'] <= x <= bounds['x_max'] and
                bounds['y_min'] <= y <= bounds['y_max'] and
                bounds['z_min'] <= z <= bounds['z_max'])

    def get_safe_coordinates(self, x: float, y: float, z: float) -> Dict[str, float]:
        """Clamp coordinates to safe machine bounds"""
        bounds = self.machine_bounds

        safe_x = max(bounds['x_min'], min(bounds['x_max'], x))
        safe_y = max(bounds['y_min'], min(bounds['y_max'], y))
        safe_z = max(bounds['z_min'], min(bounds['z_max'], z))

        return {'x': safe_x, 'y': safe_y, 'z': safe_z}

    def get_origin_description(self) -> str:
        """Get human-readable description of the origin configuration"""
        descriptions = {
            MachineOrigin.BOTTOM_LEFT: "Bottom-Left (0,0) - Traditional CNC",
            MachineOrigin.BOTTOM_RIGHT: "Bottom-Right (0,0)",
            MachineOrigin.TOP_LEFT: "Top-Left (0,0)",
            MachineOrigin.TOP_RIGHT: "Top-Right (0,0)"
        }
        return descriptions.get(self.machine_origin, "Unknown origin")

    def get_coordinate_system_info(self) -> Dict[str, Any]:
        """Get comprehensive coordinate system information"""
        bounds = self.machine_bounds
        homing = self.homing_position

        return {
            'origin': {
                'position': self.machine_origin.value,
                'description': self.get_origin_description(),
                'coordinates': (0.0, 0.0)  # Origin is always at (0,0) by definition
            },
            'homing': {
                'position': f"({homing['x']:.0f}, {homing['y']:.0f}, {homing['z']:.0f})",
                'coordinates': homing.copy(),
                'description': "Where machine moves when homing"
            },
            'work_area': {
                'bounds': bounds.copy(),
                'size': self.machine_size.copy(),
                'description': f"X({bounds['x_min']:.0f} to {bounds['x_max']:.0f}) Y({bounds['y_min']:.0f} to {bounds['y_max']:.0f})"
            }
        }

    def validate_configuration(self) -> Dict[str, Any]:
        """Validate hardware configuration"""
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
        total_size = max(self.machine_size['x'], self.machine_size['y'])
        if abs(offset['x']) > total_size or abs(offset['y']) > total_size:
            warnings.append("Camera offset is larger than machine size")

        # Check if homing position is reachable
        homing = self.homing_position
        if not self.is_coordinate_in_bounds(homing['x'], homing['y'], homing['z']):
            warnings.append("Homing position is outside machine bounds")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'configuration': {
                'machine_size': self.machine_size,
                'origin': self.machine_origin.value,
                'bounds': self.machine_bounds,
                'homing_position': self.homing_position,
                'camera_offset': self.camera_offset,
                'coordinate_system_info': self.get_coordinate_system_info()
            }
        }

    def get_status_summary(self) -> Dict[str, Any]:
        """Get compact status summary"""
        coord_info = self.get_coordinate_system_info()

        return {
            'machine_size': self.machine_size,
            'origin': {
                'name': self.machine_origin.value,
                'description': self.get_origin_description()
            },
            'homing_position': self.homing_position,
            'camera_offset': self.camera_offset,
            'has_camera': self.has_camera,
            'bounds': self.machine_bounds,
            'coordinate_system': coord_info,
            'is_valid': self.validate_configuration()['valid']
        }
