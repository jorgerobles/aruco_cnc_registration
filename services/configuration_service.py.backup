# services/configuration_service.py
"""
Configuration Service - Bridge between Configuration Manager and Application Services
Applies configurations to hardware, camera, and application services
Follows SOLID principles - single responsibility for configuration application
"""

from typing import Optional, Callable
from pathlib import Path

from services.configuration_manager import ConfigurationManager, ConfigurationEvents, ApplicationConfig
from services.hardware_service import HardwareService, MachineOrigin
from services.camera_manager import CameraManager
from services.event_broker import event_aware, event_handler, EventPriority


class ConfigurationServiceEvents:
    """Events dispatched by configuration service"""
    APPLIED = "config_service.applied"
    APPLY_FAILED = "config_service.apply_failed"
    AUTO_SAVED = "config_service.auto_saved"


@event_aware()
class ConfigurationService:
    """
    Configuration Service that applies configurations to application services
    Single responsibility: bridge configuration data to service implementations
    """

    def __init__(self,
                 hardware_service: HardwareService,
                 camera_manager: CameraManager,
                 logger: Optional[Callable] = None):
        self.hardware_service = hardware_service
        self.camera_manager = camera_manager
        self.logger = logger

        self.config_manager = ConfigurationManager()
        self.auto_save_enabled = True
        self.current_config_file: Optional[str] = None

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[ConfigService] {message}", level)

    def load_and_apply_configuration(self, file_path: str) -> bool:
        """
        Load configuration from file and apply to all services

        Args:
            file_path: Path to configuration file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load configuration
            if not self.config_manager.load_configuration(file_path):
                return False

            config = self.config_manager.get_current_configuration()
            if config is None:
                self.log("No configuration loaded", "error")
                return False

            # Apply to services
            success = self._apply_configuration_to_services(config)

            if success:
                self.current_config_file = file_path
                self.log(f"Configuration loaded and applied from: {file_path}")

                self.emit(ConfigurationServiceEvents.APPLIED, {
                    'file_path': file_path,
                    'config': config
                })
            else:
                self.emit(ConfigurationServiceEvents.APPLY_FAILED, {
                    'file_path': file_path,
                    'reason': "Failed to apply configuration to services"
                })

            return success

        except Exception as e:
            error_msg = f"Failed to load and apply configuration: {e}"
            self.log(error_msg, "error")
            self.emit(ConfigurationServiceEvents.APPLY_FAILED, {
                'file_path': file_path,
                'reason': error_msg
            })
            return False

    def save_current_configuration(self, file_path: str) -> bool:
        """
        Save current service configurations to file

        Args:
            file_path: Where to save the configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            # Gather current configurations from services
            config = self._gather_current_configuration()

            # Save to file
            success = self.config_manager.save_configuration(file_path, config)

            if success:
                self.current_config_file = file_path
                self.log(f"Configuration saved to: {file_path}")

            return success

        except Exception as e:
            error_msg = f"Failed to save configuration: {e}"
            self.log(error_msg, "error")
            return False

    def auto_save_configuration(self) -> bool:
        """Auto-save current configuration if enabled and file is set"""
        if not self.auto_save_enabled or not self.current_config_file:
            return False

        success = self.save_current_configuration(self.current_config_file)
        if success:
            self.emit(ConfigurationServiceEvents.AUTO_SAVED, {
                'file_path': self.current_config_file
            })

        return success

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
        """Update camera configuration and optionally auto-save"""
        try:
            # Apply to camera manager
            if 'camera_id' in kwargs:
                # Note: Camera reconnection would be handled by camera manager
                pass

            if 'resolution_width' in kwargs and 'resolution_height' in kwargs:
                # Note: Resolution change would require camera reconnection
                pass

            if 'calibration_file' in kwargs:
                calib_file = kwargs['calibration_file']
                if calib_file and Path(calib_file).exists():
                    self.camera_manager.load_calibration(calib_file)

            # Update configuration manager
            self.config_manager.update_camera_configuration(**kwargs)

            # Auto-save if enabled
            if self.auto_save_enabled:
                self.auto_save_configuration()

            return True

        except Exception as e:
            error_msg = f"Failed to update camera settings: {e}"
            self.log(error_msg, "error")
            return False

    def update_hardware_settings(self, **kwargs) -> bool:
        """Update hardware configuration and optionally auto-save"""
        try:
            # Apply to hardware service
            if any(key in kwargs for key in ['machine_size_x', 'machine_size_y', 'machine_size_z']):
                machine_size = (
                    kwargs.get('machine_size_x', self.hardware_service.machine_size['x']),
                    kwargs.get('machine_size_y', self.hardware_service.machine_size['y']),
                    kwargs.get('machine_size_z', self.hardware_service.machine_size['z'])
                )
                self.hardware_service.machine_size = {
                    'x': machine_size[0],
                    'y': machine_size[1],
                    'z': machine_size[2]
                }

            if any(key in kwargs for key in ['camera_offset_x', 'camera_offset_y', 'camera_offset_z']):
                camera_offset = (
                    kwargs.get('camera_offset_x', self.hardware_service.camera_offset['x']),
                    kwargs.get('camera_offset_y', self.hardware_service.camera_offset['y']),
                    kwargs.get('camera_offset_z', self.hardware_service.camera_offset['z'])
                )
                self.hardware_service.set_camera_offset(*camera_offset)

            if 'machine_origin' in kwargs:
                origin_str = kwargs['machine_origin']
                origin_enum = MachineOrigin(origin_str)
                self.hardware_service.machine_origin = origin_enum

            if any(key in kwargs for key in ['homing_position_x', 'homing_position_y', 'homing_position_z']):
                homing_pos = (
                    kwargs.get('homing_position_x', self.hardware_service.homing_position['x']),
                    kwargs.get('homing_position_y', self.hardware_service.homing_position['y']),
                    kwargs.get('homing_position_z', self.hardware_service.homing_position['z'])
                )
                self.hardware_service.homing_position = {
                    'x': homing_pos[0],
                    'y': homing_pos[1],
                    'z': homing_pos[2]
                }

            # Update configuration manager
            self.config_manager.update_hardware_configuration(**kwargs)

            # Auto-save if enabled
            if self.auto_save_enabled:
                self.auto_save_configuration()

            return True

        except Exception as e:
            error_msg = f"Failed to update hardware settings: {e}"
            self.log(error_msg, "error")
            return False

    def update_application_settings(self, **kwargs) -> bool:
        """Update application configuration and optionally auto-save"""
        try:
            # Update configuration manager
            self.config_manager.update_application_configuration(**kwargs)

            # Auto-save if enabled
            if self.auto_save_enabled:
                self.auto_save_configuration()

            return True

        except Exception as e:
            error_msg = f"Failed to update application settings: {e}"
            self.log(error_msg, "error")
            return False

    def set_auto_save(self, enabled: bool):
        """Enable or disable auto-save functionality"""
        self.auto_save_enabled = enabled
        self.log(f"Auto-save {'enabled' if enabled else 'disabled'}")

    def get_current_configuration(self) -> Optional[ApplicationConfig]:
        """Get current configuration"""
        return self.config_manager.get_current_configuration()

    def _apply_configuration_to_services(self, config: ApplicationConfig) -> bool:
        """Apply configuration to all services"""
        try:
            # Apply hardware configuration
            self.hardware_service.machine_size = {
                'x': config.hardware.machine_size_x,
                'y': config.hardware.machine_size_y,
                'z': config.hardware.machine_size_z
            }

            self.hardware_service.set_camera_offset(
                config.hardware.camera_offset_x,
                config.hardware.camera_offset_y,
                config.hardware.camera_offset_z
            )

            self.hardware_service.machine_origin = MachineOrigin(config.hardware.machine_origin)

            self.hardware_service.homing_position = {
                'x': config.hardware.homing_position_x,
                'y': config.hardware.homing_position_y,
                'z': config.hardware.homing_position_z
            }

            # Apply camera configuration
            # Note: Camera reconnection with new settings would be handled separately
            if config.camera.calibration_file and Path(config.camera.calibration_file).exists():
                self.camera_manager.load_calibration(config.camera.calibration_file)

            self.log("Configuration applied to all services")
            return True

        except Exception as e:
            error_msg = f"Failed to apply configuration to services: {e}"
            self.log(error_msg, "error")
            return False

    def _gather_current_configuration(self) -> ApplicationConfig:
        """Gather current configuration from all services"""
        # Get current hardware configuration
        hardware_config = self.config_manager.get_current_configuration()
        if hardware_config:
            # Update with current service values
            hardware_config.hardware.machine_size_x = self.hardware_service.machine_size['x']
            hardware_config.hardware.machine_size_y = self.hardware_service.machine_size['y']
            hardware_config.hardware.machine_size_z = self.hardware_service.machine_size['z']

            hardware_config.hardware.camera_offset_x = self.hardware_service.camera_offset['x']
            hardware_config.hardware.camera_offset_y = self.hardware_service.camera_offset['y']
            hardware_config.hardware.camera_offset_z = self.hardware_service.camera_offset['z']

            hardware_config.hardware.machine_origin = self.hardware_service.machine_origin.value

            hardware_config.hardware.homing_position_x = self.hardware_service.homing_position['x']
            hardware_config.hardware.homing_position_y = self.hardware_service.homing_position['y']
            hardware_config.hardware.homing_position_z = self.hardware_service.homing_position['z']

            return hardware_config
        else:
            # Create new configuration from current service values
            return ApplicationConfig.create_default()

    @event_handler(ConfigurationEvents.LOADED, EventPriority.NORMAL)
    def _on_configuration_loaded(self, event_data):
        """Handle configuration loaded event"""
        self.log(f"Configuration loaded: {event_data['file_path']}")

    @event_handler(ConfigurationEvents.ERROR, EventPriority.HIGH)
    def _on_configuration_error(self, error_message):
        """Handle configuration errors"""
        self.log(f"Configuration error: {error_message}", "error")