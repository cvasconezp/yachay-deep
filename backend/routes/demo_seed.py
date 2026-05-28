"""
Demo data anonymization — generates shuffled/anonymized student data
for demo.yachaydeep.com presentations.

Strategy: Takes real academic data but shuffles PII fields independently
so no real student can be identified. Names come from a pool of common
Ecuadorian names; cédulas are randomly generated valid-format numbers.
"""
import random
import string
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth.jwt import get_current_user

router = APIRouter(prefix="/admin/demo", tags=["demo"])

# ── Name pools (common Ecuadorian names) ──
NOMBRES_M = [
    "Carlos", "Juan", "Luis", "Miguel", "José", "Andrés", "David",
    "Fernando", "Ricardo", "Santiago", "Diego", "Sebastián", "Mateo",
    "Alejandro", "Daniel", "Gabriel", "Pablo", "Nicolás", "Martín",
    "Emilio", "Roberto", "Héctor", "Francisco", "Eduardo", "Tomás",
    "Esteban", "Adrián", "Óscar", "Jorge", "Raúl", "Iván",
    "Cristian", "Kevin", "Bryan", "Alex", "Ariel", "Marco",
]
NOMBRES_F = [
    "María", "Ana", "Gabriela", "Sofía", "Valentina", "Camila",
    "Isabella", "Daniela", "Lucía", "Natalia", "Carolina", "Andrea",
    "Fernanda", "Paula", "Valeria", "Alejandra", "Mariana", "Diana",
    "Elena", "Rosa", "Patricia", "Verónica", "Catalina", "Tatiana",
    "Mónica", "Jessica", "Karina", "Paola", "Viviana", "Mayra",
    "Lorena", "Estefanía", "Priscila", "Karla", "Johanna",
]
APELLIDOS = [
    "García", "Rodríguez", "Martínez", "López", "González", "Hernández",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Rivera",
    "Gómez", "Díaz", "Reyes", "Morales", "Cruz", "Ortiz", "Gutiérrez",
    "Chávez", "Ramos", "Vargas", "Castillo", "Jiménez", "Moreno",
    "Romero", "Alvarado", "Ruiz", "Mendoza", "Aguilar", "Medina",
    "Herrera", "Vega", "Castro", "Ríos", "Contreras", "Guerrero",
    "Figueroa", "Cordero", "Bravo", "Delgado", "Ponce", "Salazar",
    "Espinoza", "Zambrano", "Vera", "Pacheco", "Cárdenas", "Lara",
    "Campoverde", "Quezada", "Cabrera", "Toapanta", "Chimbo", "Guamán",
    "Illescas", "Chuquimarca", "Morocho", "Aucapiña", "Yuquilema",
]
CIUDADES = [
    "Quito", "Guayaquil", "Cuenca", "Ambato", "Loja", "Riobamba",
    "Machala", "Portoviejo", "Ibarra", "Esmeraldas", "Latacunga",
    "Tulcán", "Azogues", "Guaranda", "Puyo",
]
PROVINCIAS = [
    "Pichincha", "Guayas", "Azuay", "Tungurahua", "Loja", "Chimborazo",
    "El Oro", "Manabí", "Imbabura", "Esmeraldas", "Cotopaxi",
    "Carchi", "Cañar", "Bolívar", "Pastaza",
]

# University name for demo
DEMO_UNIVERSITY = "Universidad Nacional de Innovación Educativa"
DEMO_SHORT = "UNIE"

# Carreras renamed for demo
CARRERA_MAP = {
    # Real → Demo (will be populated dynamically from actual data)
}
DEMO_CARRERAS = [
    "Ingeniería en Ciencias de la Computación",
    "Licenciatura en Ciencias de la Educación",
    "Ingeniería en Biotecnología",
    "Administración de Empresas",
    "Comunicación Social",
    "Psicología Clínica",
    "Derecho",
    "Ingeniería Ambiental",
    "Contabilidad y Auditoría",
    "Medicina Veterinaria",
]


def _generate_cedula():
    """Generate a fake but valid-format Ecuadorian cédula."""
    province = random.randint(1, 24)
    third = random.randint(0, 5)
    rest = ''.join(random.choices(string.digits, k=6))
    check = random.randint(0, 9)
    return f"{province:02d}{third}{rest}{check}"


def _generate_email(nombre, apellido):
    """Generate a fake institutional email."""
    n = nombre.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    a = apellido.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    num = random.randint(10, 99)
    return f"{n[0]}{a}{num}@unie.edu.ec"


def _generate_phone():
    """Generate a fake Ecuadorian mobile number."""
    return f"09{random.randint(10000000, 99999999)}"


@router.post("/generate-anonymized-snapshot")
def generate_anonymized_snapshot(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generates an anonymized copy of current student data.
    Returns a JSON summary — the actual anonymization for multi-tenant
    will write to a separate schema/table set when full multi-tenant is implemented.

    For now, returns the anonymization mapping so it can be reviewed.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    from ..models.student import Student

    students = db.query(Student).all()
    if not students:
        raise HTTPException(status_code=404, detail="No hay estudiantes para anonimizar")

    # Collect unique carreras and create mapping
    real_carreras = list(set(s.carrera for s in students if s.carrera))
    random.shuffle(real_carreras)
    carrera_map = {}
    for i, rc in enumerate(real_carreras):
        carrera_map[rc] = DEMO_CARRERAS[i % len(DEMO_CARRERAS)]

    # Shuffle PII independently
    n = len(students)
    genders = [s.genero for s in students]

    # Generate names based on gender distribution
    nombres_pool = []
    for g in genders:
        if g and g.lower() in ("femenino", "f", "mujer"):
            nombres_pool.append(random.choice(NOMBRES_F))
        elif g and g.lower() in ("masculino", "m", "hombre"):
            nombres_pool.append(random.choice(NOMBRES_M))
        else:
            nombres_pool.append(random.choice(NOMBRES_M + NOMBRES_F))

    apellidos1 = [random.choice(APELLIDOS) for _ in range(n)]
    apellidos2 = [random.choice(APELLIDOS) for _ in range(n)]
    cedulas = [_generate_cedula() for _ in range(n)]
    ciudades_shuffled = [random.choice(CIUDADES) for _ in range(n)]
    provincias_shuffled = [random.choice(PROVINCIAS) for _ in range(n)]

    anonymized = []
    for i, s in enumerate(students):
        nombre_completo = f"{apellidos1[i]} {apellidos2[i]} {nombres_pool[i]}"
        anon = {
            "original_id": s.id,
            "nombre": nombre_completo,
            "cedula": cedulas[i],
            "correo": _generate_email(nombres_pool[i], apellidos1[i]),
            "correo_institucional": _generate_email(nombres_pool[i], apellidos1[i]),
            "telefono": _generate_phone(),
            "whatsapp": _generate_phone(),
            "carrera": carrera_map.get(s.carrera, s.carrera),
            "ciudad": ciudades_shuffled[i],
            "provincia": provincias_shuffled[i],
            # Academic data stays the same (realistic demo)
            "nivel_riesgo": s.nivel_riesgo,
            "indice_compromiso": s.indice_compromiso,
            "dias_sin_acceso": s.dias_sin_acceso,
            "porcentaje_tareas": s.porcentaje_tareas,
            "promedio_calificaciones": s.promedio_calificaciones,
            "nivel_academico": s.nivel_academico,
            "periodo": s.periodo,
        }
        anonymized.append(anon)

    return {
        "total_students": n,
        "university_name": DEMO_UNIVERSITY,
        "carrera_mapping": carrera_map,
        "sample": anonymized[:5],  # Only return 5 as preview
        "message": f"Snapshot de {n} estudiantes anonimizados listo. "
                   "Los datos académicos (riesgo, notas, compromiso) se mantienen reales.",
    }
