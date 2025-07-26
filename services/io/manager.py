"""
Import/Export Interfaces for RouteManager
Allows pluggable importers and exporters for different formats
"""
from typing import List, Optional, Tuple

from services.io.io_interfaces import IRouteImporter, IRouteExporter


class ImportExportManager:
    """Manages collection of importers and exporters"""

    def __init__(self):
        self._importers: List[IRouteImporter] = []
        self._exporters: List[IRouteExporter] = []

    def register_importer(self, importer: IRouteImporter):
        """Register a route importer"""
        self._importers.append(importer)

    def register_exporter(self, exporter: IRouteExporter):
        """Register a route exporter"""
        self._exporters.append(exporter)

    def get_importers(self) -> List[IRouteImporter]:
        """Get all registered importers"""
        return self._importers.copy()

    def get_exporters(self) -> List[IRouteExporter]:
        """Get all registered exporters"""
        return self._exporters.copy()

    def find_importer(self, file_path: str) -> Optional[IRouteImporter]:
        """Find suitable importer for file"""
        for importer in self._importers:
            if importer.can_import(file_path):
                return importer
        return None

    def find_exporter_by_extension(self, extension: str) -> Optional[IRouteExporter]:
        """Find exporter by file extension"""
        for exporter in self._exporters:
            if extension.lower() in [ext.lower() for ext in exporter.file_extensions]:
                return exporter
        return None

    def get_import_file_types(self) -> List[Tuple[str, str]]:
        """Get file types for import dialog"""
        file_types = []
        for importer in self._importers:
            extensions = " ".join([f"*{ext}" for ext in importer.file_extensions])
            file_types.append((importer.file_description, extensions))
        return file_types

    def get_export_file_types(self) -> List[Tuple[str, str]]:
        """Get file types for export dialog"""
        file_types = []
        for exporter in self._exporters:
            extensions = " ".join([f"*{ext}" for ext in exporter.file_extensions])
            file_types.append((exporter.file_description, extensions))
        return file_types