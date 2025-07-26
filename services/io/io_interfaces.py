from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any


class IRouteImporter(ABC):
    """Interface for route importers"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the importer"""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> List[str]:
        """Supported file extensions (e.g., ['.svg', '.dxf'])"""
        pass

    @property
    @abstractmethod
    def file_description(self) -> str:
        """File type description for dialogs (e.g., 'SVG files')"""
        pass

    @abstractmethod
    def can_import(self, file_path: str) -> bool:
        """Check if this importer can handle the given file"""
        pass

    @abstractmethod
    def import_routes(self, file_path: str, **kwargs) -> Optional[List[List[Tuple[float, float]]]]:
        """
        Import routes from file

        Args:
            file_path: Path to file to import
            **kwargs: Additional import parameters

        Returns:
            List of routes or None on failure
        """
        pass


class IRouteExporter(ABC):
    """Interface for route exporters"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the exporter"""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> List[str]:
        """Supported file extensions"""
        pass

    @property
    @abstractmethod
    def file_description(self) -> str:
        """File type description for dialogs"""
        pass

    @property
    @abstractmethod
    def default_extension(self) -> str:
        """Default file extension (e.g., '.svg')"""
        pass

    @abstractmethod
    def export_routes(self,
                      routes: List[List[Tuple[float, float]]],
                      output_file: str,
                      **kwargs) -> bool:
        """
        Export routes to file

        Args:
            routes: Routes to export
            output_file: Output file path
            **kwargs: Additional export parameters

        Returns:
            True if export successful
        """
        pass

    @abstractmethod
    def get_export_options(self) -> Dict[str, Any]:
        """Get available export options with defaults"""
        pass