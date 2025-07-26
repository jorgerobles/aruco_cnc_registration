# services/io/form_schema_interface.py
"""
Interface for form schema providers
Allows exporters to define their own UI forms
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IFormSchemaProvider(ABC):
    """Interface for components that provide form schemas"""

    @abstractmethod
    def get_form_schema(self) -> Optional[Dict[str, Any]]:
        """
        Get form schema for this component

        Returns:
            Dictionary containing form schema or None for no custom form
        """
        pass