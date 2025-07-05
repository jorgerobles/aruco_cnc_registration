"""
Overlay Interface
Defines the contract for frame overlay components
"""

from abc import ABC, abstractmethod

import numpy as np


class FrameOverlay(ABC):
    """Abstract interface for frame overlay components"""

    @abstractmethod
    def apply_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply overlay to the given frame

        Args:
            frame: Input frame to apply overlay to

        Returns:
            Frame with overlay applied
        """
        pass

    @abstractmethod
    def set_visibility(self, visible: bool):
        """Toggle overlay visibility"""
        pass

    @abstractmethod
    def is_visible(self) -> bool:
        """Check if overlay is visible"""
        pass