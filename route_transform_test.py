import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from services.route_transformer import RouteTransformer


# Formas generadas
def create_star(center, radius, points=5):
    angles = np.linspace(0, 2 * np.pi, points * 2, endpoint=False)
    r = np.array([radius, radius/2] * points)
    x = center[0] + r * np.cos(angles)
    y = center[1] + r * np.sin(angles)
    return np.stack((x, y), axis=1)

def create_irregular_polygon(center, radius, points=7):
    angles = np.linspace(0, 2 * np.pi, points, endpoint=False)
    r = radius * (0.5 + np.random.rand(points))
    x = center[0] + r * np.cos(angles)
    y = center[1] + r * np.sin(angles)
    return np.stack((x, y), axis=1)

# Rotar un conjunto de puntos alrededor de un origen
def rotate_points(points, angle_deg, origin):
    angle_rad = np.radians(angle_deg)
    R = np.array([
        [np.cos(angle_rad), -np.sin(angle_rad)],
        [np.sin(angle_rad),  np.cos(angle_rad)]
    ])
    return (R @ (points - origin).T).T + origin

# Crear formas originales
np.random.seed(0)
paths = [
    create_star((10, 10), 5),
    create_irregular_polygon((25, 15), 6)
]

# Triángulo destino base (orden convencional)
p1 = np.array([100, 100])       # origen
p2 = np.array([200, 100])       # eje X positivo
p3 = np.array([100, 200])       # eje Y positivo
triangle_base = np.array([p1, p2, p3])

# Rotarlo 45° alrededor del origen (p1)
triangle_rotado = rotate_points(triangle_base, 45, origin=p1)

# Aplicar transformación
rt = RouteTransformer(paths)
rt.transform_to(triangle_rotado)

# Visualización
fig, ax = plt.subplots(1, 2, figsize=(12, 6))

# Original
ax[0].set_title("Original")
for path in paths:
    ax[0].add_patch(Polygon(path, closed=True, fill=True, alpha=0.6))
ax[0].autoscale()
ax[0].set_aspect('equal')

# Transformado con rotación
ax[1].set_title("Transformado (45°)")
for path in rt.transformed_paths:
    ax[1].add_patch(Polygon(path, closed=True, fill=True, alpha=0.6))
# Dibujar triángulo destino rotado
x, y = zip(*triangle_rotado)
ax[1].plot(list(x) + [x[0]], list(y) + [y[0]], 'ro--', label='Triángulo destino')
ax[1].autoscale()
ax[1].set_aspect('equal')
ax[1].legend()

plt.tight_layout()
plt.show()
