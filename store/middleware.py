# store/middleware.py
"""
Store Middleware for Debugging, Logging, and Performance Monitoring
Provides middleware functions for the ApplicationStore
"""

import time
import json
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from .actions import Action, ActionType
from .state import ApplicationState


def logging_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """
    Middleware for logging all actions and state changes
    Useful for debugging and monitoring
    """
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    # Log action details
    print(f"[{timestamp}] ACTION: {action.type.name}")

    if action.payload:
        # Only log relevant payload data (avoid logging large frame data)
        if action.type == ActionType.CAMERA_FRAME_UPDATED:
            # Safe marker data check
            marker_data = action.payload.get('marker_data')
            marker_data_present = False

            if marker_data is not None:
                if isinstance(marker_data, dict):
                    marker_data_present = True
                elif hasattr(marker_data, '__len__'):
                    marker_data_present = len(marker_data) > 0
                else:
                    marker_data_present = bool(marker_data)

            payload_info = {
                'frame_shape': getattr(action.payload.get('frame'), 'shape', None) if action.payload.get(
                    'frame') is not None else None,
                'marker_data': marker_data_present  # Now safely boolean
            }
            print(f"  Payload: {payload_info}")
        else:
            print(f"  Payload: {action.payload}")

    if action.meta:
        print(f"  Meta: {action.meta}")

    return action  # Pass action through unchanged


def performance_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """
    Middleware for performance monitoring
    Tracks action processing times and frequency
    """
    if not hasattr(performance_middleware, '_stats'):
        performance_middleware._stats = {
            'action_counts': {},
            'processing_times': {},
            'start_time': time.time()
        }

    stats = performance_middleware._stats
    action_name = action.type.name

    # Count actions
    stats['action_counts'][action_name] = stats['action_counts'].get(action_name, 0) + 1

    # Track processing time
    start_time = time.perf_counter()

    # Store start time in action meta for end measurement
    if not action.meta:
        action.meta = {}
    action.meta['_perf_start'] = start_time

    # Log performance stats every 100 actions
    total_actions = sum(stats['action_counts'].values())
    if total_actions % 100 == 0:
        print(f"\n[PERFORMANCE] Action Statistics (last 100 actions):")
        for action_type, count in stats['action_counts'].items():
            print(f"  {action_type}: {count}")

        # Reset stats
        stats['action_counts'] = {}

    return action


def camera_frame_throttling_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """
    Middleware to throttle camera frame updates for performance
    Skips frames if they're coming too fast
    """
    if action.type != ActionType.CAMERA_FRAME_UPDATED:
        return action

    if not hasattr(camera_frame_throttling_middleware, '_last_frame_time'):
        camera_frame_throttling_middleware._last_frame_time = 0

    current_time = time.time()
    time_since_last = current_time - camera_frame_throttling_middleware._last_frame_time

    # Throttle to max 15 FPS (skip if less than 66ms since last frame)
    min_interval = 1.0 / 15.0  # 15 FPS

    if time_since_last < min_interval:
        return None  # Block this action

    camera_frame_throttling_middleware._last_frame_time = current_time
    return action


def error_handling_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """
    Middleware for error handling and recovery
    Catches and logs errors, provides fallback behavior
    """
    try:
        # Validate action structure
        if not hasattr(action, 'type') or not isinstance(action.type, ActionType):
            print(f"[ERROR] Invalid action type: {action}")
            return None

        # Check for specific error conditions
        if action.type == ActionType.CAMERA_CONNECTION_CHANGED:
            payload = action.payload
            if not isinstance(payload, dict) or 'connected' not in payload:
                print(f"[ERROR] Invalid camera connection payload: {payload}")
                return None

        return action

    except Exception as e:
        print(f"[ERROR] Error in middleware processing action {action}: {e}")
        return None


def state_validation_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """
    Middleware for validating state transitions
    Ensures state changes are logical and valid
    """
    # Skip validation for frame updates (too frequent)
    if action.type == ActionType.CAMERA_FRAME_UPDATED:
        return action

    try:
        # Validate camera state transitions
        if action.type == ActionType.CAMERA_CONNECTION_CHANGED:
            connected = action.payload['connected']
            camera_id = action.payload['camera_id']

            # Validate camera ID
            if not isinstance(camera_id, int) or camera_id < 0:
                print(f"[VALIDATION] Invalid camera ID: {camera_id}")
                return None

            # Validate connection state
            if not isinstance(connected, bool):
                print(f"[VALIDATION] Invalid connection state: {connected}")
                return None

        elif action.type == ActionType.CAMERA_CALIBRATION_LOADED:
            success = action.payload['success']
            file_path = action.payload.get('file_path')

            if not isinstance(success, bool):
                print(f"[VALIDATION] Invalid calibration success flag: {success}")
                return None

            if success and (not file_path or not isinstance(file_path, str)):
                print(f"[VALIDATION] Calibration success but invalid file path: {file_path}")
                return None

        return action

    except Exception as e:
        print(f"[VALIDATION] Error validating action {action}: {e}")
        return action  # Pass through on validation errors


def debug_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """
    Middleware for detailed debugging information
    Only active when DEBUG environment variable is set
    """
    import os

    if not os.environ.get('DEBUG_STORE'):
        return action

    print(f"\n[DEBUG] Action Processing:")
    print(f"  Type: {action.type.name}")
    print(f"  Payload: {_safe_serialize(action.payload)}")
    print(f"  Meta: {action.meta}")

    # Log relevant state before action
    if action.type in [ActionType.CAMERA_CONNECTION_CHANGED, ActionType.CAMERA_CALIBRATION_LOADED]:
        print(f"  Current Camera State:")
        print(f"    Connected: {state.camera.connected}")
        print(f"    Camera ID: {state.camera.camera_id}")
        print(f"    Calibration: {state.camera.calibration_file}")

    return action


def _safe_serialize(obj: Any) -> str:
    """Safely serialize objects for logging"""
    try:
        if obj is None:
            return "None"
        elif hasattr(obj, 'shape'):  # NumPy array
            return f"Array{obj.shape}"
        elif isinstance(obj, dict):
            safe_dict = {}
            for k, v in obj.items():
                if hasattr(v, 'shape'):
                    safe_dict[k] = f"Array{v.shape}"
                elif isinstance(v, (str, int, float, bool, type(None))):
                    safe_dict[k] = v
                else:
                    safe_dict[k] = str(type(v))
            return str(safe_dict)
        elif isinstance(obj, (str, int, float, bool)):
            return str(obj)
        else:
            return str(type(obj))
    except Exception:
        return "<serialization error>"


class ActionLogger:
    """
    Advanced action logger with file output and filtering
    """

    def __init__(self, log_file: Optional[str] = None, filter_actions: Optional[list] = None):
        self.log_file = log_file
        self.filter_actions = filter_actions or []
        self.session_start = datetime.now()

        if self.log_file:
            with open(self.log_file, 'w') as f:
                f.write(f"Store Action Log - Session started: {self.session_start}\n")
                f.write("=" * 50 + "\n")

    def __call__(self, action: Action, state: ApplicationState) -> Optional[Action]:
        """Middleware function"""
        # Skip filtered actions
        if action.type in self.filter_actions:
            return action

        timestamp = datetime.now()
        log_entry = {
            'timestamp': timestamp.isoformat(),
            'action_type': action.type.name,
            'payload': _safe_serialize(action.payload),
            'meta': action.meta
        }

        # Log to file if specified
        if self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(f"{timestamp.strftime('%H:%M:%S.%f')[:-3]} | {action.type.name}")
                    if action.payload:
                        f.write(f" | {_safe_serialize(action.payload)}")
                    f.write("\n")
            except Exception as e:
                print(f"[LOG] Error writing to log file: {e}")

        return action


def create_conditional_middleware(condition_func: Callable[[Action, ApplicationState], bool],
                                  middleware_func: Callable[[Action, ApplicationState], Optional[Action]]):
    """
    Create middleware that only applies when condition is met
    """

    def conditional_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
        if condition_func(action, state):
            return middleware_func(action, state)
        return action

    return conditional_middleware


# === PREDEFINED MIDDLEWARE CONFIGURATIONS ===

# Development middleware stack
DEVELOPMENT_MIDDLEWARE = [
    error_handling_middleware,
    state_validation_middleware,
    debug_middleware,
    performance_middleware,
    logging_middleware
]

# Production middleware stack (minimal logging)
PRODUCTION_MIDDLEWARE = [
    error_handling_middleware,
    camera_frame_throttling_middleware
]

# Debug middleware stack (extensive logging)
DEBUG_MIDDLEWARE = [
    error_handling_middleware,
    state_validation_middleware,
    debug_middleware,
    performance_middleware,
    ActionLogger("store_actions.log", filter_actions=[ActionType.CAMERA_FRAME_UPDATED]),
    logging_middleware
]

# Performance middleware stack
PERFORMANCE_MIDDLEWARE = [
    error_handling_middleware,
    camera_frame_throttling_middleware,
    performance_middleware
]

# Default middleware for normal operation
DEFAULT_MIDDLEWARE = [
    error_handling_middleware,
    camera_frame_throttling_middleware,
    logging_middleware
]


# === MIDDLEWARE UTILITIES ===

def create_timing_middleware(action_types: list = None):
    """Create middleware that times specific action types"""
    target_actions = action_types or [ActionType.CAMERA_CONNECTION_CHANGED, ActionType.CAMERA_CALIBRATION_LOADED]

    def timing_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
        if action.type in target_actions:
            start_time = time.perf_counter()
            # Add timing info to meta
            if not action.meta:
                action.meta = {}
            action.meta['timing_start'] = start_time

            # Log timing info
            print(f"[TIMING] Started processing {action.type.name}")

        return action

    return timing_middleware


def create_filtering_middleware(blocked_actions: list):
    """Create middleware that blocks specific action types"""

    def filtering_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
        if action.type in blocked_actions:
            print(f"[FILTER] Blocked action: {action.type.name}")
            return None
        return action

    return filtering_middleware


# === EXAMPLE USAGE ===

"""
Example of how to use middleware with the store:

# Basic setup
store = ApplicationStore()
store.add_middleware(logging_middleware)
store.add_middleware(error_handling_middleware)

# Development setup
store = ApplicationStore()
for middleware in DEVELOPMENT_MIDDLEWARE:
    store.add_middleware(middleware)

# Custom conditional middleware
condition = lambda action, state: action.type == ActionType.CAMERA_CONNECTION_CHANGED
custom_middleware = create_conditional_middleware(condition, debug_middleware)
store.add_middleware(custom_middleware)

# Timing specific actions
timing_middleware = create_timing_middleware([ActionType.CAMERA_CONNECTION_CHANGED])
store.add_middleware(timing_middleware)
"""