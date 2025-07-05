# SOLUTION: Segregated interfaces
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class ICameraConnection(ABC):
    @abstractmethod
    def connect(self) -> bool: pass

    @abstractmethod
    def disconnect(self) -> None: pass

    @abstractmethod
    def is_connected(self) -> bool: pass


class ICameraCapture(ABC):
    @abstractmethod
    def capture_frame(self) -> Optional[np.ndarray]: pass


class ICameraCalibration(ABC):
    @abstractmethod
    def load_calibration(self, file_path: str) -> bool: pass

    @abstractmethod
    def is_calibrated(self) -> bool: pass

    @property
    @abstractmethod
    def camera_matrix(self) -> Optional[np.ndarray]: pass

    @property
    @abstractmethod
    def dist_coeffs(self) -> Optional[np.ndarray]: pass
