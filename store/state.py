# store/state.py
"""
Application State Data Structures
Clean, immutable state representation following SOLID principles
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any


class MachineOrigin(Enum):
    TOP_LEFT = "TOP_LEFT"
    TOP_RIGHT = "TOP_RIGHT"
    BOTTOM_LEFT = "BOTTOM_LEFT"
    BOTTOM_RIGHT = "BOTTOM_RIGHT"


@dataclass(frozen=True)
class CameraState:
    """Camera subsystem state"""
    connected: bool = False
    camera_id: int = 0
    resolution: Tuple[int, int] = (640, 480)
    calibration_file: Optional[str] = None
    current_frame: Optional[Any] = None  # np.ndarray, but avoiding numpy in dataclass
    marker_detection: Optional[Dict] = None
    fov_data: Optional[Dict] = None


@dataclass(frozen=True)
class MachineState:
    """GRBL machine subsystem state"""
    connected: bool = False
    port: str = "/dev/ttyUSB0"
    baudrate: int = 115200
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    status: str = "Unknown"
    homing_complete: bool = False
    work_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class HardwareConfig:
    """Hardware configuration state"""
    machine_size: Tuple[float, float, float] = (450.0, 450.0, 80.0)
    camera_offset: Tuple[float, float, float] = (-45.0, 0.0, 0.0)
    machine_origin: MachineOrigin = MachineOrigin.TOP_RIGHT
    homing_position: Tuple[float, float, float] = (-450.0, -450.0, 0.0)


@dataclass(frozen=True)
class CalibrationPoint:
    """Single calibration point data"""
    machine_pos: Tuple[float, float, float]
    camera_pos: Tuple[float, float]
    timestamp: float


@dataclass(frozen=True)
class RegistrationState:
    """Camera-machine registration state"""
    calibration_points: List[CalibrationPoint] = field(default_factory=list)
    transformation_matrix: Optional[Any] = None  # np.ndarray
    is_registered: bool = False
    registration_error: Optional[float] = None


@dataclass(frozen=True)
class RoutesState:
    """Routes and path planning state"""
    routes: List[List[Tuple[float, float]]] = field(default_factory=list)
    transformed_routes: List[List[Tuple[float, float]]] = field(default_factory=list)
    bounds: Optional[Dict] = None
    current_file: Optional[str] = None
    total_length: float = 0.0
    point_count: int = 0


@dataclass(frozen=True)
class ConfigurationState:
    """Application configuration state"""
    current_file: Optional[str] = None
    auto_save: bool = True
    last_routes_file: Optional[str] = None
    last_registration_file: Optional[str] = None


@dataclass(frozen=True)
class UIState:
    """User interface state"""
    machine_area_visible: bool = False
    debug_panel_expanded: bool = False
    status_message: str = "Ready"
    current_tab: str = "camera"


@dataclass(frozen=True)
class SystemState:
    """System-level state"""
    startup_complete: bool = False
    last_error: Optional[str] = None
    performance_metrics: Dict = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicationState:
    """Complete application state - single source of truth"""
    camera: CameraState = field(default_factory=CameraState)
    machine: MachineState = field(default_factory=MachineState)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    registration: RegistrationState = field(default_factory=RegistrationState)
    routes: RoutesState = field(default_factory=RoutesState)
    config: ConfigurationState = field(default_factory=ConfigurationState)
    ui: UIState = field(default_factory=UIState)
    system: SystemState = field(default_factory=SystemState)
