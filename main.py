"""
GRBL Camera Registration Application
Main entry point for the application
"""

import tkinter as tk

from gui.main_window import RegistrationGUI
from services.camera_manager import CameraManager
from services.grbl_controller import GRBLController
from services.hardware_service import HardwareService, MachineOrigin
from services.registration_manager import RegistrationManager
from services.routes_manager import RouteManager


def main():
    """Main application entry point"""
    root = tk.Tk()

    grbl_controller = GRBLController()
    grbl_controller.enable_verbose_logging()

    hardware_service = HardwareService(
        machine_size=(450, 450, 80),  # Your machine size
        camera_offset=(-45, 0, 0),  # Camera offset from spindle
        machine_origin=MachineOrigin.TOP_RIGHT,  # Set your origin type
        homing_position = (-450, -450, 0)

    )

    app = RegistrationGUI(root,
                          registration_manager=RegistrationManager(),
                          camera_manager=CameraManager(),
                          grbl_controller=grbl_controller,
                          route_manager=RouteManager(),
                          hardware_service=hardware_service
                          )
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()
