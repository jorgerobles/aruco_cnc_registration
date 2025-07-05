# SOLUTION: Segregated interfaces
from abc import ABC, abstractmethod
from concurrent.futures import Future
from typing import List


class IGRBLConnection(ABC):
    @abstractmethod
    def connect(self, port: str, baudrate: int = 115200) -> bool: pass

    @abstractmethod
    def disconnect(self) -> None: pass

    @abstractmethod
    def is_connected(self) -> bool: pass


class IGRBLMovement(ABC):
    @abstractmethod
    def home(self) -> bool: pass

    @abstractmethod
    def move_to(self, x: float, y: float, z: float, feed_rate: float = None) -> bool: pass

    @abstractmethod
    def jog_relative(self, x: float = 0, y: float = 0, z: float = 0, feed_rate: float = 1000) -> bool: pass

    @abstractmethod
    def emergency_stop(self) -> bool: pass

    @abstractmethod
    def resume(self) -> bool: pass

    @abstractmethod
    def reset(self) -> bool: pass


class IGRBLStatus(ABC):
    @abstractmethod
    def get_position(self) -> List[float]: pass

    @abstractmethod
    def get_status(self) -> str: pass


class IGRBLCommunication(ABC):
    @abstractmethod
    def send_command(self, command: str, timeout: float = None) -> List[str]: pass

    @abstractmethod
    def send_command_async(self, command: str, timeout: float = None) -> Future: pass

    @abstractmethod
    def send_realtime_command(self, command: str) -> None: pass