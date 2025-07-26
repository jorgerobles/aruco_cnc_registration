"""
Dynamic Tkinter Form Generator (Updated)
Simplified - schemas now come from exporters directly
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional


class DynamicFormGenerator:
    """Generates tkinter forms from JSON schema definitions"""

    def __init__(self, parent, title: str, form_schema: Dict[str, Any], default_values: Dict[str, Any] = None):
        self.parent = parent
        self.title = title
        self.form_schema = form_schema
        self.default_values = default_values or {}
        self.result = None
        self.dialog = None
        self.widgets = {}

    def show(self) -> Optional[Dict[str, Any]]:
        """Show dialog and return form values or None if cancelled"""
        self._create_dialog()
        self._create_form()
        self.dialog.wait_window()
        return self.result

    def _create_dialog(self):
        """Create the dialog window"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self.title)
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(self.parent)

        # Calculate size based on form complexity
        width = self.form_schema.get('width', 400)
        height = self.form_schema.get('height', 300)
        self.dialog.geometry(f"{width}x{height}")

    def _create_form(self):
        """Create form widgets from schema"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create form sections
        for section in self.form_schema.get('sections', []):
            self._create_section(main_frame, section)

        # Create buttons
        self._create_buttons(main_frame)

    def _create_section(self, parent, section_schema: Dict[str, Any]):
        """Create a form section with fields"""
        section_frame = ttk.LabelFrame(parent, text=section_schema.get('title', ''))
        section_frame.pack(fill=tk.X, pady=5)

        for row, field in enumerate(section_schema.get('fields', [])):
            self._create_field(section_frame, field, row)

    def _create_field(self, parent, field_schema: Dict[str, Any], row: int):
        """Create a single form field"""
        field_name = field_schema['name']
        field_type = field_schema['type']
        label_text = field_schema.get('label', field_name)
        default_value = self.default_values.get(field_name, field_schema.get('default', ''))

        # Create label
        ttk.Label(parent, text=label_text).grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=2
        )

        # Create widget based on type
        widget = self._create_widget(parent, field_type, field_schema, default_value)
        widget.grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)

        self.widgets[field_name] = {
            'widget': widget,
            'type': field_type,
            'schema': field_schema
        }

    def _create_widget(self, parent, field_type: str, field_schema: Dict[str, Any], default_value: Any):
        """Create appropriate widget based on field type"""

        if field_type == 'string':
            var = tk.StringVar(value=str(default_value))
            widget = ttk.Entry(parent, textvariable=var, width=field_schema.get('width', 15))
            widget.var = var
            return widget

        elif field_type == 'number':
            var = tk.StringVar(value=str(default_value))
            widget = ttk.Entry(parent, textvariable=var, width=field_schema.get('width', 10))
            widget.var = var
            return widget

        elif field_type == 'float':
            var = tk.StringVar(value=str(default_value))
            widget = ttk.Entry(parent, textvariable=var, width=field_schema.get('width', 10))
            widget.var = var
            return widget

        elif field_type == 'boolean':
            var = tk.BooleanVar(value=bool(default_value))
            widget = ttk.Checkbutton(parent, variable=var)
            widget.var = var
            return widget

        elif field_type == 'choice':
            var = tk.StringVar(value=str(default_value))
            widget = ttk.Combobox(
                parent,
                textvariable=var,
                values=field_schema.get('options', []),
                state='readonly',
                width=field_schema.get('width', 12)
            )
            widget.var = var
            return widget

        elif field_type == 'optional_number':
            var = tk.StringVar(value=str(default_value) if default_value else '')
            widget = ttk.Entry(parent, textvariable=var, width=field_schema.get('width', 10))
            widget.var = var
            return widget

        else:
            # Default to string entry
            var = tk.StringVar(value=str(default_value))
            widget = ttk.Entry(parent, textvariable=var, width=15)
            widget.var = var
            return widget

    def _create_buttons(self, parent):
        """Create OK/Cancel buttons"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

    def _on_ok(self):
        """Handle OK button - validate and collect values"""
        try:
            values = {}

            for field_name, widget_info in self.widgets.items():
                widget = widget_info['widget']
                field_type = widget_info['type']
                field_schema = widget_info['schema']

                raw_value = widget.var.get()

                # Convert and validate based on type
                if field_type == 'number':
                    if raw_value.strip():
                        values[field_name] = int(raw_value)
                    elif field_schema.get('required', False):
                        raise ValueError(f"{field_schema.get('label', field_name)} is required")

                elif field_type == 'float':
                    if raw_value.strip():
                        values[field_name] = float(raw_value)
                    elif field_schema.get('required', False):
                        raise ValueError(f"{field_schema.get('label', field_name)} is required")

                elif field_type == 'optional_number':
                    if raw_value.strip():
                        values[field_name] = float(raw_value)
                    # Optional fields can be None/empty

                elif field_type == 'boolean':
                    values[field_name] = raw_value

                else:  # string, choice
                    if raw_value.strip() or not field_schema.get('required', False):
                        values[field_name] = raw_value
                    else:
                        raise ValueError(f"{field_schema.get('label', field_name)} is required")

            self.result = values
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))

    def _on_cancel(self):
        """Handle Cancel button"""
        self.result = None
        self.dialog.destroy()


def create_generic_schema(default_options: Dict[str, Any]) -> Dict[str, Any]:
    """Generate generic schema from default options for exporters without custom schema"""
    fields = []

    for key, value in default_options.items():
        field_type = "string"
        if isinstance(value, bool):
            field_type = "boolean"
        elif isinstance(value, int):
            field_type = "number"
        elif isinstance(value, float):
            field_type = "float"
        elif value is None:
            field_type = "optional_number"

        fields.append({
            "name": key,
            "type": field_type,
            "label": f"{key.replace('_', ' ').title()}:",
            "default": value if value is not None else "",
            "width": 12
        })

    return {
        "title": "Export Options",
        "width": 350,
        "height": min(400, 150 + len(fields) * 35),
        "sections": [
            {
                "title": "Parameters",
                "fields": fields
            }
        ]
    }