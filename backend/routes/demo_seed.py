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


@router.post("/seed-demo-db")
def seed_demo_database(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Copies students from production DB to demo DB with anonymized PII.
    Also creates a demo admin user.
    Academic data (risk, grades, engagement) stays realistic.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    from ..database import DemoSessionLocal, demo_engine
    if not DemoSessionLocal or not demo_engine:
        raise HTTPException(status_code=503, detail="DEMO_DATABASE_URL no configurada en Railway")

    from ..models.student import Student
    from ..models.user import User, UserRole
    from ..auth.jwt import hash_password

    # Read production students
    students = db.query(Student).all()
    if not students:
        raise HTTPException(status_code=404, detail="No hay estudiantes en producción")

    # Build carrera mapping
    real_carreras = list(set(s.carrera for s in students if s.carrera))
    random.shuffle(real_carreras)
    carrera_map = {}
    for i, rc in enumerate(real_carreras):
        carrera_map[rc] = DEMO_CARRERAS[i % len(DEMO_CARRERAS)]

    n = len(students)

    # Generate anonymized PII
    nombres_pool = []
    for s in students:
        g = s.genero
        if g and g.lower() in ("femenino", "f", "mujer"):
            nombres_pool.append(random.choice(NOMBRES_F))
        elif g and g.lower() in ("masculino", "m", "hombre"):
            nombres_pool.append(random.choice(NOMBRES_M))
        else:
            nombres_pool.append(random.choice(NOMBRES_M + NOMBRES_F))

    apellidos1 = [random.choice(APELLIDOS) for _ in range(n)]
    apellidos2 = [random.choice(APELLIDOS) for _ in range(n)]

    # Write to demo DB
    demo_db = DemoSessionLocal()
    try:
        # Clear existing demo students
        demo_db.query(Student).delete()
        demo_db.commit()

        for i, s in enumerate(students):
            nombre = f"{apellidos1[i]} {apellidos2[i]} {nombres_pool[i]}"
            demo_student = Student(
                cedula=_generate_cedula(),
                nombre=nombre,
                correo=_generate_email(nombres_pool[i], apellidos1[i]),
                correo_institucional=_generate_email(nombres_pool[i], apellidos1[i]),
                telefono=_generate_phone(),
                whatsapp=_generate_phone(),
                carrera=carrera_map.get(s.carrera, s.carrera),
                sede=s.sede,
                campus=s.campus,
                nivel_academico=s.nivel_academico,
                nivel_riesgo=s.nivel_riesgo,
                indice_compromiso=s.indice_compromiso,
                dias_sin_acceso=s.dias_sin_acceso,
                porcentaje_tareas=s.porcentaje_tareas,
                promedio_calificaciones=s.promedio_calificaciones,
                pais="Ecuador",
                provincia=random.choice(PROVINCIAS),
                ciudad=random.choice(CIUDADES),
                genero=s.genero,
                periodo=s.periodo,
                estado_matricula=s.estado_matricula,
                prob_desercion=s.prob_desercion,
                prob_reprobacion=s.prob_reprobacion,
                es_tercera_matricula=s.es_tercera_matricula,
                score_recuperabilidad=s.score_recuperabilidad,
                nivel_recuperabilidad=s.nivel_recuperabilidad,
            )
            demo_db.add(demo_student)

        # Create demo admin user (same password as production admin for convenience)
        existing_admin = demo_db.query(User).filter(User.role == UserRole.admin).first()
        if not existing_admin:
            import os
            admin_pass = os.environ.get("ADMIN_PASSWORD", "demo2026")
            demo_admin = User(
                email=current_user.email,
                nombre="Admin Demo",
                hashed_password=hash_password(admin_pass),
                role=UserRole.admin,
                is_active=True,
            )
            demo_db.add(demo_admin)

        demo_db.commit()

        return {
            "status": "success",
            "students_copied": n,
            "carreras_mapped": carrera_map,
            "demo_university": DEMO_UNIVERSITY,
            "admin_email": current_user.email,
            "message": f"{n} estudiantes anonimizados copiados a BD demo. "
                       f"Admin: {current_user.email} (misma contraseña).",
        }
    except Exception as e:
        demo_db.rollback()
        raise HTTPException(status_code=500, detail=f"Error seeding demo: {str(e)}")
    finally:
        demo_db.close()
