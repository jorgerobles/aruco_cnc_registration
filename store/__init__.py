# store/__init__.py
"""
Store Module - Redux-like state management for the application
"""

from .state import *
from .actions import *
from .reducers import *
from .store import *
from .selectors import *
from .middleware import *

__all__ = [
    # State classes
    'MachineOrigin',
    'CameraState',
    'MachineState',
    'HardwareConfig',
    'CalibrationPoint',
    'RegistrationState',
    'RoutesState',
    'ConfigurationState',
    'UIState',
    'SystemState',
    'ApplicationState',

    # Action types and creators
    'ActionType',
    'Action',
    'CameraActions',
    'MachineActions',
    'RegistrationActions',
    'RoutesActions',
    'UIActions',

    # Reducers
    'camera_reducer',
    'machine_reducer',
    'registration_reducer',
    'routes_reducer',
    'ui_reducer',
    'root_reducer',

    # Selectors
    'Selectors',

    # Store
    'ApplicationStore',
    'get_store',
    'initialize_store',

    # Middleware
    'DEFAULT_MIDDLEWARE',
    'DEVELOPMENT_MIDDLEWARE',
    'PRODUCTION_MIDDLEWARE',
    'DEBUG_MIDDLEWARE',
]