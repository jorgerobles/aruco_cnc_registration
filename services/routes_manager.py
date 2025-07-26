"""
Refactored RouteManager with Import/Export Service Stack
Follows Open/Closed principle - extensible without modification
"""

from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import os

from services.event_broker import event_aware
from services.io.format_gcode import GCodeExporter
from services.io.format_svg import SVGImporter, SVGExporter
from services.io.manager import ImportExportManager


class RouteEvents:
    """Route-specific events"""
    ROUTES_LOADED = "routes.loaded"
    ROUTES_CLEARED = "routes.cleared"
    ROUTES_TRANSFORMED = "routes.transformed"
    ROUTE_BOUNDS_CHANGED = "routes.bounds_changed"
    ROUTES_EXPORTED = "routes.exported"
    IMPORT_FAILED = "routes.import_failed"
    EXPORT_FAILED = "routes.export_failed"


@event_aware()
class RouteManager:
    """Enhanced RouteManager with pluggable import/export services"""

    def __init__(self, import_export_manager: ImportExportManager, logger=None):
        self.logger = logger

        # Import/Export service manager
        self.import_export_manager = import_export_manager

        # Route data
        self.routes = []
        self.route_bounds = None
        self.routes_loaded = False
        self.current_file = None

        # Transformation data
        self.transformation_matrix = None
        self.transformed_routes = []

        # Statistics
        self.total_length = 0.0
        self.point_count = 0

        self.log("Routes service initialized with pluggable import/export")

    def register_importer(self, importer):
        """Register additional route importer"""
        self.import_export_manager.register_importer(importer)
        self.log(f"Registered importer: {importer.name}")

    def register_exporter(self, exporter):
        """Register additional route exporter"""
        self.import_export_manager.register_exporter(exporter)
        self.log(f"Registered exporter: {exporter.name}")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[RoutesService] {message}", level)

    def load_routes_from_file(self, file_path: str, **kwargs) -> bool:
        """Load routes using appropriate importer"""
        try:
            self.log(f"Loading routes from: {file_path}")

            # Find suitable importer
            importer = self.import_export_manager.find_importer(file_path)
            if not importer:
                self.log(f"No importer found for: {file_path}", "error")
                self.emit(RouteEvents.IMPORT_FAILED, {
                    'file': file_path,
                    'error': 'No suitable importer found'
                })
                return False

            # Import routes
            routes = importer.import_routes(file_path, **kwargs)
            if not routes:
                self.log(f"Import failed: {file_path}", "error")
                self.emit(RouteEvents.IMPORT_FAILED, {
                    'file': file_path,
                    'importer': importer.name,
                    'error': 'Import returned no routes'
                })
                return False

            # Store routes
            self.routes = routes
            self.current_file = file_path
            self.routes_loaded = True

            # Calculate bounds and statistics
            self._calculate_bounds()
            self._calculate_statistics()

            # Clear transformations
            self.transformation_matrix = None
            self.transformed_routes = []

            self.log(f"Loaded {len(self.routes)} routes using {importer.name}")

            # Emit event
            self.emit(RouteEvents.ROUTES_LOADED, {
                'file': file_path,
                'importer': importer.name,
                'route_count': len(self.routes),
                'point_count': self.point_count,
                'bounds': self.route_bounds,
                'total_length': self.total_length
            })

            return True

        except Exception as e:
            error_msg = f"Error loading routes: {e}"
            self.log(error_msg, "error")
            self.emit(RouteEvents.IMPORT_FAILED, {
                'file': file_path,
                'error': str(e)
            })
            self.clear_routes()
            return False

    def export_routes_to_file(self,
                            output_file: str,
                            use_transformed: bool = False,
                            exporter_name: str = None,
                            **kwargs) -> bool:
        """Export routes using appropriate exporter"""
        try:
            routes_to_export = self._get_export_routes(use_transformed)
            if not routes_to_export:
                self.log("No routes to export", "warning")
                return False

            # Find exporter
            if exporter_name:
                exporter = next((e for e in self.import_export_manager.get_exporters()
                               if e.name == exporter_name), None)
            else:
                # Auto-detect by file extension
                _, ext = os.path.splitext(output_file)
                exporter = self.import_export_manager.find_exporter_by_extension(ext)

            if not exporter:
                self.log(f"No exporter found for: {output_file}", "error")
                self.emit(RouteEvents.EXPORT_FAILED, {
                    'file': output_file,
                    'error': 'No suitable exporter found'
                })
                return False

            # Add metadata
            if 'metadata' not in kwargs:
                kwargs['metadata'] = self._create_export_metadata()

            # Export routes
            success = exporter.export_routes(routes_to_export, output_file, **kwargs)

            if success:
                self.emit(RouteEvents.ROUTES_EXPORTED, {
                    'output_file': output_file,
                    'exporter': exporter.name,
                    'route_count': len(routes_to_export),
                    'use_transformed': use_transformed
                })
                self.log(f"Exported using {exporter.name}: {output_file}")
            else:
                self.emit(RouteEvents.EXPORT_FAILED, {
                    'file': output_file,
                    'exporter': exporter.name,
                    'error': 'Export operation failed'
                })
                self.log(f"Export failed using {exporter.name}", "error")

            return success

        except Exception as e:
            error_msg = f"Export error: {e}"
            self.log(error_msg, "error")
            self.emit(RouteEvents.EXPORT_FAILED, {
                'file': output_file,
                'error': str(e)
            })
            return False

    # Backward compatibility methods
    def load_routes_from_svg(self, svg_file: str, angle_threshold: float = 5.0) -> bool:
        """Backward compatibility: Load SVG routes"""
        return self.load_routes_from_file(svg_file,
                                        angle_threshold=angle_threshold,
                                        skip_display_none=True)

    def export_routes_to_svg(self, output_file: str, use_transformed: bool = False, **kwargs) -> bool:
        """Backward compatibility: Export to SVG"""
        return self.export_routes_to_file(output_file, use_transformed, "SVG Exporter", **kwargs)

    def get_import_file_types(self) -> List[Tuple[str, str]]:
        """Get file types for import dialog"""
        return self.import_export_manager.get_import_file_types()

    def get_export_file_types(self) -> List[Tuple[str, str]]:
        """Get file types for export dialog"""
        return self.import_export_manager.get_export_file_types()

    def get_exporters(self) -> List:
        """Get available exporters"""
        return self.import_export_manager.get_exporters()

    def get_importers(self) -> List:
        """Get available importers"""
        return self.import_export_manager.get_importers()

    def _get_export_routes(self, use_transformed: bool) -> List[List[Tuple[float, float]]]:
        """Get routes for export"""
        if use_transformed and self.transformed_routes:
            return self.transformed_routes
        return self.routes

    def _create_export_metadata(self) -> Dict[str, Any]:
        """Create metadata for export"""
        return {
            'source_file': self.current_file or 'unknown',
            'route_count': len(self.routes),
            'point_count': self.point_count,
            'total_length_mm': f"{self.total_length:.2f}",
            'exported_by': 'RouteManager'
        }

    # Keep existing methods unchanged
    def clear_routes(self):
        """Clear all route data"""
        self.routes = []
        self.route_bounds = None
        self.routes_loaded = False
        self.current_file = None
        self.transformation_matrix = None
        self.transformed_routes = []
        self.total_length = 0.0
        self.point_count = 0

        self.log("Routes cleared")
        self.emit(RouteEvents.ROUTES_CLEARED)

    def get_routes(self) -> List[List[Tuple[float, float]]]:
        """Get current routes data"""
        return self.routes.copy() if self.routes else []

    def get_route_bounds(self) -> Optional[List[float]]:
        """Get route bounds [x_min, y_min, x_max, y_max]"""
        return self.route_bounds.copy() if self.route_bounds else None

    def get_routes_count(self) -> int:
        """Get number of loaded routes"""
        return len(self.routes) if self.routes else 0

    def get_total_route_length(self) -> float:
        """Get total length of all routes"""
        return self.total_length

    def get_point_count(self) -> int:
        """Get total number of points in all routes"""
        return self.point_count

    def is_loaded(self) -> bool:
        """Check if routes are loaded"""
        return self.routes_loaded and len(self.routes) > 0

    def get_route_info(self) -> Dict[str, Any]:
        """Get comprehensive route information"""
        return {
            'loaded': self.routes_loaded,
            'file': self.current_file,
            'route_count': len(self.routes) if self.routes else 0,
            'point_count': self.point_count,
            'bounds': self.route_bounds.copy() if self.route_bounds else None,
            'total_length': self.total_length,
            'has_transformation': self.transformation_matrix is not None,
        }

    def _calculate_bounds(self):
        """Calculate bounding box of all routes"""
        if not self.routes:
            self.route_bounds = None
            return

        try:
            all_x = []
            all_y = []

            for route in self.routes:
                for x, y in route:
                    all_x.append(x)
                    all_y.append(y)

            if all_x and all_y:
                self.route_bounds = [
                    min(all_x), min(all_y), max(all_x), max(all_y)
                ]
            else:
                self.route_bounds = None

        except Exception as e:
            self.log(f"Error calculating bounds: {e}", "error")
            self.route_bounds = None

    def _calculate_statistics(self):
        """Calculate route statistics"""
        if not self.routes:
            self.total_length = 0.0
            self.point_count = 0
            return

        try:
            total_length = 0.0
            point_count = 0

            for route in self.routes:
                point_count += len(route)

                for i in range(len(route) - 1):
                    x1, y1 = route[i]
                    x2, y2 = route[i + 1]
                    segment_length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    total_length += segment_length

            self.total_length = total_length
            self.point_count = point_count

        except Exception as e:
            self.log(f"Error calculating statistics: {e}", "error")
            self.total_length = 0.0
            self.point_count = 0