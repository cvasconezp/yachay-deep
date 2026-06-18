"""
Demo data anonymization — phased seeding to avoid Railway timeouts.
Each phase copies a subset of tables. Run phase 1 first, then 2, then 3.
"""
import random
import string
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth.jwt import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/demo", tags=["demo"])

BATCH = 500
NOMBRES = ["Carlos","Juan","Luis","Miguel","José","Andrés","David","Fernando",
           "Ricardo","Santiago","María","Ana","Gabriela","Sofía","Valentina",
           "Camila","Isabella","Daniela","Lucía","Natalia","Carolina","Andrea"]
APELLIDOS = ["García","Rodríguez","Martínez","López","González","Hernández",
             "Pérez","Sánchez","Ramírez","Torres","Flores","Rivera","Gómez",
             "Díaz","Reyes","Morales","Cruz","Ortiz","Gutiérrez","Chávez",
             "Ramos","Vargas","Castillo","Jiménez","Moreno","Romero","Alvarado",
             "Ruiz","Mendoza","Aguilar","Medina","Herrera","Vega","Castro",
             "Espinoza","Zambrano","Vera","Pacheco","Cárdenas","Lara",
             "Campoverde","Quezada","Cabrera","Toapanta","Guamán"]
CIUDADES = ["Quito","Guayaquil","Cuenca","Ambato","Loja","Riobamba","Machala"]
PROVINCIAS = ["Pichincha","Guayas","Azuay","Tungurahua","Loja","Chimborazo","El Oro"]
DEMO_CARRERAS = ["Ing. Ciencias de la Computación","Lic. Ciencias de la Educación",
                 "Ing. Biotecnología","Administración de Empresas","Comunicación Social",
                 "Psicología Clínica","Derecho","Ing. Ambiental","Contabilidad y Auditoría",
                 "Medicina Veterinaria"]
OBS = ["Contactado. Problemas de conectividad.","Retomará actividades.",
       "No contestó. Mensaje dejado.","Carga laboral.","Derivado a bienestar.",
       "Se comprometió a ponerse al día.","Dificultades económicas.",
       "Mejoró participación.","Problemas de salud.","Coordinación notificada."]

def _ced():
    return f"{random.randint(1,24):02d}{random.randint(0,5)}{''.join(random.choices(string.digits,k=6))}{random.randint(0,9)}"
def _em(n,a):
    for o,r in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        n=n.lower().replace(o,r); a=a.lower().replace(o,r)
    return f"{n[0]}{a}{random.randint(10,99)}@unie.edu.ec"
def _ph(): return f"09{random.randint(10000000,99999999)}"
def _rn(): return f"{random.choice(APELLIDOS)} {random.choice(APELLIDOS)} {random.choice(NOMBRES)}"


def _get_demo_db():
    from ..database import DemoSessionLocal, demo_engine
    if not DemoSessionLocal:
        raise HTTPException(status_code=503, detail="DEMO_DATABASE_URL no configurada")
    return DemoSessionLocal()


def _get_maps(db):
    """Build carrera_map, docente_map, student_id_map from production + demo DBs."""
    from ..models.student import Student
    from ..models.enrollment import Enrollment
    from ..models.grade import Grade
    from ..models.course import Course
    from ..models.course_config import CourseConfig
    from ..models.docente_tracking import DocenteTracking

    # Carrera map
    real_carreras = list(set(r[0] for r in db.query(Student.carrera).distinct() if r[0]))
    random.seed(42)  # deterministic mapping
    random.shuffle(real_carreras)
    carrera_map = {rc: DEMO_CARRERAS[i % len(DEMO_CARRERAS)] for i, rc in enumerate(real_carreras)}

    # Docente map
    all_doc = set()
    for model in [Enrollment, Grade, Course, CourseConfig, DocenteTracking]:
        if hasattr(model, 'docente'):
            for r in db.query(model.docente).distinct():
                if r[0]: all_doc.add(r[0])
    random.seed(42)
    docente_map = {d: _rn() for d in sorted(all_doc)}

    # Student ID map (prod → demo)
    demo_db = _get_demo_db()
    try:
        prod_ids = [r[0] for r in db.query(Student.id).order_by(Student.id).all()]
        demo_ids = [r[0] for r in demo_db.query(Student.id).order_by(Student.id).all()]
        student_id_map = {}
        for p, d in zip(prod_ids, demo_ids):
            student_id_map[p] = d
    finally:
        demo_db.close()

    return carrera_map, docente_map, student_id_map


@router.post("/seed-demo-db")
def seed_phase1(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Phase 1: Students + Users + Semester/Course configs. Fast."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    from ..models.student import Student
    from ..models.user import User, UserRole
    from ..models.course import Course
    from ..models.course_config import CourseConfig, SemesterConfig
    from ..models.enrollment import Enrollment
    from ..models.grade import Grade
    from ..models.avac_access import AvacAccess
    from ..models.task_submission import TaskSubmission
    from ..models.intervention import Intervention
    from ..models.alert_event import AlertEvent
    from ..models.docente_tracking import DocenteTracking
    from ..auth.jwt import hash_password

    demo_db = _get_demo_db()
    try:
        # Clear ALL tables
        for m in [AlertEvent, DocenteTracking, Intervention, TaskSubmission,
                  AvacAccess, Grade, Enrollment, CourseConfig, SemesterConfig,
                  Course, Student, User]:
            demo_db.query(m).delete()
        demo_db.commit()

        students = db.query(Student).all()
        if not students:
            raise HTTPException(status_code=404, detail="No hay estudiantes")

        # Build maps
        real_carreras = list(set(s.carrera for s in students if s.carrera))
        random.seed(42)
        random.shuffle(real_carreras)
        carrera_map = {rc: DEMO_CARRERAS[i % len(DEMO_CARRERAS)] for i, rc in enumerate(real_carreras)}

        all_doc = set()
        for model in [Enrollment, Grade, Course, CourseConfig, DocenteTracking]:
            for r in db.query(model.docente).distinct():
                if r[0]: all_doc.add(r[0])
        random.seed(42)
        docente_map = {d: _rn() for d in sorted(all_doc)}

        # Students
        random.seed(None)  # back to random
        for i, s in enumerate(students):
            nom = random.choice(NOMBRES)
            ap1, ap2 = random.choice(APELLIDOS), random.choice(APELLIDOS)
            demo_db.add(Student(
                cedula=_ced(), nombre=f"{ap1} {ap2} {nom}",
                correo=_em(nom,ap1), correo_institucional=_em(nom,ap1),
                telefono=_ph(), whatsapp=_ph(),
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
            ))
            if (i+1) % BATCH == 0: demo_db.flush()
        demo_db.commit()

        # Admin
        demo_db.add(User(
            email=current_user.email, nombre="Admin Demo",
            hashed_password=current_user.hashed_password,
            role=UserRole.admin, is_active=True,
        ))
        demo_db.commit()

        # Semester configs
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

        # Courses + Course configs
        for c in db.query(Course).all():
            demo_db.add(Course(
                codigo_avac=c.codigo_avac, nombre=c.nombre,
                carrera=carrera_map.get(c.carrera, c.carrera),
                docente=docente_map.get(c.docente, c.docente),
                periodo=c.periodo, grupo=c.grupo,
            ))
        demo_db.commit()
        for cc in db.query(CourseConfig).all():
            dn = docente_map.get(cc.docente, cc.docente)
            demo_db.add(CourseConfig(
                codigo_avac=cc.codigo_avac, nombre=cc.nombre, asignatura=cc.asignatura,
                carrera=carrera_map.get(cc.carrera, cc.carrera),
                docente=dn, correo_docente=_em(dn.split()[-1],dn.split()[0]) if dn else None,
                semestre=cc.semestre, bloque=cc.bloque, nivel=cc.nivel, grupo=cc.grupo,
                activo=cc.activo, es_especial=cc.es_especial, notas=cc.notas,
            ))
        demo_db.commit()

        return {"status": "ok", "phase": 1, "students": len(students),
                "message": "Phase 1 done. Now run phase=2"}
    except HTTPException: raise
    except Exception as e:
        demo_db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        demo_db.close()


@router.post("/seed-demo-phase2")
def seed_phase2(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Phase 2: Enrollments + Grades (large tables)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    from ..models.enrollment import Enrollment
    from ..models.grade import Grade

    carrera_map, docente_map, sid_map = _get_maps(db)
    demo_db = _get_demo_db()
    stats = {}
    try:
        # Enrollments
        c = 0
        for e in db.query(Enrollment).yield_per(1000):
            ns = sid_map.get(e.student_id)
            if not ns: continue
            dn = docente_map.get(e.docente, e.docente)
            demo_db.add(Enrollment(
                student_id=ns, codigo_grupo=e.codigo_grupo,
                codigo_asignatura=e.codigo_asignatura, asignatura=e.asignatura,
                tipo_asignatura=e.tipo_asignatura,
                carrera=carrera_map.get(e.carrera, e.carrera),
                nivel=e.nivel, nombre_grupo=e.nombre_grupo, bloque=e.bloque,
                docente=dn, correo_docente=_em(dn.split()[-1],dn.split()[0]) if dn else None,
                numero_repitencias=e.numero_repitencias, pagado=e.pagado,
                estado_matriculado=e.estado_matriculado,
                es_tercera_matricula=e.es_tercera_matricula,
                tipo_aprobacion=e.tipo_aprobacion, estado_solicitud=e.estado_solicitud,
                periodo=e.periodo,
            ))
            c += 1
            if c % BATCH == 0: demo_db.commit()
        demo_db.commit()
        stats["enrollments"] = c

        # Grades
        c = 0
        for g in db.query(Grade).yield_per(1000):
            ns = sid_map.get(g.student_id)
            if not ns: continue
            demo_db.add(Grade(
                student_id=ns, asignatura=g.asignatura,
                carrera=carrera_map.get(g.carrera, g.carrera),
                grupo=g.grupo, docente=docente_map.get(g.docente, g.docente),
                nota_final=g.nota_final, periodo=g.periodo, sede=g.sede,
                numero_repitencias=g.numero_repitencias, nivel=g.nivel,
            ))
            c += 1
            if c % BATCH == 0: demo_db.commit()
        demo_db.commit()
        stats["grades"] = c

        return {"status": "ok", "phase": 2, **stats, "message": "Phase 2 done. Now run phase=3"}
    except Exception as e:
        demo_db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        demo_db.close()


@router.post("/seed-demo-phase3")
def seed_phase3(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Phase 3: AVAC accesses + Task submissions (largest tables)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    from ..models.avac_access import AvacAccess
    from ..models.task_submission import TaskSubmission

    _, _, sid_map = _get_maps(db)
    demo_db = _get_demo_db()
    stats = {}
    try:
        c = 0
        for a in db.query(AvacAccess).yield_per(1000):
            ns = sid_map.get(a.student_id)
            if not ns: continue
            demo_db.add(AvacAccess(
                student_id=ns, codigo_curso=a.codigo_curso, periodo=a.periodo,
                snapshot_date=a.snapshot_date, nombre_estudiante_avac="Estudiante Demo",
                ultimo_acceso_texto=a.ultimo_acceso_texto,
                dias_sin_acceso=a.dias_sin_acceso, estado_avac=a.estado_avac,
                fecha_extraccion=a.fecha_extraccion,
            ))
            c += 1
            if c % BATCH == 0: demo_db.commit()
        demo_db.commit()
        stats["avac_accesses"] = c

        c = 0
        for ts in db.query(TaskSubmission).yield_per(1000):
            ns = sid_map.get(ts.student_id)
            if not ns: continue
            demo_db.add(TaskSubmission(
                student_id=ns, codigo_curso=ts.codigo_curso, periodo=ts.periodo,
                snapshot_date=ts.snapshot_date, unidad=ts.unidad, estado=ts.estado,
                calificacion_texto=ts.calificacion_texto, calificacion=ts.calificacion,
                calificacion_maxima=ts.calificacion_maxima,
                entregada=ts.entregada, calificada=ts.calificada, retrasada=ts.retrasada,
                fecha_entrega=ts.fecha_entrega, fecha_calificacion=ts.fecha_calificacion,
                calificacion_final=ts.calificacion_final, total_curso=ts.total_curso,
            ))
            c += 1
            if c % BATCH == 0: demo_db.commit()
        demo_db.commit()
        stats["task_submissions"] = c

        return {"status": "ok", "phase": 3, **stats, "message": "Phase 3 done. Now run phase=4"}
    except Exception as e:
        demo_db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        demo_db.close()


@router.post("/seed-demo-phase4")
def seed_phase4(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Phase 4: Interventions + Alerts + Docente tracking."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    from ..models.intervention import Intervention
    from ..models.alert_event import AlertEvent
    from ..models.docente_tracking import DocenteTracking
    from ..models.user import User

    carrera_map, docente_map, sid_map = _get_maps(db)
    demo_db = _get_demo_db()
    demo_admin = demo_db.query(User).first()
    uid_map = {current_user.id: demo_admin.id} if demo_admin else {}
    stats = {}
    try:
        c = 0
        for iv in db.query(Intervention).yield_per(500):
            ns = sid_map.get(iv.student_id)
            if not ns: continue
            demo_db.add(Intervention(
                student_id=ns, monitor_id=uid_map.get(iv.monitor_id),
                monitor_nombre="Admin Demo" if iv.monitor_nombre else None,
                carrera=carrera_map.get(iv.carrera, iv.carrera),
                medio=iv.medio, motivo=iv.motivo, estado=iv.estado,
                asignatura=iv.asignatura, docente=docente_map.get(iv.docente, iv.docente),
                observacion=random.choice(OBS) if iv.observacion else None,
                periodo=iv.periodo, resultado=iv.resultado,
                requiere_seguimiento=iv.requiere_seguimiento, nota_cierre=iv.nota_cierre,
                derivar_bienestar=iv.derivar_bienestar, derivar_financiero=iv.derivar_financiero,
                derivar_coordinacion=iv.derivar_coordinacion, derivar_docente=iv.derivar_docente,
            ))
            c += 1
            if c % BATCH == 0: demo_db.commit()
        demo_db.commit()
        stats["interventions"] = c

        c = 0
        for ae in db.query(AlertEvent).yield_per(1000):
            ns = sid_map.get(ae.student_id)
            if not ns: continue
            demo_db.add(AlertEvent(
                student_id=ns, tipo=ae.tipo, codigo_curso=ae.codigo_curso,
                mensaje=ae.mensaje, severidad=ae.severidad,
                leido=ae.leido, leido_por="Admin Demo" if ae.leido_por else None,
            ))
            c += 1
            if c % BATCH == 0: demo_db.commit()
        demo_db.commit()
        stats["alert_events"] = c

        c = 0
        for dt in db.query(DocenteTracking).yield_per(1000):
            demo_db.add(DocenteTracking(
                codigo_curso=dt.codigo_curso, nombre_curso=dt.nombre_curso,
                actividad=dt.actividad, tipo_actividad=dt.tipo_actividad,
                calificada=dt.calificada, fecha_limite=dt.fecha_limite,
                fecha_calificacion=dt.fecha_calificacion,
                docente=docente_map.get(dt.docente, dt.docente),
                dias_retraso=dt.dias_retraso, semestre=dt.semestre, fuente=dt.fuente,
            ))
            c += 1
            if c % BATCH == 0: demo_db.commit()
        demo_db.commit()
        stats["docente_tracking"] = c

        return {"status": "ok", "phase": 4, **stats, "message": "All phases complete! Demo is ready."}
    except Exception as e:
        demo_db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        demo_db.close()


# ─────────── [DEMO] Generación de datos 100% sintéticos (super-admin) ───────────
SUBJECTS = [
    "Matemática General", "Lengua y Comunicación", "Introducción a la Profesión",
    "Metodología de la Investigación", "Estadística Aplicada", "Ética Profesional",
    "Fundamentos de Programación", "Psicología General", "Sociología", "Economía",
    "Cálculo Diferencial", "Álgebra Lineal", "Bases de Datos", "Gestión de Proyectos",
    "Pensamiento Crítico", "Realidad Nacional", "Antropología", "Pedagogía General",
    "Didáctica", "Evaluación Educativa", "Tecnologías Educativas", "Inglés I",
    "Inglés II", "Contabilidad Básica", "Derecho Constitucional", "Biología",
    "Química General", "Física", "Filosofía", "Currículo", "Práctica Preprofesional I",
    "Innovación Educativa", "Gestión del Talento", "Marketing Digital",
    "Cálculo Integral", "Probabilidad", "Investigación de Operaciones", "Ecología",
    "Historia del Pensamiento", "Comunicación Digital", "Liderazgo", "Inglés III",
    "Inglés IV", "Estructura de Datos", "Redes y Comunicaciones", "Sistemas Operativos",
    "Bioquímica", "Microbiología", "Derecho Laboral", "Finanzas",
    "Gestión Ambiental", "Diseño Curricular", "Psicopedagogía", "Neurociencia Educativa",
    "Práctica Preprofesional II", "Trabajo de Titulación", "Emprendimiento",
    "Ética y Ciudadanía", "Cultura Física", "Realidad Socioeconómica",
    "Tecnologías Emergentes", "Gestión de la Calidad", "Auditoría",
]

# Banco para construir una malla determinista por carrera: 8 niveles x ≤6 materias.
def _build_malla_por_carrera():
    malla = {}
    for ci, carrera in enumerate(DEMO_CARRERAS):
        rnd = random.Random(1000 + ci)  # determinista por carrera (independiente del seed global)
        pool = SUBJECTS.copy(); rnd.shuffle(pool)
        idx = 0; niveles = {}
        for nivel in range(1, 9):
            k = rnd.randint(4, 6)        # ≤6 materias por nivel
            niveles[nivel] = pool[idx:idx + k]; idx += k
        malla[carrera] = niveles
    return malla


def _wipe_demo(demo_db):
    """Borra TODOS los datos del demo (respetando FKs). No toca usuarios/settings."""
    from ..models import (AlertEvent, Intervention, Grade, Enrollment, AvacAccess,
                          TaskSubmission, DocenteTracking, RecommendationLog, Student,
                          CourseConfig, SemesterConfig, ScrapingRun)
    for model in (AlertEvent, Intervention, RecommendationLog, DocenteTracking,
                  Grade, Enrollment, AvacAccess, TaskSubmission, ScrapingRun, Student,
                  CourseConfig, SemesterConfig):
        try:
            demo_db.query(model).delete()
        except Exception as e:
            logger.warning(f"wipe {model.__name__}: {e}")
    demo_db.commit()


@router.get("/whoami")
def whoami(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """[DIAG] Muestra a qué BD enruta ESTA petición (según X-Tenant), para detectar
    si ups está cayendo en la BD demo por error. Usa get_db (mismo que /courses)."""
    from ..database import get_current_tenant
    from ..models.course_config import CourseConfig, SemesterConfig
    bind = db.get_bind()
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    return {
        "resolved_tenant": get_current_tenant(),
        "db_host": getattr(bind.url, "host", None),
        "db_name": getattr(bind.url, "database", None),
        "course_configs": db.query(CourseConfig).count(),
        "semestre_activo": sc.semestre if sc else None,
        "user": current_user.email,
    }


@router.get("/info")
def demo_info(current_user=Depends(get_current_user)):
    """[DEMO] Diagnóstico (super-admin): a qué BD apunta el demo vs producción
    (host/base, SIN credenciales) y conteo de estudiantes en cada una.
    Sirve para verificar que el generador escribe en la BD demo y NO en producción."""
    from ..auth.jwt import is_super_admin
    if not is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="Se requiere super administrador")
    from ..database import engine as prod_engine, demo_engine
    from ..models.student import Student

    def _safe(url):
        try:
            return {"host": url.host, "database": url.database, "backend": url.get_backend_name()}
        except Exception:
            return {"host": None, "database": None}

    out = {"demo_configurada": demo_engine is not None}
    out["produccion"] = _safe(prod_engine.url)
    try:
        from ..database import SessionLocal
        pdb = SessionLocal()
        out["produccion"]["estudiantes"] = pdb.query(Student).count()
        pdb.close()
    except Exception as e:
        out["produccion"]["error"] = str(e)

    from ..models.course_config import CourseConfig, SemesterConfig

    def _sem_activo(session):
        sc = session.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
        return sc.semestre if sc else None

    try:
        pdb = SessionLocal()
        out["produccion"]["cursos_config"] = pdb.query(CourseConfig).count()
        out["produccion"]["semestre_activo"] = _sem_activo(pdb)
        pdb.close()
    except Exception as e:
        out["produccion"]["cursos_error"] = str(e)

    if demo_engine is not None:
        out["demo"] = _safe(demo_engine.url)
        try:
            ddb = _get_demo_db()
            out["demo"]["estudiantes"] = ddb.query(Student).count()
            out["demo"]["cursos_config"] = ddb.query(CourseConfig).count()
            out["demo"]["semestre_activo"] = _sem_activo(ddb)
            ddb.close()
        except Exception as e:
            out["demo"]["error"] = str(e)
        out["misma_bd_que_produccion"] = (
            out["demo"].get("host") == out["produccion"].get("host")
            and out["demo"].get("database") == out["produccion"].get("database")
        )
    return out


@router.post("/regenerate-synthetic")
def regenerate_synthetic(
    n_estudiantes: int = Query(1000, ge=10, le=2000),
    current_user=Depends(get_current_user),
):
    """[DEMO] Regenera la BD demo con datos 100% sintéticos (sin PII real).
    Malla por carrera con máx 6 materias por nivel; incluye historial de
    calificaciones (para ML), alertas, intervenciones, seguimiento docente
    y un historial de ejecuciones de scraping. Solo super-admin."""
    from ..auth.jwt import is_super_admin
    if not is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="Se requiere super administrador (admin global)")

    from datetime import datetime, timezone, timedelta
    from ..models import (Student, Enrollment, Grade, AvacAccess, TaskSubmission,
                          SemesterConfig, Intervention, DocenteTracking, ScrapingRun)

    PERIODOS_HIST = ["P65", "P66", "P67"]  # niveles pasados → periodos históricos (para ML)
    APROB = 70.0

    demo_db = _get_demo_db()
    try:
        _wipe_demo(demo_db)
        malla = _build_malla_por_carrera()
        docentes_pool = [_rn() for _ in range(25)]

        now = datetime.now(timezone.utc)
        demo_db.add(SemesterConfig(
            semestre="P68", activo=True, bloque_actual="2",
            bloque1_inicio=now - timedelta(days=120), bloque1_fin=now - timedelta(days=40),
            bloque2_inicio=now - timedelta(days=39), bloque2_fin=now + timedelta(days=40),
        ))
        demo_db.commit()

        creados = {"estudiantes": 0, "matriculas": 0, "calificaciones": 0,
                   "accesos": 0, "tareas": 0, "intervenciones": 0,
                   "seguimiento_docente": 0, "alertas": 0, "scraping_runs": 0}

        for _i in range(n_estudiantes):
            nom = random.choice(NOMBRES)
            ap1, ap2 = random.choice(APELLIDOS), random.choice(APELLIDOS)
            carrera = random.choice(DEMO_CARRERAS)
            niveles_malla = malla[carrera]
            nivel = random.randint(1, 8)
            dias = random.choice([0, 1, 3, 7, 12, 16, 20, 25, 30])
            comp = round(random.uniform(0.1, 1.0), 2)
            tareas_pct = round(random.uniform(20, 100), 1)
            riesgo = ("Alto" if (dias > 21 or comp < 0.3)
                      else "Medio" if (dias > 14 or comp < 0.5) else "Bajo")

            st = Student(
                cedula=f"9{_i:09d}", nombre=f"{ap1} {ap2} {nom}", correo=_em(nom, ap1),
                correo_institucional=_em(nom, ap1), telefono=_ph(), carrera=carrera,
                nivel_academico=nivel, nivel_riesgo=riesgo, indice_compromiso=comp,
                dias_sin_acceso=dias, porcentaje_tareas=tareas_pct,
                pais="Ecuador", provincia=random.choice(PROVINCIAS), ciudad=random.choice(CIUDADES),
                genero=random.choice(["M", "F"]), periodo="P68", estado_matricula="Matriculado",
            )
            demo_db.add(st); demo_db.flush()
            creados["estudiantes"] += 1

            notas_acum = []

            # ── Historial: niveles 1..nivel-1 ya aprobados (para malla + ML) ──
            for nv in range(1, nivel):
                periodo_hist = PERIODOS_HIST[(nv - 1) % len(PERIODOS_HIST)]
                for asig in niveles_malla[nv]:
                    nota = round(random.uniform(70, 96), 1)  # historial mayormente aprobado
                    notas_acum.append(nota)
                    demo_db.add(Grade(student_id=st.id, asignatura=asig, carrera=carrera,
                                      docente=random.choice(docentes_pool), nota_final=nota,
                                      periodo=periodo_hist, nivel=nv))
                    creados["calificaciones"] += 1

            # ── Nivel actual (≤6 materias): matrículas + notas + tareas + docente ──
            for asig in niveles_malla[nivel]:
                codigo = f"DEMO{random.randint(100000, 999999)}"
                docente = random.choice(docentes_pool)
                demo_db.add(Enrollment(
                    student_id=st.id, codigo_grupo=codigo, asignatura=asig, carrera=carrera,
                    nivel=nivel, docente=docente, periodo="68", bloque=2,
                    estado_matriculado="MATRICULADO",
                ))
                creados["matriculas"] += 1
                # nota actual: sesgada por el riesgo del estudiante
                base = 55 if riesgo == "Alto" else 68 if riesgo == "Medio" else 80
                nota = round(min(100, max(0, random.gauss(base, 12))), 1)
                notas_acum.append(nota)
                demo_db.add(Grade(student_id=st.id, asignatura=asig, carrera=carrera,
                                  docente=docente, nota_final=nota, periodo="P68", nivel=nivel))
                creados["calificaciones"] += 1
                # tareas por materia
                for u in range(1, random.randint(3, 5)):
                    entregada = random.random() < (tareas_pct / 100.0)
                    demo_db.add(TaskSubmission(
                        student_id=st.id, codigo_curso=codigo, periodo="P68", unidad=str(u),
                        entregada=entregada, calificada=entregada,
                        calificacion=round(random.uniform(5, 10), 1) if entregada else None,
                        calificacion_maxima=10.0, retrasada=(not entregada and random.random() < 0.5),
                    ))
                    creados["tareas"] += 1
                # seguimiento docente (puntualidad de calificación)
                retraso = round(random.uniform(-3, 10), 1)
                demo_db.add(DocenteTracking(
                    codigo_curso=codigo, nombre_curso=asig, actividad=f"Tarea {random.randint(1,4)}",
                    tipo_actividad="tarea", calificada=(retraso < 7), docente=docente,
                    dias_retraso=retraso, semestre="P68", fuente="demo-sintetico",
                ))
                creados["seguimiento_docente"] += 1

            # promedio del estudiante
            st.promedio_calificaciones = round(sum(notas_acum) / len(notas_acum), 1) if notas_acum else None

            # acceso AVAC
            demo_db.add(AvacAccess(
                student_id=st.id, codigo_curso=f"DEMO{random.randint(100000, 999999)}",
                periodo="P68", dias_sin_acceso=float(dias),
                ultimo_acceso_texto=f"{dias} días", estado_avac="Activo" if dias < 14 else "Inactivo",
            ))
            creados["accesos"] += 1

            if _i % 100 == 99:
                demo_db.commit()

            # intervención para algunos en riesgo
            if riesgo in ("Alto", "Medio") and random.random() < 0.4:
                demo_db.add(Intervention(
                    student_id=st.id, monitor_nombre=random.choice(docentes_pool), carrera=carrera,
                    medio=random.choice(["WhatsApp", "Llamada", "Email"]),
                    motivo=random.choice(["Bajo rendimiento", "Inactividad", "Tareas atrasadas"]),
                    estado=random.choice(["Activo", "SNA", "Cerrado"]),
                    resultado=random.choice(["Contactado", "No contestó", "Comprometido"]),
                    requiere_seguimiento=random.choice(["si", "no"]),
                    observacion=random.choice(OBS), periodo="P68",
                ))
                creados["intervenciones"] += 1

        demo_db.commit()

        # ── Historial de scraping (para que el panel no esté vacío) ──
        for i in range(6):
            d = now - timedelta(days=i)
            demo_db.add(ScrapingRun(
                tipo="full", status="success",
                cursos_procesados=random.randint(600, 730), cursos_error=0,
                registros_insertados=random.randint(60000, 71000),
                descripcion="Pipeline ETL completo (demo sintético)",
                triggered_by="demo", started_at=d, finished_at=d + timedelta(minutes=random.randint(20, 90)),
            ))
            creados["scraping_runs"] += 1
        demo_db.commit()

        # ── Alertas: reutiliza la lógica real de generación sobre la BD demo ──
        try:
            from ..services.alert_generator import generate_alerts_batch
            res_al = generate_alerts_batch(demo_db)
            creados["alertas"] = res_al.get("created", 0)
        except Exception as e:
            logger.warning(f"[DEMO] alertas: {e}")

        logger.info(f"[DEMO] Datos sintéticos regenerados: {creados}")
        return {"detail": "Datos demo regenerados", "creados": creados}
    finally:
        demo_db.close()
