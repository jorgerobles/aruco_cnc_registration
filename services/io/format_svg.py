"""
services.io - Route Import/Export Services
SVG importer/exporter implementations using existing svg modules
"""

import os
from typing import List, Tuple, Optional, Dict, Any

from services.io.io_interfaces import IRouteImporter, IRouteExporter
from svg.svg_loader import svg_to_routes
from svg.svg_exporter import routes_to_svg


class SVGImporter(IRouteImporter):
    """SVG file importer using svg_loader module"""

    @property
    def name(self) -> str:
        return "SVG Importer"

    @property
    def file_extensions(self) -> List[str]:
        return ['.svg']

    @property
    def file_description(self) -> str:
        return "SVG files"

    def can_import(self, file_path: str) -> bool:
        """Check if file can be imported"""
        try:
            return (os.path.exists(file_path) and
                    file_path.lower().endswith('.svg'))
        except Exception:
            return False

    def import_routes(self, file_path: str, **kwargs) -> Optional[List[List[Tuple[float, float]]]]:
        """Import routes from SVG file using svg_loader"""
        try:
            angle_threshold = kwargs.get('angle_threshold', 5.0)
            skip_display_none = kwargs.get('skip_display_none', True)

            routes = svg_to_routes(file_path, angle_threshold, skip_display_none)
            return routes if routes else None

        except Exception:
            return None


class SVGExporter(IRouteExporter):
    """SVG file exporter using svg_exporter module"""

    @property
    def name(self) -> str:
        return "SVG Exporter"

    @property
    def file_extensions(self) -> List[str]:
        return ['.svg']

    @property
    def file_description(self) -> str:
        return "SVG files"

    @property
    def default_extension(self) -> str:
        return '.svg'

    def export_routes(self,
                      routes: List[List[Tuple[float, float]]],
                      output_file: str,
                      **kwargs) -> bool:
        """Export routes to SVG file using svg_exporter"""
        try:
            return routes_to_svg(routes, output_file, **kwargs)
        except Exception:
            return False

    def get_export_options(self) -> Dict[str, Any]:
        """Get default SVG export options"""
        return {
            'width_mm': None,
            'height_mm': None,
            'margin_mm': 5.0,
            'stroke_width': 0.1,
            'stroke_color': 'black',
            'metadata': None
        }