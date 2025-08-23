**Controls Layout:**
```
Routes:
  [Load SVG File]  [Clear Routes]
  Status: "X routes loaded (Y points)"

Registration Points:  
  [Load NPZ File]  [Export to YAML]  [Clear Registration]
  Status: "X points loaded"

Transformation:
  [Apply Rigid Transform]
  [Apply Affine Transform] 
  [Clear Transform]
  Status: "Method transform applied (X routes)"

Debug Info:
  [Show Transform Matrix]
```# Route Transformation Debugger

A clean, lean debugging application for testing SVG route transformation using triangle matching with registration points.

## Features

- **SVG Route Loading**: Load and visualize SVG files as routes
- **NPZ Registration**: Load registration point data from NPZ files  
- **YAML Export**: Export registration data to human-readable YAML
- **Triangle Transformation**: Apply triangle-based coordinate transformation with two methods:
  - **Rigid transformation**: Rotation + translation only (preserves shape/size)
  - **Affine transformation**: Rotation + translation + scaling + shearing (handles shape/size differences)
- **Interactive Canvas**: Machine coordinate visualization with:
  - **Zoom**: Mouse wheel to zoom in/out (0.1x to 20x)
  - **Pan**: Click and drag to move around  
  - **Grid and coordinates**: Real-time coordinate display
  - **Keyboard shortcuts**: R=Reset view, F=Fit view
  - Automatic scaling of labels and elements with zoom level

## Architecture

Simple, event-free architecture with focused responsibilities:

- `Controller` - UI coordination and data flow
- `RouteLoader` - SVG parsing using svgpathtools (copied from svg_loader.py)
- `Registration` - NPZ loading and YAML export (references registration_manager.py)
- `Transformer` - Triangle transformation mathematics (references route_transformer.py)
- `Canvas` - Machine coordinate visualization (references window_machine_area_canvas.py)

## Installation

1. **Install dependencies**:
   ```bash
   pip install svgpathtools numpy pyyaml
   ```

2. **Ensure parent directory access** for reference algorithms (route_transformer.py, etc.)

## Usage

1. **Start Application**
   ```bash
   cd debug_app
   python main.py
   ```

2. **Load Data**
   - Click "Load SVG File" to load routes
   - Click "Load NPZ File" to load registration points

3. **Apply Transformation**
   - **"Apply Rigid Transform"** - Use rigid transformation (shape-preserving, rotation + translation only)
   - **"Apply Affine Transform"** - Use affine transformation (flexible scaling, rotation + translation + scaling)
   - Routes will be transformed using triangle matching with the selected method
   - Console output shows triangle analysis and recommendations

4. **Debug and Analyze**
   - Click "Show Transform Matrix" to see transformation details
   - Console output shows triangle segment analysis and method recommendations
   - Compare rigid vs affine results for best alignment

4. **Interactive Navigation**
   - **Mouse wheel**: Zoom in/out for precise inspection
   - **Click + drag**: Pan around the canvas
   - **R key**: Reset view to default
   - **F key**: Fit view (currently same as reset)
   - Watch coordinate readout in status bar

5. **Export/Debug**
   - Click "Export to YAML" to save registration data in readable format
   - View transformation results in the visualization canvas

## Coordinate System

- **Machine Bounds**: 450mm × 450mm
- **Origin**: Top-right corner (0, 0)
- **Extent**: X-axis extends left (0 to -450), Y-axis extends down (0 to -450)
- **Grid**: Major lines every 50mm, minor lines every 10mm

## File Formats

### SVG Input
- Standard SVG files with path elements
- **Uses svgpathtools for robust parsing** (same as reference codebase)
- Automatically skips hidden elements (`display="none"`)
- Supports all SVG path commands (M, L, H, V, C, S, Q, T, A, Z)
- Handles curves, arcs, and complex paths accurately
- Proper viewBox, width, height scaling

### NPZ Input (Registration Points)
Multiple formats supported:
- `machine_positions`, `camera_positions` arrays
- `calibration_points` array of tuples  
- Individual `point_0`, `point_1`, ... entries

### YAML Output (Registration Export)
```yaml
registration_info:
  point_count: 3
  format: 2D
  coordinate_system: machine_coordinates
points:
  - point_id: 1
    machine_position: {x: -100.0, y: -100.0}
    camera_position: {x: 320.0, y: 240.0}
    normalized_position: {u: 0.5, v: 0.5}
```

## Transformation Methods

### **Rigid Transformation**
- **Use when**: Registration triangles are very similar in size/shape (< 1mm differences)
- **Preserves**: Shape, size, angles - only rotates and translates
- **Best for**: High-precision calibrated systems
- **Limitations**: Cannot handle scaling differences

### **Affine Transformation** 
- **Use when**: Registration triangles differ in size/shape (> 1mm differences)  
- **Handles**: Scaling, rotation, translation, and minor shearing
- **Best for**: Real-world calibration with measurement variations
- **More flexible**: Accommodates imperfect triangle correspondence

**The debug output will recommend which method to use based on triangle analysis.**

## Interactive Visualization

**Zoom and Pan Controls:**
- **Mouse wheel**: Zoom in/out (0.1x to 20x zoom range)
- **Click + drag**: Pan around the canvas
- **R key**: Reset to default view
- **Status bar**: Shows current mouse coordinates and zoom level

**Zoom-Responsive Elements:**
- Grid lines and labels appear/disappear based on zoom level
- Text size scales with zoom for readability
- Line widths and point sizes adapt to zoom level
- Minor grid lines only visible when zoomed in

**Visualization Elements:**
- **Original Routes**: Orange/green/red/purple/teal colors with R1, R2, R3... labels
- **Transformed Routes**: Darker colors with T1, T2, T3... labels  
- **Registration Points**: Red diamonds with P1, P2, P3... labels
- **Source Triangle**: Blue dashed triangle from route bounding box
- **Destination Triangle**: Red solid triangle from first 3 registration points
- **Route Endpoints**: Green circles (start), red squares (end)
- **Machine bounds**: 450×450mm area with grid and origin marker

## Dependencies

- Python 3.6+
- tkinter (usually included with Python)
- **svgpathtools** - Robust SVG path parsing (same as reference codebase)
- numpy - Numerical computations and transformations
- PyYAML - YAML export functionality
- Access to parent directory modules for reference algorithms

## Error Handling

- File validation before loading
- Clear error messages for invalid data
- Graceful handling of malformed files
- Coordinate conversion error protection