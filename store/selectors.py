# store/selectors.py
"""
Selector functions for efficient state access
Memoized selectors for expensive computations
"""

from typing import Tuple, List, Optional, Dict
from .state import ApplicationState


class Selectors:
    """Collection of selector functions for accessing state"""

    # Camera selectors
    @staticmethod
    def is_camera_connected(state: ApplicationState) -> bool:
        return state.camera.connected

    @staticmethod
    def get_camera_resolution(state: ApplicationState) -> Tuple[int, int]:
        return state.camera.resolution

    @staticmethod
    def has_camera_calibration(state: ApplicationState) -> bool:
        return state.camera.calibration_file is not None

    @staticmethod
    def get_current_frame(state: ApplicationState):
        return state.camera.current_frame

    # Machine selectors
    @staticmethod
    def is_machine_connected(state: ApplicationState) -> bool:
        return state.machine.connected

    @staticmethod
    def get_machine_position(state: ApplicationState) -> Tuple[float, float, float]:
        return state.machine.position

    @staticmethod
    def get_machine_status(state: ApplicationState) -> str:
        return state.machine.status

    @staticmethod
    def get_work_offset(state: ApplicationState) -> Tuple[float, float, float]:
        return state.machine.work_offset

    # Registration selectors
    @staticmethod
    def is_registered(state: ApplicationState) -> bool:
        return state.registration.is_registered

    @staticmethod
    def get_calibration_point_count(state: ApplicationState) -> int:
        return len(state.registration.calibration_points)

    @staticmethod
    def get_registration_error(state: ApplicationState) -> Optional[float]:
        return state.registration.registration_error

    # Routes selectors
    @staticmethod
    def has_routes(state: ApplicationState) -> bool:
        return len(state.routes.routes) > 0

    @staticmethod
    def get_route_count(state: ApplicationState) -> int:
        return len(state.routes.routes)

    @staticmethod
    def get_total_points(state: ApplicationState) -> int:
        return state.routes.point_count

    # Complex selectors combining multiple state pieces
    @staticmethod
    def can_capture_calibration_point(state: ApplicationState) -> bool:
        """Can capture calibration point if camera connected and has frame"""
        return (state.camera.connected and
                state.machine.connected and
                state.camera.current_frame is not None)

    @staticmethod
    def can_set_work_offset(state: ApplicationState) -> bool:
        """Can set work offset if registered and machine connected"""
        return (state.registration.is_registered and
                state.machine.connected)

    @staticmethod
    def can_transform_routes(state: ApplicationState) -> bool:
        """Can transform routes if have routes and registration"""
        return (len(state.routes.routes) > 0 and
                state.registration.is_registered)

    @staticmethod
    def get_connection_status(state: ApplicationState) -> Dict[str, bool]:
        """Get overall connection status"""
        return {
            'camera': state.camera.connected,
            'machine': state.machine.connected,
            'registered': state.registration.is_registered
        }

    @staticmethod
    def get_system_ready(state: ApplicationState) -> bool:
        """System is ready for operation"""
        return (state.camera.connected and
                state.machine.connected and
                state.registration.is_registered)