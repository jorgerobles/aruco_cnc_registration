# services/configuration_service.py
"""
Updated Configuration Service with Store Integration Support
Works with both store-integrated and event-based services during transition
Provides immediate feedback and proper error handling
"""

from typing import Optional, Callable
from pathlib import Path

from services.configuration_manager import ConfigurationManager, ConfigurationEvents, ApplicationConfig
from services.hardware_service import HardwareService, MachineOrigin
from services.camera_manager import CameraManager  # Now store-integrated
from services.event_broker import event_aware, event_handler, EventPriority

# Store integration imports
from store.store import ApplicationStore
from store.actions import ActionType


class ConfigurationServiceEvents:
    """Events dispatched by configuration service"""
    APPLIED = "config_service.applied"
    APPLY_FAILED = "config_service.apply_failed"
    AUTO_SAVED = "config_service.auto_saved"


@event_aware()  # Keep for legacy event handling during transition
class ConfigurationService:
    """
    Updated Configuration Service with Store Integration Support
    Detects and works with both store-integrated and event-based services
    """

    def __init__(self,
                 hardware_service: HardwareService,
                 camera_manager: CameraManager,
                 store: Optional[ApplicationStore] = None,
                 logger: Optional[Callable] = None):
        self.hardware_service = hardware_service
        self.camera_manager = camera_manager
        self.store = store  # Optional store for future integration
        self.logger = logger

        self.config_manager = ConfigurationManager()
        self.auto_save_enabled = True
        self.current_config_file: Optional[str] = None

        # Detect if camera manager is store-integrated
        self._camera_is_store_integrated = hasattr(camera_manager, 'store') and camera_manager.store is not None

        if self._camera_is_store_integrated:
            self.log("Camera manager is store-integrated", "info")
        else:
            self.log("Camera manager is event-based (legacy)", "info")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[ConfigService] {message}", level)

    def load_and_apply_configuration(self, file_path: str) -> bool:
        """
        Load configuration from file and apply to all services
        Now provides immediate feedback and proper error handling
        """
        try:
            # Load configuration
            if not self.config_manager.load_configuration(file_path):
                self.emit(ConfigurationServiceEvents.APPLY_FAILED, {
                    'file_path': file_path,
                    'error': 'Failed to load configuration file'
                })
                return False

            config = self.config_manager.get_current_configuration()
            if config is None:
                self.emit(ConfigurationServiceEvents.APPLY_FAILED, {
                    'file_path': file_path,
                    'error': 'Configuration file is empty or invalid'
                })
                return False

            # Apply configuration to services with improved error handling
            success = True
            errors = []

            # Apply to hardware service
            try:
                self._apply_to_hardware_service(config)
                self.log("Hardware configuration applied successfully")
            except Exception as e:
                success = False
                errors.append(f"Hardware service: {e}")
                self.log(f"Failed to apply hardware configuration: {e}", "error")

            # Apply to camera manager with store-aware handling
            try:
                camera_success = self._apply_to_camera_manager(config)
                if camera_success:
                    self.log("Camera configuration applied successfully")
                else:
                    success = False
                    errors.append("Camera manager: Configuration application failed")
                    self.log("Failed to apply camera configuration", "error")
            except Exception as e:
                success = False
                errors.append(f"Camera manager: {e}")
                self.log(f"Exception applying camera configuration: {e}", "error")

            # Store current config file path if successful
            if success:
                self.current_config_file = file_path

                # Emit success event
                self.emit(ConfigurationServiceEvents.APPLIED, {
                    'config': config,
                    'file_path': file_path
                })

                self.log(f"Configuration loaded and applied: {file_path}")
                return True
            else:
                # Emit failure event with details
                self.emit(ConfigurationServiceEvents.APPLY_FAILED, {
                    'file_path': file_path,
                    'errors': errors
                })

                self.log(f"Configuration application failed: {'; '.join(errors)}", "error")
                return False

        except Exception as e:
            error_msg = f"Failed to load and apply configuration: {e}"
            self.log(error_msg, "error")

            self.emit(ConfigurationServiceEvents.APPLY_FAILED, {
                'file_path': file_path,
                'error': str(e)
            })
            return False

    def _apply_to_hardware_service(self, config: ApplicationConfig):
        """Apply hardware configuration with validation"""
        if not config.hardware:
            raise ValueError("No hardware configuration found")

        # Validate configuration values
        if config.hardware.machine_size_x <= 0 or config.hardware.machine_size_y <= 0:
            raise ValueError("Invalid machine size values")

        # Apply hardware settings
        self.hardware_service.update_machine_size(
            config.hardware.machine_size_x,
            config.hardware.machine_size_y,
            config.hardware.machine_size_z
        )

        self.hardware_service.update_camera_offset(
            config.hardware.camera_offset_x,
            config.hardware.camera_offset_y,
            config.hardware.camera_offset_z
        )

        # Convert string to enum if needed
        if isinstance(config.hardware.machine_origin, str):
            origin = MachineOrigin(config.hardware.machine_origin)
        else:
            origin = config.hardware.machine_origin

        self.hardware_service.set_machine_origin(origin)

        self.hardware_service.update_homing_position(
            config.hardware.homing_position_x,
            config.hardware.homing_position_y,
            config.hardware.homing_position_z
        )

    def _apply_to_camera_manager(self, config: ApplicationConfig) -> bool:
        """
        Apply camera configuration with store-aware handling
        Returns success status immediately
        """
        if not config.camera:
            return False

        success = True

        try:
            # Set camera ID (may require reconnection)
            if config.camera.camera_id != self.camera_manager.camera_id:
                if self._camera_is_store_integrated:
                    # Store-integrated version returns immediate result
                    id_success = self.camera_manager.set_camera_id(config.camera.camera_id)
                    if not id_success:
                        self.log(f"Failed to set camera ID to {config.camera.camera_id}", "error")
                        success = False
                else:
                    # Legacy version - set directly
                    self.camera_manager.set_camera_id(config.camera.camera_id)

            # Set resolution
            if hasattr(self.camera_manager, 'set_resolution'):
                if self._camera_is_store_integrated:
                    # Store-integrated version returns immediate result
                    res_success = self.camera_manager.set_resolution(
                        config.camera.resolution_width,
                        config.camera.resolution_height
                    )
                    if not res_success:
                        self.log("Failed to set camera resolution", "error")
                        success = False
                else:
                    # Legacy version - assume success
                    self.camera_manager.resolution = (
                        config.camera.resolution_width,
                        config.camera.resolution_height
                    )

            # Load calibration file if specified
            if config.camera.calibration_file and Path(config.camera.calibration_file).exists():
                if self._camera_is_store_integrated:
                    # Store-integrated version returns immediate result
                    calib_success = self.camera_manager.load_calibration(config.camera.calibration_file)
                    if not calib_success:
                        self.log(f"Failed to load calibration: {config.camera.calibration_file}", "error")
                        success = False
                else:
                    # Legacy version - call method (uses events for feedback)
                    self.camera_manager.load_calibration(config.camera.calibration_file)

            return success

        except Exception as e:
            self.log(f"Exception in camera configuration: {e}", "error")
            return False

    def save_current_configuration(self, file_path: str) -> bool:
        """Save current configuration with immediate feedback"""
        try:
            # Get current configuration
            current_config = self.config_manager.get_current_configuration()
            if current_config is None:
                self.log("No configuration to save", "error")
                return False

            # Update configuration with current service states
            self._update_config_from_services(current_config)

            # Save configuration
            success = self.config_manager.save_configuration(file_path, current_config)

            if success:
                self.current_config_file = file_path
                self.log(f"Configuration saved: {file_path}")
            else:
                self.log(f"Failed to save configuration: {file_path}", "error")

            return success

        except Exception as e:
            error_msg = f"Failed to save configuration: {e}"
            self.log(error_msg, "error")
            return False

    def _update_config_from_services(self, config: ApplicationConfig):
        """Update configuration object with current service states"""
        try:
            # Update camera configuration from camera manager
            if config.camera:
                config.camera.camera_id = self.camera_manager.camera_id
                config.camera.resolution_width = self.camera_manager.resolution[0]
                config.camera.resolution_height = self.camera_manager.resolution[1]

                # Get calibration info if available
                if self._camera_is_store_integrated and self.store:
                    camera_state = self.store.get_state().camera
                    if camera_state.calibration_file:
                        config.camera.calibration_file = camera_state.calibration_file

            # Update hardware configuration from hardware service
            if config.hardware:
                machine_size = self.hardware_service.get_machine_size()
                config.hardware.machine_size_x = machine_size['x']
                config.hardware.machine_size_y = machine_size['y']
                config.hardware.machine_size_z = machine_size['z']

                camera_offset = self.hardware_service.get_camera_offset()
                config.hardware.camera_offset_x = camera_offset['x']
                config.hardware.camera_offset_y = camera_offset['y']
                config.hardware.camera_offset_z = camera_offset['z']

                config.hardware.machine_origin = self.hardware_service.machine_origin.value

        except Exception as e:
            self.log(f"Error updating config from services: {e}", "error")

    def auto_save_configuration(self) -> bool:
        """Auto-save current configuration if enabled"""
        if not self.auto_save_enabled or not self.current_config_file:
            return False

        try:
            success = self.save_current_configuration(self.current_config_file)

            if success:
                self.emit(ConfigurationServiceEvents.AUTO_SAVED, {
                    'file_path': self.current_config_file
                })

            return success

        except Exception as e:
            self.log(f"Auto-save failed: {e}", "error")
            return False

    def create_default_configuration(self, file_path: str) -> bool:
        """Create and save a default configuration file"""
        try:
            success = self.config_manager.create_default_configuration_file(file_path)

            if success:
                self.log(f"Default configuration created: {file_path}")
                # Also apply the default configuration
                return self.load_and_apply_configuration(file_path)

            return False

        except Exception as e:
            error_msg = f"Failed to create default configuration: {e}"
            self.log(error_msg, "error")
            return False

    def update_camera_settings(self, **kwargs) -> bool:
        """Update camera configuration with immediate feedback"""
        try:
            success = True

            # Apply camera settings with store-aware handling
            for key, value in kwargs.items():
                if key == 'camera_id':
                    if self._camera_is_store_integrated:
                        id_success = self.camera_manager.set_camera_id(value)
                        if not id_success:
                            self.log(f"Failed to set camera ID to {value}", "error")
                            success = False
                    else:
                        self.camera_manager.set_camera_id(value)

                elif key in ['resolution_width', 'resolution_height']:
                    if 'resolution_width' in kwargs and 'resolution_height' in kwargs:
                        if self._camera_is_store_integrated:
                            res_success = self.camera_manager.set_resolution(
                                kwargs['resolution_width'],
                                kwargs['resolution_height']
                            )
                            if not res_success:
                                self.log("Failed to set camera resolution", "error")
                                success = False
                        else:
                            self.camera_manager.resolution = (
                                kwargs['resolution_width'],
                                kwargs['resolution_height']
                            )

                elif key == 'calibration_file':
                    if value and Path(value).exists():
                        if self._camera_is_store_integrated:
                            calib_success = self.camera_manager.load_calibration(value)
                            if not calib_success:
                                self.log(f"Failed to load calibration: {value}", "error")
                                success = False
                        else:
                            self.camera_manager.load_calibration(value)

            # Update configuration manager
            config_success = self.config_manager.update_camera_configuration(**kwargs)
            if not config_success:
                success = False

            # Auto-save if enabled and successful
            if success and self.auto_save_enabled:
                self.auto_save_configuration()

            return success

        except Exception as e:
            error_msg = f"Failed to update camera settings: {e}"
            self.log(error_msg, "error")
            return False

    def update_hardware_settings(self, **kwargs) -> bool:
        """Update hardware configuration with immediate feedback"""
        try:
            success = True

            # Apply to hardware service
            for key, value in kwargs.items():
                if key in ['machine_size_x', 'machine_size_y', 'machine_size_z']:
                    if all(k in kwargs for k in ['machine_size_x', 'machine_size_y', 'machine_size_z']):
                        try:
                            self.hardware_service.update_machine_size(
                                kwargs['machine_size_x'],
                                kwargs['machine_size_y'],
                                kwargs['machine_size_z']
                            )
                        except Exception as e:
                            self.log(f"Failed to update machine size: {e}", "error")
                            success = False

                elif key in ['camera_offset_x', 'camera_offset_y', 'camera_offset_z']:
                    if all(k in kwargs for k in ['camera_offset_x', 'camera_offset_y', 'camera_offset_z']):
                        try:
                            self.hardware_service.update_camera_offset(
                                kwargs['camera_offset_x'],
                                kwargs['camera_offset_y'],
                                kwargs['camera_offset_z']
                            )
                        except Exception as e:
                            self.log(f"Failed to update camera offset: {e}", "error")
                            success = False

                elif key == 'machine_origin':
                    try:
                        if isinstance(value, str):
                            origin = MachineOrigin(value)
                        else:
                            origin = value
                        self.hardware_service.set_machine_origin(origin)
                    except Exception as e:
                        self.log(f"Failed to update machine origin: {e}", "error")
                        success = False

            # Update configuration manager
            config_success = self.config_manager.update_hardware_configuration(**kwargs)
            if not config_success:
                success = False

            # Auto-save if enabled and successful
            if success and self.auto_save_enabled:
                self.auto_save_configuration()

            return success

        except Exception as e:
            error_msg = f"Failed to update hardware settings: {e}"
            self.log(error_msg, "error")
            return False

    def get_current_configuration(self) -> Optional[ApplicationConfig]:
        """Get current configuration"""
        return self.config_manager.get_current_configuration()

    def get_camera_status(self) -> dict:
        """Get current camera status with store awareness"""
        status = {
            'connected': False,
            'camera_id': self.camera_manager.camera_id,
            'resolution': self.camera_manager.resolution,
            'calibrated': self.camera_manager.is_calibrated(),
            'store_integrated': self._camera_is_store_integrated
        }

        if self._camera_is_store_integrated and self.store:
            # Get status from store
            camera_state = self.store.get_state().camera
            status.update({
                'connected': camera_state.connected,
                'calibration_file': camera_state.calibration_file
            })
        else:
            # Get status from camera manager directly
            status['connected'] = self.camera_manager.is_connected

        return status

    def get_hardware_status(self) -> dict:
        """Get current hardware status"""
        return {
            'machine_size': self.hardware_service.get_machine_size(),
            'camera_offset': self.hardware_service.get_camera_offset(),
            'machine_origin': self.hardware_service.machine_origin.value,
            'homing_position': self.hardware_service.get_homing_position()
        }

    def is_configuration_valid(self) -> tuple[bool, list]:
        """Validate current configuration and return status with errors"""
        config = self.get_current_configuration()
        if not config:
            return False, ["No configuration loaded"]

        errors = []

        # Validate camera configuration
        if config.camera:
            if config.camera.camera_id < 0:
                errors.append("Invalid camera ID")
            if config.camera.resolution_width <= 0 or config.camera.resolution_height <= 0:
                errors.append("Invalid camera resolution")
            if config.camera.marker_length_mm <= 0:
                errors.append("Invalid marker length")

        # Validate hardware configuration
        if config.hardware:
            if any(size <= 0 for size in [config.hardware.machine_size_x,
                                          config.hardware.machine_size_y,
                                          config.hardware.machine_size_z]):
                errors.append("Invalid machine size")

        return len(errors) == 0, errors


# === CONFIGURATION SERVICE FACTORY ===

def create_configuration_service(hardware_service: HardwareService,
                                 camera_manager: CameraManager,
                                 store: Optional[ApplicationStore] = None,
                                 logger: Optional[Callable] = None) -> ConfigurationService:
    """
    Factory function to create configuration service with proper dependencies
    """
    return ConfigurationService(
        hardware_service=hardware_service,
        camera_manager=camera_manager,
        store=store,
        logger=logger
    )


# === USAGE EXAMPLES ===

"""
Example usage with store-integrated CameraManager:

store = ApplicationStore()
camera_manager = CameraManager(store=store, enable_capture_thread=True)
hardware_service = HardwareService()

config_service = ConfigurationService(
    hardware_service=hardware_service,
    camera_manager=camera_manager,
    store=store,
    logger=print
)

# Load configuration with immediate feedback
success = config_service.load_and_apply_configuration("config/default.yaml")
if not success:
    print("Configuration loading failed")

# Update camera settings with immediate feedback
success = config_service.update_camera_settings(
    camera_id=1,
    resolution_width=1280,
    resolution_height=720
)
if not success:
    print("Camera settings update failed")
"""