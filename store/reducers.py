# store/reducers.py
"""
Pure reducer functions for state updates
Each reducer handles a specific slice of state
"""
import time

from .actions import Action, ActionType
from .state import (
    ApplicationState, CameraState, MachineState, RegistrationState, RoutesState, UIState, CalibrationPoint
)


def camera_reducer(state: CameraState, action: Action) -> CameraState:
    """Reducer for camera state"""
    if action.type == ActionType.CAMERA_CONNECTION_CHANGED:
        return CameraState(
            connected=action.payload['connected'],
            camera_id=action.payload['camera_id'],
            resolution=state.resolution,
            calibration_file=state.calibration_file,
            current_frame=state.current_frame,
            marker_detection=state.marker_detection,
            fov_data=state.fov_data
        )


    elif action.type == ActionType.CAMERA_FRAME_UPDATED:
        frame = action.payload['frame']
        frame_info = {
            'shape': frame.shape,
            'timestamp': time.time(),
            'has_frame': True
        } if frame is not None else None
        return CameraState(
            connected=state.connected,
            camera_id=state.camera_id,
            resolution=state.resolution,
            calibration_file=state.calibration_file,
            current_frame=frame_info,  # ← Store metadata, not the array
            marker_detection=action.payload.get('marker_data'),
            fov_data=state.fov_data
        )

    elif action.type == ActionType.CAMERA_CALIBRATION_LOADED:
        if action.payload['success']:
            return CameraState(
                connected=state.connected,
                camera_id=state.camera_id,
                resolution=state.resolution,
                calibration_file=action.payload['file_path'],
                current_frame=state.current_frame,
                marker_detection=state.marker_detection,
                fov_data=state.fov_data
            )

    return state


def machine_reducer(state: MachineState, action: Action) -> MachineState:
    """Reducer for machine state"""
    if action.type == ActionType.MACHINE_CONNECTION_CHANGED:
        return MachineState(
            connected=action.payload['connected'],
            port=action.payload['port'],
            baudrate=action.payload['baudrate'],
            position=state.position,
            status=state.status,
            homing_complete=state.homing_complete,
            work_offset=state.work_offset
        )

    elif action.type == ActionType.MACHINE_POSITION_UPDATED:
        return MachineState(
            connected=state.connected,
            port=state.port,
            baudrate=state.baudrate,
            position=action.payload['position'],
            status=state.status,
            homing_complete=state.homing_complete,
            work_offset=state.work_offset
        )

    elif action.type == ActionType.MACHINE_STATUS_UPDATED:
        return MachineState(
            connected=state.connected,
            port=state.port,
            baudrate=state.baudrate,
            position=state.position,
            status=action.payload['status'],
            homing_complete=state.homing_complete,
            work_offset=state.work_offset
        )

    elif action.type == ActionType.MACHINE_WORK_OFFSET_SET:
        return MachineState(
            connected=state.connected,
            port=state.port,
            baudrate=state.baudrate,
            position=state.position,
            status=state.status,
            homing_complete=state.homing_complete,
            work_offset=action.payload['offset']
        )

    return state


def registration_reducer(state: RegistrationState, action: Action) -> RegistrationState:
    """Reducer for registration state"""
    if action.type == ActionType.REGISTRATION_POINT_ADDED:
        new_point = CalibrationPoint(
            machine_pos=action.payload['machine_pos'],
            camera_pos=action.payload['camera_pos'],
            timestamp=action.payload['timestamp']
        )
        return RegistrationState(
            calibration_points=state.calibration_points + [new_point],
            transformation_matrix=state.transformation_matrix,
            is_registered=state.is_registered,
            registration_error=state.registration_error
        )

    elif action.type == ActionType.REGISTRATION_POINT_REMOVED:
        index = action.payload['index']
        if 0 <= index < len(state.calibration_points):
            new_points = (state.calibration_points[:index] +
                          state.calibration_points[index + 1:])
            return RegistrationState(
                calibration_points=new_points,
                transformation_matrix=state.transformation_matrix,
                is_registered=len(new_points) >= 3,  # Need at least 3 points
                registration_error=state.registration_error
            )

    elif action.type == ActionType.REGISTRATION_CALCULATED:
        return RegistrationState(
            calibration_points=state.calibration_points,
            transformation_matrix=action.payload['transformation_matrix'],
            is_registered=True,
            registration_error=action.payload['error']
        )

    elif action.type == ActionType.REGISTRATION_CLEARED:
        return RegistrationState()

    return state


def routes_reducer(state: RoutesState, action: Action) -> RoutesState:
    """Reducer for routes state"""
    if action.type == ActionType.ROUTES_LOADED:
        return RoutesState(
            routes=action.payload['routes'],
            transformed_routes=state.transformed_routes,
            bounds=action.payload.get('bounds'),
            current_file=action.payload['file_path'],
            total_length=action.payload.get('total_length', 0.0),
            point_count=action.payload.get('point_count', 0)
        )

    elif action.type == ActionType.ROUTES_TRANSFORMED:
        return RoutesState(
            routes=state.routes,
            transformed_routes=action.payload['transformed_routes'],
            bounds=state.bounds,
            current_file=state.current_file,
            total_length=state.total_length,
            point_count=state.point_count
        )

    elif action.type == ActionType.ROUTES_CLEARED:
        return RoutesState()

    return state


def ui_reducer(state: UIState, action: Action) -> UIState:
    """Reducer for UI state"""
    if action.type == ActionType.UI_STATUS_MESSAGE_SET:
        return UIState(
            machine_area_visible=state.machine_area_visible,
            debug_panel_expanded=state.debug_panel_expanded,
            status_message=action.payload['message'],
            current_tab=state.current_tab
        )

    elif action.type == ActionType.UI_MACHINE_AREA_TOGGLED:
        return UIState(
            machine_area_visible=action.payload['visible'],
            debug_panel_expanded=state.debug_panel_expanded,
            status_message=state.status_message,
            current_tab=state.current_tab
        )

    return state


def root_reducer(state: ApplicationState, action: Action) -> ApplicationState:
    """Root reducer that combines all sub-reducers"""
    return ApplicationState(
        camera=camera_reducer(state.camera, action),
        machine=machine_reducer(state.machine, action),
        hardware=state.hardware,  # Hardware config rarely changes
        registration=registration_reducer(state.registration, action),
        routes=routes_reducer(state.routes, action),
        config=state.config,  # Config handled separately
        ui=ui_reducer(state.ui, action),
        system=state.system  # System state handled separately
    )
