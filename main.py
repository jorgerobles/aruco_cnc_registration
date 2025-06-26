"""
GRBL Camera Registration Application
Main entry point for the application
"""

import tkinter as tk
from gui.main_window import RegistrationGUI


def main():
    """Main application entry point"""
    root = tk.Tk()
    app = RegistrationGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()