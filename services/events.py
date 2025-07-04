
# Predefined event types - Updated to include DEBUG_INFO
class CameraEvents:
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    CALIBRATION_LOADED = "camera.calibration_loaded"


class GRBLEvents:
    """GRBL event type constants"""

    # Connection events
    CONNECTED = "grbl.connected"
    DISCONNECTED = "grbl.disconnected"
    CONNECTION_LOST = "grbl.connection_lost"

    # Command events
    COMMAND_SENT = "grbl.command_sent"
    COMMAND_COMPLETED = "grbl.command_completed"
    COMMAND_FAILED = "grbl.command_failed"
    COMMAND_TIMEOUT = "grbl.command_timeout"

    # Response events
    RESPONSE_RECEIVED = "grbl.response_received"

    # Status events
    STATUS_CHANGED = "grbl.status_changed"
    POSITION_CHANGED = "grbl.position_changed"

    # Error events
    ERROR = "grbl.error"
    WARNING = "grbl.warning"

    # Debug events
    DEBUG_INFO = "grbl.debug_info"

    # System events
    ALARM = "grbl.alarm"
    RESET = "grbl.reset"
    EMERGENCY_STOP = "grbl.emergency_stop"

    # Settings events
    SETTINGS_CHANGED = "grbl.settings_changed"
    WORK_OFFSET_CHANGED = "grbl.work_offset_changed"

class RegistrationEvents:
    POINT_ADDED = "registration.point_added"
    POINT_REMOVED = "registration.point_removed"
    POINT_TRANSFORMED = "registration.point_transformed"
    BATCH_TRANSFORMED = "registration.batch_transformed"
    COMPUTED = "registration.computed"
    AUTO_COMPUTED = "registration.auto_computed"
    CLEARED = "registration.cleared"
    RESET = "registration.reset"
    SAVED = "registration.saved"
    LOADED = "registration.loaded"
    VALIDATION_PASSED = "registration.validation_passed"
    VALIDATION_FAILED = "registration.validation_failed"
    ERROR = "registration.error"
    DEBUG_INFO = "registration.debug_info"  # New event for debug information


class ApplicationEvents:
    STARTUP = "app.startup"
    SHUTDOWN = "app.shutdown"
    MODE_CHANGED = "app.mode_changed"
    ERROR = "app.error"