"""
Controller - Main UI coordinator
Clean implementation with direct method calls, no events
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os

from route_loader import RouteLoader
from registration import Registration
from transformer import Transformer
from canvas import Canvas


class DebugLogger:
    """Simple logger wrapper for consistent logging"""

    def __init__(self, logger):
        self.logger = logger

    def info(self, message: str):
        """Log info message"""
        if self.logger:
            self.logger.info(f"[DEBUG] {message}")

    def warning(self, message: str):
        """Log warning message"""
        if self.logger:
            self.logger.warning(f"[DEBUG] {message}")

    def error(self, message: str):
        """Log error message"""
        if self.logger:
            self.logger.error(f"[DEBUG] {message}")


class Controller:
    """Main controller - coordinates UI and data flow"""

    def __init__(self, root, logger):
        self.root = root
        self.logger = logger

        # Components
        self.route_loader = RouteLoader()
        self.registration = Registration()
        self.transformer = Transformer()
        self.canvas = None

        # Data
        self.routes = []
        self.registration_points = []
        self.transformed_routes = []
        self.source_triangle = None
        self.destination_triangle = None

        # UI
        self.create_ui()
        self.update_status()

        self.logger.info("Controller initialized")

    def create_ui(self):
        """Create main UI layout"""
        # Main paned window
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - controls
        left_frame = ttk.Frame(paned, width=280)
        paned.add(left_frame, weight=0)

        # Right panel - canvas
        canvas_frame = ttk.Frame(paned)
        paned.add(canvas_frame, weight=1)

        self.create_controls(left_frame)
        self.create_canvas(canvas_frame)
        self.create_status_bar()

    def create_controls(self, parent):
        """Create control buttons and info"""
        # Title
        ttk.Label(parent, text="Route Transform Debugger",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Routes section
        routes_frame = ttk.LabelFrame(parent, text="SVG Routes")
        routes_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(routes_frame, text="Load SVG File",
                  command=self.load_svg_clicked).pack(fill=tk.X, padx=5, pady=2)

        self.routes_info = tk.StringVar(value="No routes loaded")
        ttk.Label(routes_frame, textvariable=self.routes_info).pack(padx=5, pady=2)

        ttk.Button(routes_frame, text="Clear Routes",
                  command=self.clear_routes_clicked).pack(fill=tk.X, padx=5, pady=2)

        # Registration section
        reg_frame = ttk.LabelFrame(parent, text="Registration Points")
        reg_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(reg_frame, text="Load NPZ File",
                  command=self.load_npz_clicked).pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(reg_frame, text="Export to YAML",
                  command=self.export_yaml_clicked).pack(fill=tk.X, padx=5, pady=2)

        self.registration_info = tk.StringVar(value="No registration loaded")
        ttk.Label(reg_frame, textvariable=self.registration_info).pack(padx=5, pady=2)

        ttk.Button(reg_frame, text="Clear Registration",
                  command=self.clear_registration_clicked).pack(fill=tk.X, padx=5, pady=2)

        # Transform section
        transform_frame = ttk.LabelFrame(parent, text="Transformation")
        transform_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(transform_frame, text="Apply Rigid Transform",
                  command=self.rigid_transform_clicked).pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(transform_frame, text="Apply Affine Transform",
                   command=self.affine_transform_clicked).pack(fill=tk.X, padx=5, pady=2)

        self.transform_info = tk.StringVar(value="Ready")
        ttk.Label(transform_frame, textvariable=self.transform_info).pack(padx=5, pady=2)

        ttk.Button(transform_frame, text="Clear Transform",
                  command=self.clear_transform_clicked).pack(fill=tk.X, padx=5, pady=2)

    def create_canvas(self, parent):
        """Create visualization canvas"""
        self.canvas = Canvas(parent)

    def create_status_bar(self):
        """Create status bar"""
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(side=tk.BOTTOM, fill=tk.X)

    # Button handlers - direct method calls
    def load_svg_clicked(self):
        """Load SVG file"""
        file_path = filedialog.askopenfilename(
            title="Load SVG Routes",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            self.routes = self.route_loader.load_svg_file(
                file_path,
                angle_threshold=5.0,  # Standard angle threshold
                skip_display_none=True  # Skip hidden SVG elements
            )

            if self.routes:
                self.logger.info(f"Loaded {len(self.routes)} routes from {os.path.basename(file_path)}")
                self.update_display()
            else:
                messagebox.showerror("Error", "No routes found in SVG file")

        except Exception as e:
            self.logger.error(f"Error loading SVG: {e}")
            messagebox.showerror("Error", f"Failed to load SVG: {e}")

    def load_npz_clicked(self):
        """Load NPZ registration file"""
        file_path = filedialog.askopenfilename(
            title="Load Registration Points",
            filetypes=[("NPZ files", "*.npz"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            self.registration_points = self.registration.load_npz_file(file_path)

            if self.registration_points:
                self.logger.info(f"Loaded {len(self.registration_points)} registration points")
                self.update_display()
            else:
                messagebox.showerror("Error", "No registration points found in NPZ file")

        except Exception as e:
            self.logger.error(f"Error loading NPZ: {e}")
            messagebox.showerror("Error", f"Failed to load NPZ: {e}")

    def export_yaml_clicked(self):
        """Export registration to YAML"""
        if not self.registration_points:
            messagebox.showwarning("Warning", "No registration points to export")
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Registration to YAML",
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            success = self.registration.export_yaml(self.registration_points, file_path)

            if success:
                messagebox.showinfo("Success", f"Exported to {os.path.basename(file_path)}")
            else:
                messagebox.showerror("Error", "Failed to export YAML")

        except Exception as e:
            self.logger.error(f"Error exporting YAML: {e}")
            messagebox.showerror("Error", f"Failed to export: {e}")

    def rigid_transform_clicked(self):
        """Apply rigid transformation"""
        self._apply_transformation("rigid")

    def affine_transform_clicked(self):
        """Apply affine transformation"""
        self._apply_transformation("affine")

    def _apply_transformation(self, method):
        """Apply transformation with specified method"""
        if not self.routes:
            messagebox.showwarning("Warning", "No routes loaded")
            return

        if not self.registration_points:
            messagebox.showwarning("Warning", "No registration points loaded")
            return

        try:
            # Get triangles
            self.source_triangle = self.transformer.get_source_triangle(self.routes)
            self.destination_triangle = self.registration.get_triangle_points(self.registration_points)

            if not self.source_triangle or not self.destination_triangle:
                messagebox.showerror("Error", "Failed to compute triangles")
                return

            # Store current method
            self.current_transform_method = method

            # DEBUG: Analyze triangle segments before transformation
            self._debug_triangle_segments(method)

            # Apply transformation with selected method
            self.transformed_routes = self.transformer.transform_routes(
                self.routes, self.destination_triangle, method=method
            )

            if self.transformed_routes:
                # Get transformation info for display
                transform_info = self.transformer.get_transformation_info(
                    self.source_triangle, self.destination_triangle, method=method
                )

                # Store for debug display
                self.last_transform_info = transform_info

                self.logger.info(f"{method.capitalize()} transformation applied to {len(self.routes)} routes")
                if 'rms_error' in transform_info:
                    self.logger.info(f"RMS Error: {transform_info['rms_error']:.4f}mm")

                self.update_display()
            else:
                messagebox.showerror("Error", "Transformation failed")

        except Exception as e:
            self.logger.error(f"Error applying transformation: {e}")
            messagebox.showerror("Error", f"Transformation failed: {e}")

    def _debug_triangle_segments(self, method):
        """Debug triangle segment lengths to detect transformation issues"""
        try:
            self.logger.info("=" * 60)
            self.logger.info(f"TRIANGLE SEGMENT ANALYSIS - {method.upper()} TRANSFORMATION")
            self.logger.info("=" * 60)

            # Calculate source triangle segments
            src_segments = self._calculate_triangle_segments(self.source_triangle, "Source Triangle")

            # Calculate destination triangle segments
            dst_segments = self._calculate_triangle_segments(self.destination_triangle, "Destination Triangle")

            # Compare segment lengths
            self.logger.info("\nSEGMENT LENGTH COMPARISON:")
            self.logger.info("-" * 40)

            segment_names = ["P1→P2", "P1→P3", "P2→P3"]
            max_diff = 0.0
            total_diff = 0.0

            for i, name in enumerate(segment_names):
                src_len = src_segments[i]
                dst_len = dst_segments[i]
                diff = abs(dst_len - src_len)
                diff_percent = (diff / src_len * 100) if src_len > 0 else 0

                self.logger.info(f"{name}: Source={src_len:.3f}mm, Dest={dst_len:.3f}mm, Diff={diff:.3f}mm ({diff_percent:.2f}%)")

                max_diff = max(max_diff, diff)
                total_diff += diff

            # Analysis based on transformation method
            self.logger.info(f"\nANALYSIS FOR {method.upper()} TRANSFORMATION:")
            self.logger.info(f"Maximum difference: {max_diff:.3f}mm")
            self.logger.info(f"Average difference: {total_diff/3:.3f}mm")

            if method == "rigid":
                if max_diff > 1.0:  # More than 1mm difference
                    self.logger.warning("⚠️  LARGE SEGMENT DIFFERENCES DETECTED!")
                    self.logger.warning("For rigid transformation, segments should be identical.")
                    self.logger.info("💡 Consider using AFFINE transformation instead.")
                elif max_diff > 0.1:  # More than 0.1mm difference
                    self.logger.warning("⚠️  Small segment differences detected.")
                    self.logger.warning("This may cause alignment issues with rigid transformation.")
                else:
                    self.logger.info("✅ Triangle segments match well - rigid transformation should work correctly.")
            else:  # affine
                self.logger.info("ℹ️  Using affine transformation - can handle scaling and shape differences.")
                if max_diff > 50.0:  # Very large differences
                    self.logger.warning("⚠️  Very large shape differences - check triangle correspondence.")
                else:
                    self.logger.info("✅ Affine transformation should handle these differences well.")

            # Additional debug info
            self._debug_triangle_properties()

        except Exception as e:
            self.logger.error(f"Error in triangle segment debug: {e}")

    def show_transform_matrix(self):
        """Show transformation matrix and details"""
        if hasattr(self, 'last_transform_info') and self.last_transform_info:
            info = self.last_transform_info

            if 'error' in info:
                messagebox.showerror("Error", f"No transformation data: {info['error']}")
                return

            method = info.get('method', 'unknown')

            # Format transformation details
            details = [f"Transformation Method: {method.upper()}"]

            if method == "affine":
                details.extend([
                    "",
                    "Affine Transformation Matrix:",
                    f"{info.get('transformation_matrix', 'N/A')}",
                    "",
                    f"Translation: ({info.get('translation', [0, 0])[0]:.3f}, {info.get('translation', [0, 0])[1]:.3f}) mm",
                    f"Scale X: {info.get('scale_x', 1.0):.6f}",
                    f"Scale Y: {info.get('scale_y', 1.0):.6f}",
                    f"Rotation: {info.get('rotation_angle_degrees', 0):.3f}°",
                    f"Determinant: {info.get('determinant', 1.0):.6f}",
                ])
            else:  # rigid
                details.extend([
                    "",
                    f"Rotation Matrix:",
                    f"{info.get('rotation_matrix', 'N/A')}",
                    "",
                    f"Translation: {info.get('translation_vector', 'N/A')} mm",
                    f"Rotation Angle: {info.get('rotation_angle_degrees', 0):.3f}°",
                    f"Translation Distance: {info.get('translation_distance', 0):.3f} mm",
                ])

            details.extend([
                "",
                f"RMS Error: {info.get('rms_error', 0):.4f} mm"
            ])

            messagebox.showinfo("Transformation Details", "\n".join(details))
        else:
            messagebox.showinfo("Transformation Matrix", "No transformation applied yet")

    def _calculate_triangle_segments(self, triangle, name):
        """Calculate the three segment lengths of a triangle"""
        try:
            self.logger.info(f"\n{name}:")

            p1, p2, p3 = triangle
            self.logger.info(f"  P1: ({p1[0]:.3f}, {p1[1]:.3f})")
            self.logger.info(f"  P2: ({p2[0]:.3f}, {p2[1]:.3f})")
            self.logger.info(f"  P3: ({p3[0]:.3f}, {p3[1]:.3f})")

            # Calculate segment lengths
            seg_p1_p2 = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
            seg_p1_p3 = ((p3[0] - p1[0])**2 + (p3[1] - p1[1])**2)**0.5
            seg_p2_p3 = ((p3[0] - p2[0])**2 + (p3[1] - p2[1])**2)**0.5

            self.logger.info(f"  Segments: P1→P2={seg_p1_p2:.3f}mm, P1→P3={seg_p1_p3:.3f}mm, P2→P3={seg_p2_p3:.3f}mm")

            return [seg_p1_p2, seg_p1_p3, seg_p2_p3]

        except Exception as e:
            self.logger.error(f"Error calculating segments for {name}: {e}")
            return [0, 0, 0]

    def _debug_triangle_properties(self):
        """Additional triangle debugging info"""
        try:
            self.logger.info(f"\nADDITIONAL TRIANGLE PROPERTIES:")
            self.logger.info("-" * 40)

            # Source triangle area and centroid
            src_area = self._calculate_triangle_area(self.source_triangle)
            src_centroid = self._calculate_triangle_centroid(self.source_triangle)

            # Destination triangle area and centroid
            dst_area = self._calculate_triangle_area(self.destination_triangle)
            dst_centroid = self._calculate_triangle_centroid(self.destination_triangle)

            self.logger.info(f"Source area: {src_area:.3f} mm²")
            self.logger.info(f"Destination area: {dst_area:.3f} mm²")
            self.logger.info(f"Area ratio: {dst_area/src_area:.6f}" if src_area > 0 else "Area ratio: undefined")

            self.logger.info(f"Source centroid: ({src_centroid[0]:.3f}, {src_centroid[1]:.3f})")
            self.logger.info(f"Destination centroid: ({dst_centroid[0]:.3f}, {dst_centroid[1]:.3f})")

            # Distance between centroids
            centroid_dist = ((dst_centroid[0] - src_centroid[0])**2 + (dst_centroid[1] - src_centroid[1])**2)**0.5
            self.logger.info(f"Centroid distance: {centroid_dist:.3f}mm")

        except Exception as e:
            self.logger.error(f"Error calculating triangle properties: {e}")

    def _calculate_triangle_area(self, triangle):
        """Calculate triangle area using cross product"""
        try:
            p1, p2, p3 = triangle
            # Vector from p1 to p2 and p1 to p3
            v1 = (p2[0] - p1[0], p2[1] - p1[1])
            v2 = (p3[0] - p1[0], p3[1] - p1[1])
            # Cross product magnitude / 2
            cross = abs(v1[0] * v2[1] - v1[1] * v2[0])
            return cross / 2.0
        except Exception:
            return 0.0

    def _calculate_triangle_centroid(self, triangle):
        """Calculate triangle centroid"""
        try:
            p1, p2, p3 = triangle
            centroid_x = (p1[0] + p2[0] + p3[0]) / 3
            centroid_y = (p1[1] + p2[1] + p3[1]) / 3
            return (centroid_x, centroid_y)
        except Exception:
            return (0.0, 0.0)

    def clear_routes_clicked(self):
        """Clear routes"""
        self.routes = []
        self.transformed_routes = []
        self.source_triangle = None
        self.update_display()

    def clear_registration_clicked(self):
        """Clear registration"""
        self.registration_points = []
        self.destination_triangle = None
        self.update_display()

    def clear_transform_clicked(self):
        """Clear transformation results"""
        self.transformed_routes = []
        self.source_triangle = None
        self.destination_triangle = None
        self.current_transform_method = None
        self.last_transform_info = None
        self.update_display()

    def update_display(self):
        """Update all display elements"""
        self.update_status()
        self.update_canvas()

    def update_status(self):
        """Update status text"""
        # Routes info
        if self.routes:
            routes_text = f"{len(self.routes)} routes loaded"
            total_points = sum(len(route) for route in self.routes)
            routes_text += f" ({total_points} points)"
        else:
            routes_text = "No routes loaded"
        self.routes_info.set(routes_text)

        # Registration info
        if self.registration_points:
            reg_text = f"{len(self.registration_points)} points loaded"
        else:
            reg_text = "No registration loaded"
        self.registration_info.set(reg_text)

        # Transform info
        if self.transformed_routes:
            method_name = self.current_transform_method or "unknown"
            transform_text = f"{method_name.capitalize()} transform applied ({len(self.transformed_routes)} routes)"
        elif self.routes and self.registration_points:
            transform_text = "Ready to transform"
        else:
            transform_text = "Need routes + registration"
        self.transform_info.set(transform_text)

        # Status bar
        status_parts = []
        if self.routes:
            status_parts.append(f"{len(self.routes)} routes")
        if self.registration_points:
            status_parts.append(f"{len(self.registration_points)} reg points")
        if self.transformed_routes:
            status_parts.append("transformed")

        if status_parts:
            self.status_var.set(" | ".join(status_parts))
        else:
            self.status_var.set("Ready - Load routes and registration")

    def update_canvas(self):
        """Update canvas visualization"""
        if self.canvas:
            self.canvas.update_visualization(
                original_routes=self.routes,
                transformed_routes=self.transformed_routes,
                registration_points=self.registration_points,
                source_triangle=self.source_triangle,
                destination_triangle=self.destination_triangle
            )