"""
Constantes compartidas del backend — mapeos de sedes EIB, umbrales, etc.
Fuente única de verdad para evitar inconsistencias entre módulos.
"""

# Mapeo grupo EIB → Centro de apoyo (sede)
# Basado en la estructura académica de la carrera EIB de la UPS
EIB_GRUPO_SEDE = {
    1: "Latacunga",
    2: "Cayambe",
    3: "Otavalo",
    4: "Riobamba",
    5: "Amazonía Norte",
    6: "Wasakentsa",
}

# Versión string-key para uso con datos que vienen como texto
EIB_GRUPO_SEDE_STR = {str(k): v for k, v in EIB_GRUPO_SEDE.items()}
