"""
Demo data anonymization — generates shuffled/anonymized data
for demo.yachaydeep.com presentations.

Strategy: Copies ALL tables from production to demo DB, anonymizing PII.
Uses bulk operations and batched commits to avoid timeouts.
"""
import random
import string
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth.jwt import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/demo", tags=["demo"])

BATCH_SIZE = 500  # commit every N rows

NOMBRES_M = [
    "Carlos", "Juan", "Luis", "Miguel", "José", "Andrés", "David",
    "Fernando", "Ricardo", "Santiago", "Diego", "Sebastián", "Mateo",
    "Alejandro", "Daniel", "Gabriel", "Pablo", "Nicolás", "Martín",
    "Emilio", "Roberto", "Héctor", "Francisco", "Eduardo", "Tomás",
]
NOMBRES_F = [
    "María", "Ana", "Gabriela", "Sofía", "Valentina", "Camila",
    "Isabella", "Daniela", "Lucía", "Natalia", "Carolina", "Andrea",
    "Fernanda", "Paula", "Valeria", "Alejandra", "Mariana", "Diana",
]
APELLIDOS = [
    "García", "Rodríguez", "Martínez", "López", "González", "Hernández",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Rivera",
    "Gómez", "Díaz", "Reyes", "Morales", "Cruz", "Ortiz", "Gutiérrez",
    "Chávez", "Ramos", "Vargas", "Castillo", "Jiménez", "Moreno",
    "Romero", "Alvarado", "Ruiz", "Mendoza", "Aguilar", "Medina",
    "Herrera", "Vega", "Castro", "Ríos", "Contreras", "Guerrero",
    "Espinoza", "Zambrano", "Vera", "Pacheco", "Cárdenas", "Lara",
    "Campoverde", "Quezada", "Cabrera", "Toapanta", "Guamán",
]
CIUDADES = ["Quito", "Guayaquil", "Cuenca", "Ambato", "Loja", "Riobamba",
            "Machala", "Portoviejo", "Ibarra", "Esmeraldas"]
PROVINCIAS = ["Pichincha", "Guayas", "Azuay", "Tungurahua", "Loja",
              "Chimborazo", "El Oro", "Manabí", "Imbabura", "Esmeraldas"]
DEMO_CARRERAS = [
    "Ingeniería en Ciencias de la Computación", "Licenciatura en Ciencias de la Educación",
    "Ingeniería en Biotecnología", "Administración de Empresas",
    "Comunicación Social", "Psicología Clínica", "Derecho",
    "Ingeniería Ambiental", "Contabilidad y Auditoría", "Medicina Veterinaria",
]
OBSERVACIONES_DEMO = [
    "Se contactó al estudiante. Indica problemas de conectividad.",
    "Estudiante confirma que retomará actividades.",
    "No contestó la llamada. Se dejó mensaje.",
    "Carga laboral como razón de inactividad.",
    "Se derivó a bienestar estudiantil.",
    "Estudiante se comprometió a ponerse al día.",
    "Contactado vía email. Dificultades económicas.",
    "Seguimiento realizado. Mejoró su participación.",
    "Problemas de salud. Se recomienda seguimiento.",
    "Coordinación académica notificada.",
]

def _cedula():
    return f"{random.randint(1,24):02d}{random.randint(0,5)}{''.join(random.choices(string.digits,k=6))}{random.randint(0,9)}"

def _email(n, a):
    for old, new in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        n = n.lower().replace(old, new)
        a = a.lower().replace(old, new)
    return f"{n[0]}{a}{random.randint(10,99)}@unie.edu.ec"

def _phone():
    return f"09{random.randint(10000000,99999999)}"

def _rand_name():
    return f"{random.choice(APELLIDOS)} {random.choice(APELLIDOS)} {random.choice(NOMBRES_M + NOMBRES_F)}"


@router.post("/seed-demo-db")
def seed_demo_database(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Copies ALL tables from production to demo with anonymized PII. Batched for performance."""
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
    demo_db = DemoSessionLocal()

    try:
        # ── Clear demo tables ──
        logger.info("Clearing demo tables...")
        for model in [AlertEvent, DocenteTracking, Intervention, TaskSubmission,
                      AvacAccess, Grade, Enrollment, CourseConfig, SemesterConfig,
                      Course, Student, User]:
            demo_db.query(model).delete()
        demo_db.commit()

        # ── Read production data ──
        logger.info("Reading production data...")
        students = db.query(Student).all()
        if not students:
            raise HTTPException(status_code=404, detail="No hay estudiantes")

        # Build carrera map
        real_carreras = list(set(s.carrera for s in students if s.carrera))
        random.shuffle(real_carreras)
        carrera_map = {rc: DEMO_CARRERAS[i % len(DEMO_CARRERAS)] for i, rc in enumerate(real_carreras)}

        # Build docente map from enrollments (biggest source of teacher names)
        all_docentes = set()
        for row in db.query(Enrollment.docente).distinct():
            if row[0]: all_docentes.add(row[0])
        for row in db.query(Grade.docente).distinct():
            if row[0]: all_docentes.add(row[0])
        for row in db.query(Course.docente).distinct():
            if row[0]: all_docentes.add(row[0])
        for row in db.query(CourseConfig.docente).distinct():
            if row[0]: all_docentes.add(row[0])
        for row in db.query(DocenteTracking.docente).distinct():
            if row[0]: all_docentes.add(row[0])
        docente_map = {d: _rand_name() for d in all_docentes}

        # ── 1. Students ──
        logger.info(f"Seeding {len(students)} students...")
        student_id_map = {}
        for i, s in enumerate(students):
            nom = random.choice(NOMBRES_F if s.genero and s.genero.lower() in ("femenino","f","mujer") else NOMBRES_M)
            ap1, ap2 = random.choice(APELLIDOS), random.choice(APELLIDOS)
            nombre = f"{ap1} {ap2} {nom}"
            ds = Student(
                cedula=_cedula(), nombre=nombre,
                correo=_email(nom, ap1), correo_institucional=_email(nom, ap1),
                telefono=_phone(), whatsapp=_phone(),
                carrera=carrera_map.get(s.carrera, s.carrera),
                sede=s.sede, campus=s.campus, nivel_academico=s.nivel_academico,
                nivel_riesgo=s.nivel_riesgo, indice_compromiso=s.indice_compromiso,
                dias_sin_acceso=s.dias_sin_acceso, porcentaje_tareas=s.porcentaje_tareas,
                promedio_calificaciones=s.promedio_calificaciones,
                pais="Ecuador", provincia=random.choice(PROVINCIAS), ciudad=random.choice(CIUDADES),
                genero=s.genero, periodo=s.periodo, estado_matricula=s.estado_matricula,
                prob_desercion=s.prob_desercion, prob_reprobacion=s.prob_reprobacion,
                es_tercera_matricula=s.es_tercera_matricula,
                score_recuperabilidad=s.score_recuperabilidad,
                nivel_recuperabilidad=s.nivel_recuperabilidad,
            )
            demo_db.add(ds)
            if (i + 1) % BATCH_SIZE == 0:
                demo_db.flush()
        demo_db.flush()

        # Build ID map after flush
        demo_students = demo_db.query(Student.id).order_by(Student.id).all()
        for orig, new in zip(students, demo_students):
            student_id_map[orig.id] = new[0]
        stats["students"] = len(students)
        demo_db.commit()
        logger.info(f"Students done: {len(students)}")

        # ── 2. Admin user ──
        demo_admin = User(
            email=current_user.email, nombre="Admin Demo",
            hashed_password=current_user.hashed_password,
            role=UserRole.admin, is_active=True,
        )
        demo_db.add(demo_admin)
        demo_db.flush()
        user_id_map = {current_user.id: demo_admin.id}
        demo_db.commit()

        # ── 3. Semester configs (no PII) ──
        for sc in db.query(SemesterConfig).all():
            demo_db.add(SemesterConfig(
                semestre=sc.semestre, activo=sc.activo, bloque_actual=sc.bloque_actual,
                bloque1_inicio=sc.bloque1_inicio, bloque1_fin=sc.bloque1_fin,
                bloque2_inicio=sc.bloque2_inicio, bloque2_fin=sc.bloque2_fin,
                calendario_academico=sc.calendario_academico,
                umbral_nota_aprobacion=sc.umbral_nota_aprobacion,
                umbral_dias_inactividad=sc.umbral_dias_inactividad,
                umbral_tareas_minimo=sc.umbral_tareas_minimo,
                umbral_compromiso_minimo=sc.umbral_compromiso_minimo,
                auto_alertas=sc.auto_alertas,
                retrain_cada_n_etl=sc.retrain_cada_n_etl, retrain_contador_etl=0,
            ))
        demo_db.commit()
        stats["semester_configs"] = db.query(SemesterConfig).count()

        # ── 4. Courses ──
        for c in db.query(Course).all():
            demo_db.add(Course(
                codigo_avac=c.codigo_avac, nombre=c.nombre,
                carrera=carrera_map.get(c.carrera, c.carrera),
                docente=docente_map.get(c.docente, c.docente),
                periodo=c.periodo, grupo=c.grupo,
            ))
        demo_db.commit()
        stats["courses"] = db.query(Course).count()

        # ── 5. Course configs ──
        for cc in db.query(CourseConfig).all():
            dn = docente_map.get(cc.docente, cc.docente)
            demo_db.add(CourseConfig(
                codigo_avac=cc.codigo_avac, nombre=cc.nombre, asignatura=cc.asignatura,
                carrera=carrera_map.get(cc.carrera, cc.carrera),
                docente=dn, correo_docente=_email(dn.split()[-1], dn.split()[0]) if dn else None,
                semestre=cc.semestre, bloque=cc.bloque, nivel=cc.nivel, grupo=cc.grupo,
                activo=cc.activo, es_especial=cc.es_especial, notas=cc.notas,
            ))
        demo_db.commit()
        stats["course_configs"] = db.query(CourseConfig).count()

        # ── 6. Enrollments (large - batch) ──
        logger.info("Seeding enrollments...")
        count = 0
        for e in db.query(Enrollment).yield_per(1000):
            nsid = student_id_map.get(e.student_id)
            if not nsid: continue
            dn = docente_map.get(e.docente, e.docente)
            demo_db.add(Enrollment(
                student_id=nsid, codigo_grupo=e.codigo_grupo,
                codigo_asignatura=e.codigo_asignatura, asignatura=e.asignatura,
                tipo_asignatura=e.tipo_asignatura,
                carrera=carrera_map.get(e.carrera, e.carrera),
                nivel=e.nivel, nombre_grupo=e.nombre_grupo, bloque=e.bloque,
                docente=dn, correo_docente=_email(dn.split()[-1], dn.split()[0]) if dn else None,
                numero_repitencias=e.numero_repitencias, pagado=e.pagado,
                estado_matriculado=e.estado_matriculado,
                es_tercera_matricula=e.es_tercera_matricula,
                tipo_aprobacion=e.tipo_aprobacion, estado_solicitud=e.estado_solicitud,
                periodo=e.periodo,
            ))
            count += 1
            if count % BATCH_SIZE == 0: demo_db.commit()
        demo_db.commit()
        stats["enrollments"] = count

        # ── 7. Grades (large - batch) ──
        logger.info("Seeding grades...")
        count = 0
        for g in db.query(Grade).yield_per(1000):
            nsid = student_id_map.get(g.student_id)
            if not nsid: continue
            demo_db.add(Grade(
                student_id=nsid, asignatura=g.asignatura,
                carrera=carrera_map.get(g.carrera, g.carrera),
                grupo=g.grupo, docente=docente_map.get(g.docente, g.docente),
                nota_final=g.nota_final, periodo=g.periodo, sede=g.sede,
                numero_repitencias=g.numero_repitencias, nivel=g.nivel,
            ))
            count += 1
            if count % BATCH_SIZE == 0: demo_db.commit()
        demo_db.commit()
        stats["grades"] = count

        # ── 8. AVAC accesses (large - batch) ──
        logger.info("Seeding avac_accesses...")
        count = 0
        for a in db.query(AvacAccess).yield_per(1000):
            nsid = student_id_map.get(a.student_id)
            if not nsid: continue
            demo_db.add(AvacAccess(
                student_id=nsid, codigo_curso=a.codigo_curso, periodo=a.periodo,
                snapshot_date=a.snapshot_date, nombre_estudiante_avac="Estudiante Demo",
                ultimo_acceso_texto=a.ultimo_acceso_texto,
                dias_sin_acceso=a.dias_sin_acceso, estado_avac=a.estado_avac,
                fecha_extraccion=a.fecha_extraccion,
            ))
            count += 1
            if count % BATCH_SIZE == 0: demo_db.commit()
        demo_db.commit()
        stats["avac_accesses"] = count

        # ── 9. Task submissions (large - batch, no PII) ──
        logger.info("Seeding task_submissions...")
        count = 0
        for ts in db.query(TaskSubmission).yield_per(1000):
            nsid = student_id_map.get(ts.student_id)
            if not nsid: continue
            demo_db.add(TaskSubmission(
                student_id=nsid, codigo_curso=ts.codigo_curso, periodo=ts.periodo,
                snapshot_date=ts.snapshot_date, unidad=ts.unidad, estado=ts.estado,
                calificacion_texto=ts.calificacion_texto, calificacion=ts.calificacion,
                calificacion_maxima=ts.calificacion_maxima,
                entregada=ts.entregada, calificada=ts.calificada, retrasada=ts.retrasada,
                fecha_entrega=ts.fecha_entrega, fecha_calificacion=ts.fecha_calificacion,
                calificacion_final=ts.calificacion_final, total_curso=ts.total_curso,
            ))
            count += 1
            if count % BATCH_SIZE == 0: demo_db.commit()
        demo_db.commit()
        stats["task_submissions"] = count

        # ── 10. Interventions ──
        logger.info("Seeding interventions...")
        count = 0
        for iv in db.query(Intervention).yield_per(500):
            nsid = student_id_map.get(iv.student_id)
            if not nsid: continue
            demo_db.add(Intervention(
                student_id=nsid, monitor_id=user_id_map.get(iv.monitor_id),
                monitor_nombre="Admin Demo" if iv.monitor_nombre else None,
                carrera=carrera_map.get(iv.carrera, iv.carrera),
                medio=iv.medio, motivo=iv.motivo, estado=iv.estado,
                asignatura=iv.asignatura, docente=docente_map.get(iv.docente, iv.docente),
                observacion=random.choice(OBSERVACIONES_DEMO) if iv.observacion else None,
                periodo=iv.periodo, resultado=iv.resultado,
                requiere_seguimiento=iv.requiere_seguimiento, nota_cierre=iv.nota_cierre,
                derivar_bienestar=iv.derivar_bienestar, derivar_financiero=iv.derivar_financiero,
                derivar_coordinacion=iv.derivar_coordinacion, derivar_docente=iv.derivar_docente,
            ))
            count += 1
            if count % BATCH_SIZE == 0: demo_db.commit()
        demo_db.commit()
        stats["interventions"] = count

        # ── 11. Alert events ──
        logger.info("Seeding alert_events...")
        count = 0
        for ae in db.query(AlertEvent).yield_per(1000):
            nsid = student_id_map.get(ae.student_id)
            if not nsid: continue
            demo_db.add(AlertEvent(
                student_id=nsid, tipo=ae.tipo, codigo_curso=ae.codigo_curso,
                mensaje=ae.mensaje, severidad=ae.severidad,
                leido=ae.leido, leido_por="Admin Demo" if ae.leido_por else None,
            ))
            count += 1
            if count % BATCH_SIZE == 0: demo_db.commit()
        demo_db.commit()
        stats["alert_events"] = count

        # ── 12. Docente tracking ──
        logger.info("Seeding docente_tracking...")
        count = 0
        for dt in db.query(DocenteTracking).yield_per(1000):
            demo_db.add(DocenteTracking(
                codigo_curso=dt.codigo_curso, nombre_curso=dt.nombre_curso,
                actividad=dt.actividad, tipo_actividad=dt.tipo_actividad,
                calificada=dt.calificada, fecha_limite=dt.fecha_limite,
                fecha_calificacion=dt.fecha_calificacion,
                docente=docente_map.get(dt.docente, dt.docente),
                dias_retraso=dt.dias_retraso, semestre=dt.semestre, fuente=dt.fuente,
            ))
            count += 1
            if count % BATCH_SIZE == 0: demo_db.commit()
        demo_db.commit()
        stats["docente_tracking"] = count

        logger.info(f"Demo seed complete: {stats}")
        return {
            "status": "success",
            "tables_seeded": stats,
            "carreras_mapped": carrera_map,
            "docentes_anonymized": len(docente_map),
            "admin_email": current_user.email,
        }
    except HTTPException:
        raise
    except Exception as e:
        demo_db.rollback()
        import traceback
        logger.error(f"Seed error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        demo_db.close()
