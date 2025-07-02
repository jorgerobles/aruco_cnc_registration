
# Predefined event types - Updated to include DEBUG_INFO
class CameraEvents:
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    CALIBRATION_LOADED = "camera.calibration_loaded"


class GRBLEvents:
    CONNECTED = "grbl.connected"
    DISCONNECTED = "grbl.disconnected"
    POSITION_CHANGED = "grbl.position_changed"
    STATUS_CHANGED = "grbl.status_changed"
    ERROR = "grbl.error"
    COMMAND_SENT = "grbl.command_sent"
    RESPONSE_RECEIVED = "grbl.response_received"
    DEBUG_INFO = "grbl.debug_info"  # NEW: For GRBL internal debug messages


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