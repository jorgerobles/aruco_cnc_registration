# SOLUTION: Segregated interfaces
from abc import ABC, abstractmethod
from typing import List, Optional

import numpy as np


class IRegistrationDataManager(ABC):
    @abstractmethod
    def add_calibration_point(self, machine_pos: np.ndarray, camera_tvec: np.ndarray, norm_pos: np.ndarray): pass

    @abstractmethod
    def remove_calibration_point(self, index: int) -> bool: pass

    @abstractmethod
    def clear_calibration_points(self): pass

    @abstractmethod
    def get_calibration_points_count(self) -> int: pass

    @abstractmethod
    def get_machine_positions(self) -> List[np.ndarray]: pass


class IRegistrationComputation(ABC):
    @abstractmethod
    def compute_registration(self, force_recompute: bool = False) -> bool: pass

    @abstractmethod
    def transform_point(self, camera_point: np.ndarray) -> np.ndarray: pass

    @abstractmethod
    def is_registered(self) -> bool: pass

    @abstractmethod
    def get_registration_error(self) -> Optional[float]: pass


class IRegistrationPersistence(ABC):
    @abstractmethod
    def save_registration(self, filename: str) -> bool: pass

    @abstractmethod
    def load_registration(self, filename: str) -> bool: pass
