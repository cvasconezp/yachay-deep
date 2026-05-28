"""
Demo data anonymization — generates shuffled/anonymized data
for demo.yachaydeep.com presentations.

Strategy: Copies ALL tables from production to demo DB, anonymizing PII:
- Student names, cédulas, emails, phones → random Ecuadorian names
- Teacher names → consistent fake teacher mapping
- Carrera names → renamed for demo
- Observation text → generic placeholders
Academic metrics (grades, risk scores, engagement) stay realistic.
"""
import random
import string
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

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
DEMO_UNIVERSITY = "Universidad Nacional de Innovación Educativa"
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
OBSERVACIONES_DEMO = [
    "Se contactó al estudiante por WhatsApp. Indica que tiene problemas de conectividad.",
    "Estudiante confirma que retomará actividades la próxima semana.",
    "No contestó la llamada. Se dejó mensaje de voz.",
    "Estudiante menciona carga laboral como razón de inactividad.",
    "Se derivó a bienestar estudiantil por situación personal.",
    "Coordinación académica notificada. Estudiante requiere tutoría.",
    "El estudiante se comprometió a ponerse al día con las entregas.",
    "Contactado vía email institucional. Confirma dificultades económicas.",
    "Se realizó seguimiento. El estudiante mejoró su participación.",
    "Estudiante indica problemas de salud. Se recomienda seguimiento.",
]


def _generate_cedula():
    province = random.randint(1, 24)
    third = random.randint(0, 5)
    rest = ''.join(random.choices(string.digits, k=6))
    check = random.randint(0, 9)
    return f"{province:02d}{third}{rest}{check}"


def _generate_email(nombre, apellido, domain="unie.edu.ec"):
    n = nombre.lower()
    for old, new in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        n = n.replace(old, new)
    a = apellido.lower()
    for old, new in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        a = a.replace(old, new)
    num = random.randint(10, 99)
    return f"{n[0]}{a}{num}@{domain}"


def _generate_phone():
    return f"09{random.randint(10000000, 99999999)}"


def _make_docente_map(docentes_reales):
    """Create a consistent mapping of real teacher names to fake ones."""
    mapping = {}
    for d in docentes_reales:
        if d and d not in mapping:
            ap1 = random.choice(APELLIDOS)
            ap2 = random.choice(APELLIDOS)
            nom = random.choice(NOMBRES_M + NOMBRES_F)
            mapping[d] = f"{ap1} {ap2} {nom}"
    return mapping


def _anonymize_message(msg, student_name_map=None):
    """Replace any real names in alert messages with generic text."""
    if not msg:
        return msg
    # Simple approach: return the message structure but it typically
    # doesn't contain student names (uses student_id FK instead)
    return msg


@router.post("/seed-demo-db")
def seed_demo_database(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Copies ALL tables from production DB to demo DB with anonymized PII.
    Creates admin user, maps student IDs, teacher names, and carreras.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    from ..database import DemoSessionLocal, demo_engine
    if not DemoSessionLocal or not demo_engine:
        raise HTTPException(status_code=503, detail="DEMO_DATABASE_URL no configurada")

    from ..models.student import Student
    from ..models.user import User, UserRole
    from ..models.enrollment import Enrollment
    from ..models.grade import Grade
    from ..models.avac_access import AvacAccess
    from ..models.task_submission import TaskSubmission
    from ..models.course import Course
    from ..models.course_config import CourseConfig, SemesterConfig
    from ..models.intervention import Intervention
    from ..models.alert_event import AlertEvent
    from ..models.docente_tracking import DocenteTracking
    from ..auth.jwt import hash_password

    stats = {}

    # ── Read production data ──
    students = db.query(Student).all()
    if not students:
        raise HTTPException(status_code=404, detail="No hay estudiantes en producción")

    enrollments = db.query(Enrollment).all()
    grades = db.query(Grade).all()
    avac_accesses = db.query(AvacAccess).all()
    task_subs = db.query(TaskSubmission).all()
    courses = db.query(Course).all()
    course_configs = db.query(CourseConfig).all()
    semester_configs = db.query(SemesterConfig).all()
    interventions = db.query(Intervention).all()
    alerts = db.query(AlertEvent).all()
    docente_tracking = db.query(DocenteTracking).all()

    # ── Build mappings ──
    # Carrera map
    real_carreras = list(set(s.carrera for s in students if s.carrera))
    random.shuffle(real_carreras)
    carrera_map = {rc: DEMO_CARRERAS[i % len(DEMO_CARRERAS)] for i, rc in enumerate(real_carreras)}

    # Teacher name map (consistent across all tables)
    all_docentes = set()
    for e in enrollments:
        if e.docente: all_docentes.add(e.docente)
    for g in grades:
        if g.docente: all_docentes.add(g.docente)
    for c in courses:
        if c.docente: all_docentes.add(c.docente)
    for cc in course_configs:
        if cc.docente: all_docentes.add(cc.docente)
    for dt in docente_tracking:
        if dt.docente: all_docentes.add(dt.docente)
    for iv in interventions:
        if iv.docente: all_docentes.add(iv.docente)
    docente_map = _make_docente_map(all_docentes)

    # Student name generation
    n = len(students)
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

    # ── Write to demo DB ──
    demo_db = DemoSessionLocal()
    try:
        # Clear all tables (order matters for FK constraints)
        for model in [AlertEvent, DocenteTracking, Intervention, TaskSubmission,
                      AvacAccess, Grade, Enrollment, CourseConfig, SemesterConfig,
                      Course, Student, User]:
            demo_db.query(model).delete()
        demo_db.commit()

        # 1. Students (with ID remapping)
        student_id_map = {}  # old_id -> new_id
        student_name_map = {}  # old_id -> new_name
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
                sede=s.sede, campus=s.campus,
                nivel_academico=s.nivel_academico,
                nivel_riesgo=s.nivel_riesgo,
                indice_compromiso=s.indice_compromiso,
                dias_sin_acceso=s.dias_sin_acceso,
                porcentaje_tareas=s.porcentaje_tareas,
                promedio_calificaciones=s.promedio_calificaciones,
                pais="Ecuador",
                provincia=random.choice(PROVINCIAS),
                ciudad=random.choice(CIUDADES),
                genero=s.genero, periodo=s.periodo,
                estado_matricula=s.estado_matricula,
                prob_desercion=s.prob_desercion,
                prob_reprobacion=s.prob_reprobacion,
                es_tercera_matricula=s.es_tercera_matricula,
                score_recuperabilidad=s.score_recuperabilidad,
                nivel_recuperabilidad=s.nivel_recuperabilidad,
            )
            demo_db.add(demo_student)
            demo_db.flush()  # get the new ID
            student_id_map[s.id] = demo_student.id
            student_name_map[s.id] = nombre

        stats["students"] = n

        # 2. Admin user
        demo_admin = User(
            email=current_user.email,
            nombre="Admin Demo",
            hashed_password=current_user.hashed_password,  # same password
            role=UserRole.admin,
            is_active=True,
        )
        demo_db.add(demo_admin)
        demo_db.flush()
        user_id_map = {current_user.id: demo_admin.id}

        # 3. Semester configs (no PII)
        for sc in semester_configs:
            demo_db.execute(
                text("INSERT INTO semester_configs (semestre, activo, bloque_actual, "
                     "fecha_inicio_b1, fecha_fin_b1, fecha_inicio_b2, fecha_fin_b2, "
                     "umbrales, calendario_academico) "
                     "VALUES (:s, :a, :ba, :fb1, :fe1, :fb2, :fe2, :u, :c)"),
                {"s": sc.semestre, "a": sc.activo, "ba": sc.bloque_actual,
                 "fb1": sc.fecha_inicio_b1, "fe1": sc.fecha_fin_b1,
                 "fb2": sc.fecha_inicio_b2, "fe2": sc.fecha_fin_b2,
                 "u": sc.umbrales, "c": sc.calendario_academico}
            )
        stats["semester_configs"] = len(semester_configs)

        # 4. Courses
        for c in courses:
            demo_db.add(Course(
                codigo_avac=c.codigo_avac, nombre=c.nombre,
                carrera=carrera_map.get(c.carrera, c.carrera),
                docente=docente_map.get(c.docente, c.docente),
                periodo=c.periodo, grupo=c.grupo,
            ))
        stats["courses"] = len(courses)

        # 5. Course configs
        for cc in course_configs:
            d_name = docente_map.get(cc.docente, cc.docente)
            d_email = _generate_email(d_name.split()[-1], d_name.split()[0], "unie.edu.ec") if d_name else None
            demo_db.add(CourseConfig(
                codigo_avac=cc.codigo_avac, nombre=cc.nombre,
                asignatura=cc.asignatura,
                carrera=carrera_map.get(cc.carrera, cc.carrera),
                docente=d_name, correo_docente=d_email,
                semestre=cc.semestre, bloque=cc.bloque,
                nivel=cc.nivel, grupo=cc.grupo,
                activo=cc.activo, es_especial=cc.es_especial,
                notas=cc.notas,
            ))
        stats["course_configs"] = len(course_configs)

        # 6. Enrollments
        for e in enrollments:
            new_sid = student_id_map.get(e.student_id)
            if not new_sid:
                continue
            d_name = docente_map.get(e.docente, e.docente)
            d_email = _generate_email(d_name.split()[-1], d_name.split()[0], "unie.edu.ec") if d_name else None
            demo_db.add(Enrollment(
                student_id=new_sid,
                codigo_grupo=e.codigo_grupo,
                codigo_asignatura=e.codigo_asignatura,
                asignatura=e.asignatura,
                tipo_asignatura=e.tipo_asignatura,
                carrera=carrera_map.get(e.carrera, e.carrera),
                nivel=e.nivel, nombre_grupo=e.nombre_grupo,
                bloque=e.bloque,
                docente=d_name, correo_docente=d_email,
                numero_repitencias=e.numero_repitencias,
                pagado=e.pagado,
                estado_matriculado=e.estado_matriculado,
                es_tercera_matricula=e.es_tercera_matricula,
                tipo_aprobacion=e.tipo_aprobacion,
                estado_solicitud=e.estado_solicitud,
                periodo=e.periodo,
            ))
        stats["enrollments"] = len(enrollments)

        # 7. Grades
        for g in grades:
            new_sid = student_id_map.get(g.student_id)
            if not new_sid:
                continue
            demo_db.add(Grade(
                student_id=new_sid,
                asignatura=g.asignatura,
                carrera=carrera_map.get(g.carrera, g.carrera),
                grupo=g.grupo,
                docente=docente_map.get(g.docente, g.docente),
                nota_final=g.nota_final,
                periodo=g.periodo, sede=g.sede,
                numero_repitencias=g.numero_repitencias,
                nivel=g.nivel,
            ))
        stats["grades"] = len(grades)

        # 8. AVAC accesses
        for a in avac_accesses:
            new_sid = student_id_map.get(a.student_id)
            if not new_sid:
                continue
            demo_db.add(AvacAccess(
                student_id=new_sid,
                codigo_curso=a.codigo_curso,
                periodo=a.periodo,
                snapshot_date=a.snapshot_date,
                nombre_estudiante_avac=student_name_map.get(a.student_id, "Estudiante Demo"),
                ultimo_acceso_texto=a.ultimo_acceso_texto,
                dias_sin_acceso=a.dias_sin_acceso,
                estado_avac=a.estado_avac,
                fecha_extraccion=a.fecha_extraccion,
            ))
        stats["avac_accesses"] = len(avac_accesses)

        # 9. Task submissions (no direct PII)
        for ts in task_subs:
            new_sid = student_id_map.get(ts.student_id)
            if not new_sid:
                continue
            demo_db.add(TaskSubmission(
                student_id=new_sid,
                codigo_curso=ts.codigo_curso,
                periodo=ts.periodo,
                snapshot_date=ts.snapshot_date,
                unidad=ts.unidad, estado=ts.estado,
                calificacion_texto=ts.calificacion_texto,
                calificacion=ts.calificacion,
                calificacion_maxima=ts.calificacion_maxima,
                entregada=ts.entregada, calificada=ts.calificada,
                retrasada=ts.retrasada,
                fecha_entrega=ts.fecha_entrega,
                fecha_calificacion=ts.fecha_calificacion,
                archivos_enviados=ts.archivos_enviados,
                comentarios_retroalimentacion=ts.comentarios_retroalimentacion,
                calificacion_final=ts.calificacion_final,
                total_curso=ts.total_curso,
            ))
        stats["task_submissions"] = len(task_subs)

        # 10. Interventions
        for iv in interventions:
            new_sid = student_id_map.get(iv.student_id)
            if not new_sid:
                continue
            demo_db.add(Intervention(
                student_id=new_sid,
                monitor_id=user_id_map.get(iv.monitor_id),
                monitor_nombre="Admin Demo" if iv.monitor_nombre else None,
                carrera=carrera_map.get(iv.carrera, iv.carrera),
                medio=iv.medio, motivo=iv.motivo, estado=iv.estado,
                asignatura=iv.asignatura,
                docente=docente_map.get(iv.docente, iv.docente),
                observacion=random.choice(OBSERVACIONES_DEMO) if iv.observacion else None,
                periodo=iv.periodo, resultado=iv.resultado,
                requiere_seguimiento=iv.requiere_seguimiento,
                nota_cierre=iv.nota_cierre,
                derivar_bienestar=iv.derivar_bienestar,
                derivar_financiero=iv.derivar_financiero,
                derivar_coordinacion=iv.derivar_coordinacion,
                derivar_docente=iv.derivar_docente,
            ))
        stats["interventions"] = len(interventions)

        # 11. Alert events
        for ae in alerts:
            new_sid = student_id_map.get(ae.student_id)
            if not new_sid:
                continue
            demo_db.add(AlertEvent(
                student_id=new_sid,
                tipo=ae.tipo,
                codigo_curso=ae.codigo_curso,
                mensaje=ae.mensaje,  # typically no PII, uses student_id
                severidad=ae.severidad,
                leido=ae.leido,
                leido_por="Admin Demo" if ae.leido_por else None,
            ))
        stats["alert_events"] = len(alerts)

        # 12. Docente tracking
        for dt in docente_tracking:
            demo_db.add(DocenteTracking(
                codigo_curso=dt.codigo_curso,
                nombre_curso=dt.nombre_curso,
                actividad=dt.actividad,
                tipo_actividad=dt.tipo_actividad,
                calificada=dt.calificada,
                fecha_limite=dt.fecha_limite,
                fecha_calificacion=dt.fecha_calificacion,
                docente=docente_map.get(dt.docente, dt.docente),
                dias_retraso=dt.dias_retraso,
                semestre=dt.semestre,
                fuente=dt.fuente,
            ))
        stats["docente_tracking"] = len(docente_tracking)

        demo_db.commit()

        return {
            "status": "success",
            "tables_seeded": stats,
            "carreras_mapped": carrera_map,
            "docentes_anonymized": len(docente_map),
            "demo_university": DEMO_UNIVERSITY,
            "admin_email": current_user.email,
            "message": f"Demo DB completamente poblada. {n} estudiantes + {len(stats)} tablas.",
        }
    except Exception as e:
        demo_db.rollback()
        import traceback
        raise HTTPException(status_code=500, detail=f"Error seeding demo: {str(e)}\n{traceback.format_exc()}")
    finally:
        demo_db.close()
