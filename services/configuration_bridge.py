# services/configuration_bridge.py
"""
Configuration Bridge Service
Ensures GUI components are synchronized with configuration on startup and changes
Simple service that handles the coordination between configuration and UI components
"""

from typing import List, Any
from services.configuration_service import ConfigurationService
from services.event_broker import event_aware, event_handler, EventPriority


@event_aware()
class ConfigurationBridge:
    """
    Bridge service that ensures UI components stay synchronized with configuration
    Handles initial synchronization and updates when configuration changes
    """

    def __init__(self, configuration_service: ConfigurationService):
        self.configuration_service = configuration_service
        self.registered_components = []

    def register_component(self, component):
        """
        Register a GUI component for configuration synchronization
        Component should have update_from_configuration method
        """
        if hasattr(component, 'update_from_configuration'):
            self.registered_components.append(component)

            # Immediately sync with current configuration if available
            current_config = self.configuration_service.get_current_configuration()
            if current_config:
                self._sync_component_with_config(component, current_config)
        else:
            raise ValueError("Component must have 'update_from_configuration' method")

    def sync_all_components(self):
        """Synchronize all registered components with current configuration"""
        current_config = self.configuration_service.get_current_configuration()
        if current_config:
            for component in self.registered_components:
                self._sync_component_with_config(component, current_config)

    def _sync_component_with_config(self, component, config):
        """Synchronize a single component with configuration"""
        try:
            component.update_from_configuration(config)

            # Also update hardware offset if component supports it
            if hasattr(component, 'update_hardware_offset_from_configuration'):
                component.update_hardware_offset_from_configuration(config)

        except Exception as e:
            print(f"Error syncing component {type(component).__name__}: {e}")


# Utility function to initialize camera panel with current configuration
def initialize_camera_panel_with_config(camera_panel, configuration_service: ConfigurationService):
    """
    Utility function to initialize camera panel with current configuration
    Call this after creating the camera panel to ensure it shows correct values
    """
    current_config = configuration_service.get_current_configuration()
    if current_config:
        camera_panel.update_from_configuration(current_config)
        camera_panel.update_hardware_offset_from_configuration(current_config)

        # Log the synchronization
        if hasattr(camera_panel, 'log'):
            camera_panel.log("Camera panel initialized with current configuration")


# Utility function for main application
def setup_configuration_sync(configuration_service: ConfigurationService, *components):
    """
    Utility function to setup configuration synchronization for multiple components

    Args:
        configuration_service: The configuration service instance
        *components: GUI components that need configuration sync

    Returns:
        ConfigurationBridge instance for further management
    """
    bridge = ConfigurationBridge(configuration_service)

    for component in components:
        try:
            bridge.register_component(component)
        except ValueError as e:
            print(f"Warning: Could not register component {type(component).__name__}: {e}")

    return bridge