#!/usr/bin/env python3
"""
Route Transformation Debugging Application
Clean, lean implementation for SVG routes + registration points transformation
"""

import sys
import os
import tkinter as tk
import logging

# Add the parent directory to sys.path to access reference modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller import Controller


def setup_logging():
    """Setup basic logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__)


def main():
    """Main entry point"""
    logger = setup_logging()
    logger.info("Starting Route Transformation Debug Application")

    # Create main window
    root = tk.Tk()
    root.title("Route Transformation Debugger")
    root.geometry("1200x800")
    root.minsize(800, 600)

    # Create controller (handles everything)
    controller = Controller(root, logger)

    # Configure window closing
    def on_closing():
        logger.info("Shutting down debug application")
        root.quit()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Start main loop
    try:
        logger.info("Debug application ready")
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Debug application interrupted")
        on_closing()
    except Exception as e:
        logger.error(f"Debug application error: {e}")
        raise


if __name__ == "__main__":
    main()