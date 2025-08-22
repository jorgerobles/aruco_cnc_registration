# store/actions.py
"""
Action Types and Action Creators
Following Redux patterns with typed actions
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Optional, List, Tuple


class ActionType(Enum):
    # Camera Actions
    CAMERA_CONNECT_REQUESTED = auto()
    CAMERA_CONNECTION_CHANGED = auto()
    CAMERA_FRAME_UPDATED = auto()
    CAMERA_CALIBRATION_LOADED = auto()
    CAMERA_CONFIG_UPDATED = auto()

    # Machine Actions
    MACHINE_CONNECT_REQUESTED = auto()
    MACHINE_CONNECTION_CHANGED = auto()
    MACHINE_POSITION_UPDATED = auto()
    MACHINE_STATUS_UPDATED = auto()
    MACHINE_HOMING_COMPLETED = auto()
    MACHINE_WORK_OFFSET_SET = auto()

    # Hardware Actions
    HARDWARE_CONFIG_UPDATED = auto()

    # Registration Actions
    REGISTRATION_POINT_ADDED = auto()
    REGISTRATION_POINT_REMOVED = auto()
    REGISTRATION_CALCULATED = auto()
    REGISTRATION_CLEARED = auto()

    # Routes Actions
    ROUTES_LOADED = auto()
    ROUTES_TRANSFORMED = auto()
    ROUTES_CLEARED = auto()

    # Configuration Actions
    CONFIG_LOADED = auto()
    CONFIG_SAVED = auto()
    CONFIG_UPDATED = auto()

    # UI Actions
    UI_STATUS_MESSAGE_SET = auto()
    UI_MACHINE_AREA_TOGGLED = auto()
    UI_TAB_CHANGED = auto()

    # System Actions
    SYSTEM_STARTUP_COMPLETED = auto()
    SYSTEM_ERROR_OCCURRED = auto()


@dataclass(frozen=True)
class Action:
    """Immutable action for state updates"""
    type: ActionType
    payload: Any = None
    meta: Dict = None

    def __post_init__(self):
        # Ensure meta is never None
        if self.meta is None:
            object.__setattr__(self, 'meta', {})

# Action Creators
class CameraActions:
    """Action creators for camera operations"""

    @staticmethod
    def connect_requested(camera_id: int) -> Action:
        return Action(
            ActionType.CAMERA_CONNECT_REQUESTED,
            {'camera_id': camera_id}
        )

    @staticmethod
    def connection_changed(connected: bool, camera_id: int = 0) -> Action:
        return Action(
            ActionType.CAMERA_CONNECTION_CHANGED,
            {'connected': connected, 'camera_id': camera_id}
        )

    @staticmethod
    def frame_updated(frame: Any, marker_data: Optional[Dict] = None) -> Action:
        return Action(
            ActionType.CAMERA_FRAME_UPDATED,
            {'frame': frame, 'marker_data': marker_data}
        )

    @staticmethod
    def calibration_loaded(success: bool, file_path: Optional[str] = None) -> Action:
        return Action(
            ActionType.CAMERA_CALIBRATION_LOADED,
            {'success': success, 'file_path': file_path}
        )


class MachineActions:
    """Action creators for machine operations"""

    @staticmethod
    def connect_requested(port: str, baudrate: int = 115200) -> Action:
        return Action(
            ActionType.MACHINE_CONNECT_REQUESTED,
            {'port': port, 'baudrate': baudrate}
        )

    @staticmethod
    def connection_changed(connected: bool, port: str = "", baudrate: int = 115200) -> Action:
        return Action(
            ActionType.MACHINE_CONNECTION_CHANGED,
            {'connected': connected, 'port': port, 'baudrate': baudrate}
        )

    @staticmethod
    def position_updated(position: Tuple[float, float, float]) -> Action:
        return Action(
            ActionType.MACHINE_POSITION_UPDATED,
            {'position': position}
        )

    @staticmethod
    def status_updated(status: str) -> Action:
        return Action(
            ActionType.MACHINE_STATUS_UPDATED,
            {'status': status}
        )

    @staticmethod
    def work_offset_set(offset: Tuple[float, float, float]) -> Action:
        return Action(
            ActionType.MACHINE_WORK_OFFSET_SET,
            {'offset': offset}
        )


class RegistrationActions:
    """Action creators for registration operations"""

    @staticmethod
    def point_added(machine_pos: Tuple[float, float, float],
                    camera_pos: Tuple[float, float],
                    timestamp: float) -> Action:
        return Action(
            ActionType.REGISTRATION_POINT_ADDED,
            {
                'machine_pos': machine_pos,
                'camera_pos': camera_pos,
                'timestamp': timestamp
            }
        )

    @staticmethod
    def point_removed(index: int) -> Action:
        return Action(
            ActionType.REGISTRATION_POINT_REMOVED,
            {'index': index}
        )

    @staticmethod
    def calculated(transformation_matrix: Any, error: float) -> Action:
        return Action(
            ActionType.REGISTRATION_CALCULATED,
            {'transformation_matrix': transformation_matrix, 'error': error}
        )

    @staticmethod
    def cleared() -> Action:
        return Action(ActionType.REGISTRATION_CLEARED)


class RoutesActions:
    """Action creators for routes operations"""

    @staticmethod
    def loaded(routes: List[List[Tuple[float, float]]],
               file_path: str,
               bounds: Optional[Dict] = None) -> Action:
        return Action(
            ActionType.ROUTES_LOADED,
            {
                'routes': routes,
                'file_path': file_path,
                'bounds': bounds,
                'point_count': sum(len(route) for route in routes),
                'total_length': 0.0  # Calculate if needed
            }
        )

    @staticmethod
    def transformed(transformed_routes: List[List[Tuple[float, float]]]) -> Action:
        return Action(
            ActionType.ROUTES_TRANSFORMED,
            {'transformed_routes': transformed_routes}
        )

    @staticmethod
    def cleared() -> Action:
        return Action(ActionType.ROUTES_CLEARED)


class UIActions:
    """Action creators for UI operations"""

    @staticmethod
    def status_message_set(message: str) -> Action:
        return Action(
            ActionType.UI_STATUS_MESSAGE_SET,
            {'message': message}
        )

    @staticmethod
    def machine_area_toggled(visible: bool) -> Action:
        return Action(
            ActionType.UI_MACHINE_AREA_TOGGLED,
            {'visible': visible}
        )