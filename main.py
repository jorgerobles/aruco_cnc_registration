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

    grbl_controller = GRBLController(
        machine_origin=MachineOrigin.TOP_RIGHT
    )
    grbl_controller.enable_verbose_logging()

    app = RegistrationGUI(root,
                              registration_manager=RegistrationManager(),
                              camera_manager=CameraManager(),
                              grbl_controller=grbl_controller,
                              route_manager=RouteManager(),
                                hardware_service=HardwareService()
                              )
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()