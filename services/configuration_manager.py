# services/configuration_manager.py
"""
Configuration Manager for CNC Machine Registration System
Handles loading and saving YAML configurations for hardware, camera, and application settings
Follows SOLID principles with single responsibility
"""

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from services.event_broker import event_aware
from services.hardware_service import MachineOrigin


class ConfigurationEvents:
    """Events dispatched by configuration manager"""
    LOADED = "config.loaded"
    SAVED = "config.saved"
    ERROR = "config.error"
    VALIDATED = "config.validated"
    VALIDATION_FAILED = "config.validation_failed"


@dataclass
class CameraConfiguration:
    """Camera configuration data structure"""
    camera_id: int = 0
    resolution_width: int = 640
    resolution_height: int = 480
    calibration_file: Optional[str] = None
    marker_length_mm: float = 15.0


@dataclass
class HardwareConfiguration:
    """Hardware configuration data structure"""
    machine_size_x: float = 450.0
    machine_size_y: float = 450.0
    machine_size_z: float = 80.0
    camera_offset_x: float = -45.0
    camera_offset_y: float = 0.0
    camera_offset_z: float = 0.0
    machine_origin: str = "TOP_RIGHT"
    homing_position_x: float = -450.0
    homing_position_y: float = -450.0
    homing_position_z: float = 0.0


@dataclass
class ApplicationConfiguration:
    """Application-specific configuration"""
    last_routes_file: Optional[str] = None
    last_registration_file: Optional[str] = None
    auto_connect_camera: bool = True
    default_export_format: str = "gcode"
    fov_calculation_samples: int = 5


@dataclass
class ApplicationConfig:
    """Complete application configuration"""
    camera: CameraConfiguration
    hardware: HardwareConfiguration
    application: ApplicationConfiguration
    version: str = "1.0"

    @classmethod
    def create_default(cls) -> 'ApplicationConfig':
        """Create default configuration"""
        return cls(
            camera=CameraConfiguration(),
            hardware=HardwareConfiguration(),
            application=ApplicationConfiguration()
        )


@event_aware()
class ConfigurationManager:
    """
    Manages YAML configuration files for the CNC registration application
    Single responsibility: configuration persistence and validation
    """

    def __init__(self, config_directory: str = "config"):
        self.config_directory = Path(config_directory)
        self.config_directory.mkdir(exist_ok=True)

        self.current_config: Optional[ApplicationConfig] = None
        self.config_file_path: Optional[Path] = None

    def load_configuration(self, file_path: str) -> bool:
        """
        Load configuration from YAML file

        Args:
            file_path: Path to YAML configuration file

        Returns:
            True if successful, False otherwise
        """
        try:
            config_path = Path(file_path)

            if not config_path.exists():
                self.emit(ConfigurationEvents.ERROR, f"Configuration file not found: {file_path}")
                return False

            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)

            # Validate and convert YAML data to configuration objects
            config = self._yaml_to_config(yaml_data)

            if not self._validate_configuration(config):
                return False

            self.current_config = config
            self.config_file_path = config_path

            self.emit(ConfigurationEvents.LOADED, {
                'file_path': str(config_path),
                'config': config
            })

            return True

        except yaml.YAMLError as e:
            error_msg = f"YAML parsing error: {e}"
            self.emit(ConfigurationEvents.ERROR, error_msg)
            return False
        except Exception as e:
            error_msg = f"Failed to load configuration: {e}"
            self.emit(ConfigurationEvents.ERROR, error_msg)
            return False

    def save_configuration(self, file_path: str, config: Optional[ApplicationConfig] = None) -> bool:
        """
        Save configuration to YAML file

        Args:
            file_path: Path where to save the configuration
            config: Configuration to save (uses current if None)

        Returns:
            True if successful, False otherwise
        """
        try:
            if config is None:
                config = self.current_config

            if config is None:
                self.emit(ConfigurationEvents.ERROR, "No configuration to save")
                return False

            config_path = Path(file_path)
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert configuration to YAML-friendly dictionary
            yaml_data = self._config_to_yaml(config)

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, indent=2, sort_keys=False)

            self.config_file_path = config_path

            self.emit(ConfigurationEvents.SAVED, {
                'file_path': str(config_path),
                'config': config
            })

            return True

        except Exception as e:
            error_msg = f"Failed to save configuration: {e}"
            self.emit(ConfigurationEvents.ERROR, error_msg)
            return False

    def get_current_configuration(self) -> Optional[ApplicationConfig]:
        """Get the currently loaded configuration"""
        return self.current_config

    def update_camera_configuration(self, **kwargs) -> bool:
        """Update camera configuration parameters"""
        if self.current_config is None:
            self.current_config = ApplicationConfig.create_default()

        try:
            for key, value in kwargs.items():
                if hasattr(self.current_config.camera, key):
                    setattr(self.current_config.camera, key, value)
                else:
                    raise ValueError(f"Unknown camera configuration parameter: {key}")

            return True

        except Exception as e:
            self.emit(ConfigurationEvents.ERROR, f"Failed to update camera config: {e}")
            return False

    def update_hardware_configuration(self, **kwargs) -> bool:
        """Update hardware configuration parameters"""
        if self.current_config is None:
            self.current_config = ApplicationConfig.create_default()

        try:
            for key, value in kwargs.items():
                if hasattr(self.current_config.hardware, key):
                    setattr(self.current_config.hardware, key, value)
                else:
                    raise ValueError(f"Unknown hardware configuration parameter: {key}")

            return True

        except Exception as e:
            self.emit(ConfigurationEvents.ERROR, f"Failed to update hardware config: {e}")
            return False

    def update_application_configuration(self, **kwargs) -> bool:
        """Update application configuration parameters"""
        if self.current_config is None:
            self.current_config = ApplicationConfig.create_default()

        try:
            for key, value in kwargs.items():
                if hasattr(self.current_config.application, key):
                    setattr(self.current_config.application, key, value)
                else:
                    raise ValueError(f"Unknown application configuration parameter: {key}")

            return True

        except Exception as e:
            self.emit(ConfigurationEvents.ERROR, f"Failed to update application config: {e}")
            return False

    def create_default_configuration_file(self, file_path: str) -> bool:
        """Create a default configuration file"""
        default_config = ApplicationConfig.create_default()
        return self.save_configuration(file_path, default_config)

    def _yaml_to_config(self, yaml_data: Dict[str, Any]) -> ApplicationConfig:
        """Convert YAML data to ApplicationConfig object"""
        camera_data = yaml_data.get('camera', {})
        hardware_data = yaml_data.get('hardware', {})
        application_data = yaml_data.get('application', {})
        version = yaml_data.get('version', '1.0')

        camera_config = CameraConfiguration(**camera_data)
        hardware_config = HardwareConfiguration(**hardware_data)
        application_config = ApplicationConfiguration(**application_data)

        return ApplicationConfig(
            camera=camera_config,
            hardware=hardware_config,
            application=application_config,
            version=version
        )

    def _config_to_yaml(self, config: ApplicationConfig) -> Dict[str, Any]:
        """Convert ApplicationConfig object to YAML-friendly dictionary"""
        return {
            'version': config.version,
            'camera': asdict(config.camera),
            'hardware': asdict(config.hardware),
            'application': asdict(config.application)
        }

    def _validate_configuration(self, config: ApplicationConfig) -> bool:
        """
        Validate configuration data

        Args:
            config: Configuration to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            errors = []

            # Validate camera configuration
            if config.camera.camera_id < 0:
                errors.append("Camera ID must be non-negative")

            if config.camera.resolution_width <= 0 or config.camera.resolution_height <= 0:
                errors.append("Camera resolution must be positive")

            if config.camera.marker_length_mm <= 0:
                errors.append("Marker length must be positive")

            # Validate hardware configuration
            if any(size <= 0 for size in [config.hardware.machine_size_x,
                                          config.hardware.machine_size_y,
                                          config.hardware.machine_size_z]):
                errors.append("Machine size dimensions must be positive")

            # Validate machine origin
            valid_origins = [origin.value for origin in MachineOrigin]
            if config.hardware.machine_origin not in valid_origins:
                errors.append(f"Invalid machine origin. Must be one of: {valid_origins}")

            # Check if calibration file exists (if specified)
            if config.camera.calibration_file:
                calib_path = Path(config.camera.calibration_file)
                if not calib_path.exists():
                    errors.append(f"Camera calibration file not found: {config.camera.calibration_file}")

            # Check if last files exist (if specified)
            if config.application.last_routes_file:
                routes_path = Path(config.application.last_routes_file)
                if not routes_path.exists():
                    errors.append(f"Last routes file not found: {config.application.last_routes_file}")

            if config.application.last_registration_file:
                reg_path = Path(config.application.last_registration_file)
                if not reg_path.exists():
                    errors.append(f"Last registration file not found: {config.application.last_registration_file}")

            if errors:
                self.emit(ConfigurationEvents.VALIDATION_FAILED, {
                    'errors': errors,
                    'config': config
                })
                return False
            else:
                self.emit(ConfigurationEvents.VALIDATED, {
                    'config': config
                })
                return True

        except Exception as e:
            error_msg = f"Configuration validation failed: {e}"
            self.emit(ConfigurationEvents.ERROR, error_msg)
            return False