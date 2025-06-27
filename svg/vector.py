import math


def angle(x0, y0, x1, y1):
    """
    Calculates the angle change between two points.

    Args:
      x0: X coordinate of the previous point.
      y0: Y coordinate of the previous point.
      x1: X coordinate of the current point.
      y1: Y coordinate of the current point.

    Returns:
      The angle change in degrees.
    """
    dx = x1 - x0
    dy = y1 - y0
    angle_radians = math.atan2(dy, dx)
    angle_degrees = math.degrees(angle_radians)
    return angle_degrees


def angle_diff(angle1, angle2):
    """
    Calcula la diferencia más corta entre dos ángulos en grados.

    Args:
        angle1: Primer ángulo en grados
        angle2: Segundo ángulo en grados

    Returns:
        float: La diferencia angular más corta en grados (entre -180 y 180)
    """
    # Normalizar los ángulos a un rango de 0 a 360 grados
    angle1 = angle1 % 360
    angle2 = angle2 % 360

    # Calcular la diferencia
    diferencia = angle2 - angle1

    # Ajustar para obtener el camino más corto
    if diferencia > 180:
        diferencia -= 360
    elif diferencia < -180:
        diferencia += 360

    return diferencia


def shift(x1, y1, x2, y2, amount):
    """
    Desplaza el punto (x1, y1) en la dirección del vector desde
    (x1, y1) hacia (x2, y2), con una magnitud igual a 'amount'.

    Args:
        x1, y1: Coordenadas del punto a desplazar
        x2, y2: Coordenadas del punto que define la dirección
        amount: Distancia de desplazamiento

    Returns:
        tuple: Las nuevas coordenadas (x, y) del punto desplazado
    """
    # Calcular el vector dirección
    dx = x2 - x1
    dy = y2 - y1

    # Calcular la distancia entre los puntos
    distancia = math.sqrt(dx ** 2 + dy ** 2)

    # Evitar división por cero
    if distancia == 0:
        return x1, y1  # No hay desplazamiento si los puntos son iguales

    # Normalizar el vector (convertirlo en vector unitario)
    dx_unitario = dx / distancia
    dy_unitario = dy / distancia

    # Calcular las nuevas coordenadas
    dx1 = x1 + dx_unitario * amount
    dy1 = y1 + dy_unitario * amount
    dx2 = x2 + dx_unitario * amount
    dy2 = y2 + dy_unitario * amount

    return dx1, dy1, dx2, dy2