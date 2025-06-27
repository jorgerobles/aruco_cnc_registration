import math
from xml.dom import minidom

from svgpathtools import svg2paths2


def scale_from_svg(svg_file):
    doc = minidom.parse(svg_file)
    svg_tag = doc.getElementsByTagName('svg')[0]

    view_box = svg_tag.getAttribute('viewBox')
    width = svg_tag.getAttribute('width')
    height = svg_tag.getAttribute('height')

    if not view_box or not width or not height:
        raise ValueError("El SVG debe tener viewBox, width y height definidos.")

    vb_x, vb_y, vb_width, vb_height = map(float, view_box.strip().split())
    width_mm = float(width.replace('mm', '').strip())
    height_mm = float(height.replace('mm', '').strip())

    escala_x = width_mm / vb_width
    escala_y = height_mm / vb_height
    return escala_x, escala_y


def convert_paths(path, num_points=50, angle_threshold=5):
    """
    Convierte los segmentos de un path a puntos, dividiendo solo cuando hay variación de ángulo.

    Args:
        path: Path SVG a convertir
        num_points: Número de puntos por segmento para el muestreo
        angle_threshold: Umbral de ángulo en grados para considerar un cambio significativo

    Returns:
        Lista de puntos donde cada punto es una tupla (x, y)
    """
    points = []

    # Extraer todos los puntos primero
    all_points = []
    for segmento in path:
        for t in [i / num_points for i in range(num_points + 1)]:
            punto = segmento.point(t)
            all_points.append((punto.real, punto.imag))

    # Si no hay suficientes puntos, retornar tal cual
    if len(all_points) <= 2:
        return all_points

    # El primer punto siempre va en la secuencia
    points.append(all_points[0])
    last_angle = None

    # Analizar cambios de dirección
    for i in range(len(all_points) - 1):
        p1 = all_points[i]
        p2 = all_points[i + 1]

        # Calcular dirección del vector
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]

        # Evitar divisiones por cero en segmentos muy pequeños
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            continue

        # Calcular ángulo en grados (0-360)
        current_angle = math.degrees(math.atan2(dy, dx)) % 360

        # Para el primer punto, solo establecer el ángulo inicial
        if last_angle is None:
            last_angle = current_angle
            continue

        # Calcular diferencia de ángulo (manejo el caso circular 0-360)
        diff = min(abs(current_angle - last_angle), 360 - abs(current_angle - last_angle))

        # Si hay cambio significativo de ángulo, marcar este punto
        if diff > angle_threshold:
            # Marcar este punto como punto de cambio de dirección
            points.append(p1)
            last_angle = current_angle

    # Asegurarse de que el último punto siempre esté incluido
    if all_points and points[-1] != all_points[-1]:
        points.append(all_points[-1])

    return points


def svg_to_routes(svg_file, angle_threshold=5):
    # Leer el SVG original para extraer viewBox, width y height
    doc = minidom.parse(svg_file)
    svg_tag = doc.getElementsByTagName('svg')[0]

    view_box = svg_tag.getAttribute('viewBox')
    width_attr = svg_tag.getAttribute('width')
    height_attr = svg_tag.getAttribute('height')

    if not view_box or not width_attr or not height_attr:
        raise ValueError("El SVG debe tener 'viewBox', 'width' y 'height' definidos.")

    vb_x, vb_y, vb_width, vb_height = map(float, view_box.strip().split())

    width = float(width_attr.replace("mm", "").strip())
    height = float(height_attr.replace("mm", "").strip())

    scale_x = width / vb_width
    scale_y = height / vb_height

    # Extraer paths
    paths, attributes, svg_attributes = svg2paths2(svg_file)

    routes = []
    for path in paths:
        points_raw = convert_paths(path, angle_threshold=angle_threshold)

        # Aplicar escala + traslación desde viewBox
        # Aquí transformamos las coordenadas para que el origen sea la esquina inferior izquierda
        # Por lo tanto, invertimos el eje Y (height - y) para cambiar la dirección
        points_trans = [
            ((x - vb_x) * scale_x, height - (y - vb_y) * scale_y) for x, y in points_raw
        ]
        routes.append(points_trans)

    return routes