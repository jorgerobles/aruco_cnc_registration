import sys

from svg_loader import svg_to_routes
from tangential import routes_to_gcode

def exportar_gcode(nombre_archivo, gcode_lines):
    with open(nombre_archivo, "w") as archivo:
        for linea in gcode_lines:
            archivo.write(linea + "\n")
    print(f"G-code exportado a: {nombre_archivo}")

if __name__ == "__main__":
    svg_path = sys.argv[1]
    output_file = sys.argv[2]

    rutas = svg_to_routes(svg_path)

    gcode_total = []
    for ruta in rutas:
        gcode = routes_to_gcode(ruta, initial_rotation=90, cut_depth=-0.3, offset=2.75, angle_threshold=30)
        gcode_total.extend(gcode)



    gcode_total.append("G0 Z5 ; Levantar cuchilla")
    gcode_total.append("G0 X0 Y0 ; Regresar al origen")
    gcode_total.append("M2 ; Fin del programa")



    exportar_gcode(output_file, gcode_total)