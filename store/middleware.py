# store/middleware.py
"""
Middleware functions for the store
Logging, persistence, and debugging middleware
"""

import time
import json
from typing import Optional
from .actions import Action, ActionType
from .state import ApplicationState


def logging_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """Middleware for logging all actions"""
    print(f"[{time.strftime('%H:%M:%S')}] Action: {action.type.name}")
    if action.payload:
        # Only log simple payload data to avoid noise
        simple_payload = {}
        for key, value in action.payload.items():
            if isinstance(value, (str, int, float, bool, tuple)):
                simple_payload[key] = value
            else:
                simple_payload[key] = f"<{type(value).__name__}>"
        if simple_payload:
            print(f"                      Payload: {simple_payload}")
    return action


def performance_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """Middleware for tracking action performance"""
    start_time = time.time()

    # Let action proceed, we'll measure in the next middleware or reducer
    # Store timing info in action meta
    if action.meta is None:
        action = Action(action.type, action.payload, {})

    action.meta['start_time'] = start_time
    return action


def error_handling_middleware(action: Action, state: ApplicationState) -> Optional[Action]:
    """Middleware for error handling and validation"""
    try:
        # Basic action validation
        if not isinstance(action.type, ActionType):
            print(f"Warning: Invalid action type: {action.type}")
            return None

        # Validate specific action payloads
        if action.type == ActionType.CAMERA_CONNECTION_CHANGED:
            if 'connected' not in action.payload:
                print("Error: CAMERA_CONNECTION_CHANGED missing 'connected' in payload")
                return None

        return action

    except Exception as e:
        print(f"Error in middleware: {e}")
        return None


# Default middleware stack
DEFAULT_MIDDLEWARE = [
    error_handling_middleware,
    logging_middleware,
    performance_middleware,
]