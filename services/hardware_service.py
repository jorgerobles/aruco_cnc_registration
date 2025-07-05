"""
Minimal Hardware Service - KISS approach
Just stores basic hardware info and emits events
"""

from services.event_broker import event_aware


class HardwareEvents:
    """Hardware events"""
    CAMERA_OFFSET_UPDATED = "hardware.camera_offset_updated"
    MACHINE_SIZE_UPDATED = "hardware.machine_size_updated"


@event_aware()
class HardwareService:
    """Minimal hardware service - just stores and emits events"""

    def __init__(self, machine_size=(450, 450, 80), has_camera=True, camera_offset=(-45, 0, 0)):
        # Basic hardware info
        self.machine_size = {'x': machine_size[0], 'y': machine_size[1], 'z': machine_size[2]}  # mm
        self.has_camera = has_camera
        self.camera_offset = {'x': camera_offset[0], 'y': camera_offset[1], 'z': camera_offset[2]}  # mm

    def set_camera_offset(self, x: float, y: float, z: float):
        """Set camera offset and emit event"""
        self.camera_offset = {'x': x, 'y': y, 'z': z}

        # Emit event to whoever is listening
        self.emit(HardwareEvents.CAMERA_OFFSET_UPDATED, {
            'x': x, 'y': y, 'z': z,
            'offset': self.camera_offset
        })

    def get_camera_offset(self) -> dict:
        """Get camera offset"""
        return self.camera_offset.copy()

    def set_machine_size(self, x: float, y: float, z: float):
        """Set machine size and emit event"""
        self.machine_size = {'x': x, 'y': y, 'z': z}

        self.emit(HardwareEvents.MACHINE_SIZE_UPDATED, {
            'x': x, 'y': y, 'z': z,
            'size': self.machine_size
        })

    def get_machine_size(self) -> dict:
        """Get machine size"""
        return self.machine_size.copy()

    def set_has_camera(self, has_camera: bool):
        """Set camera availability"""
        self.has_camera = has_camera
