"""
Módulos 8.5: Resumen de Datos + Comparativa + Períodos.
Separado de analytics.py monolítico — [ARCH-03] Remediación.

Contiene: /analytics/periodos, /analytics/resumen, /analytics/comparativa
"""
from typing import Optional
from datetime import date
from math import isnan as _math_isnan, isinf as _math_isinf
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from ...database import get_db
from ...models import Student, Grade, Intervention, Enrollment, AvacAccess
from ...models.course_config import CourseConfig, SemesterConfig
from ...auth.jwt import get_current_user
from ...models.user import User
from ._helpers import apply_periodo_filter, get_umbrales

router = APIRouter(prefix="/analytics", tags=["analytics"])



@router.get("/periodos")
def get_periodos_disponibles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista de períodos disponibles en calificaciones, enrollments y semestres.
    Devuelve ordenados de más reciente a más antiguo, con 'default' indicando
    el período activo para preseleccionar en el frontend."""
    from ...models.course_config import SemesterConfig

    def _norm(val: str) -> str:
        """Normaliza un periodo a formato 'P##'."""
        v = str(val).strip()
        return v if v.startswith("P") else f"P{v}"

    periodos_set: set[str] = set()
    has_null = False

    # 1. Períodos de calificaciones
    for (p,) in db.query(Grade.periodo).distinct().all():
        if p is None:
            has_null = True
        else:
            periodos_set.add(_norm(p))

    # 2. Períodos de enrollments (matrícula)
    for (p,) in db.query(Enrollment.periodo).distinct().all():
        if p is not None:
            periodos_set.add(_norm(p))

    # 3. Semestres configurados (siempre visibles aunque no tengan grades aún)
    active_sem = None
    for row in db.query(SemesterConfig.semestre, SemesterConfig.activo).all():
        s, activo = row
        if s is not None:
            normed = _norm(s)
            periodos_set.add(normed)
            if activo:
                active_sem = normed

    # Ordenar descendente: P68, P67, P66, ... P57
    sorted_keys = sorted(periodos_set, key=lambda x: x, reverse=True)

    periodos = []
    for p in sorted_keys:
        periodos.append({"key": p, "label": p})
    if has_null:
        periodos.append({"key": "actual", "label": "Semestre actual (sin periodo)"})

    # Indicar el default: semestre activo, o el primero de la lista
    default_key = active_sem or (sorted_keys[0] if sorted_keys else "actual")

    return {"periodos": periodos, "default": default_key}


def _resumen_period_student_ids(db: Session, periodo: Optional[str], carrera_sids=None):
    """Union de student_ids de Grade + Enrollment + AvacAccess para el período.

    Incluye AvacAccess (con fallback a periodo=NULL) para ser consistente con
    el Dashboard de Riesgo y no perder estudiantes que solo tienen datos AVAC.
    """
    from sqlalchemy import or_
    pf = periodo if periodo else "actual"

    grade_sq = db.query(Grade.student_id).distinct()
    enroll_sq = db.query(Enrollment.student_id).distinct()
    avac_sq = db.query(AvacAccess.student_id).filter(AvacAccess.student_id.isnot(None)).distinct()

    if pf == "actual":
        grade_sq = grade_sq.filter(Grade.periodo.is_(None))
        enroll_sq = enroll_sq.filter(Enrollment.periodo.is_(None))
        avac_sq = avac_sq.filter(AvacAccess.periodo.is_(None))
    elif pf != "todos":
        if pf.startswith("P"):
            grade_sq = grade_sq.filter(or_(Grade.periodo == pf, Grade.periodo == pf[1:]))
            enroll_sq = enroll_sq.filter(or_(Enrollment.periodo == pf, Enrollment.periodo == pf[1:]))
            avac_sq = avac_sq.filter(or_(
                AvacAccess.periodo == pf, AvacAccess.periodo == pf[1:],
                AvacAccess.periodo.is_(None),
            ))
        else:
            grade_sq = grade_sq.filter(or_(Grade.periodo == pf, Grade.periodo == f"P{pf}"))
            enroll_sq = enroll_sq.filter(or_(Enrollment.periodo == pf, Enrollment.periodo == f"P{pf}"))
            avac_sq = avac_sq.filter(or_(
                AvacAccess.periodo == pf, AvacAccess.periodo == f"P{pf}",
                AvacAccess.periodo.is_(None),
            ))

    if carrera_sids:
        grade_sq = grade_sq.filter(Grade.student_id.in_(carrera_sids))
        enroll_sq = enroll_sq.filter(Enrollment.student_id.in_(carrera_sids))
        avac_sq = avac_sq.filter(AvacAccess.student_id.in_(carrera_sids))

    return grade_sq.union(enroll_sq).union(avac_sq), pf


@router.get("/resumen")
def get_resumen_datos(
    carrera: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen estadístico general y por carrera."""
    from sqlalchemy import or_
    today = date.today()
    umbrales = get_umbrales(db)
    nota_aprob = umbrales["nota_aprobacion"]

    _carrera_sids = None
    if carrera:
        _carrera_sids = set(s_id for (s_id,) in db.query(Student.id).filter(
            func.lower(Student.carrera).contains(carrera.lower())).all())

    # Detectar si periodo solicitado es el activo → incluir grades con NULL
    _include_null = False
    if periodo and periodo not in ("actual", "todos"):
        try:
            active_row = db.query(SemesterConfig.semestre).filter(SemesterConfig.activo == True).first()
            if active_row and active_row[0]:
                a = active_row[0].strip()
                pn = periodo.strip()
                _include_null = (a == pn or
                                 (a.startswith("P") and a[1:] == pn) or
                                 f"P{a}" == pn)
        except Exception:
            pass

    # Grades del periodo (incluye NULL si es periodo activo para datos legacy)
    grades_q = db.query(Grade)
    grades_q, periodo_filter = apply_periodo_filter(grades_q, periodo, include_null=_include_null)
    if carrera and _carrera_sids:
        grades_q = grades_q.filter(Grade.student_id.in_(_carrera_sids))
    grades = grades_q.all()
    grade_student_ids = set(g.student_id for g in grades)

    # Enrollments del periodo
    enroll_q = db.query(Enrollment)
    enroll_q, _ = apply_periodo_filter(enroll_q, periodo, column=Enrollment.periodo)
    if carrera and _carrera_sids:
        enroll_q = enroll_q.filter(Enrollment.student_id.in_(_carrera_sids))
    enrollments = enroll_q.all()
    enroll_student_ids = set(e.student_id for e in enrollments)

    # AvacAccess student IDs del periodo (incluir NULL como fallback)
    from sqlalchemy import or_ as _or
    avac_pf = periodo_filter
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if avac_pf == "actual" and semconfig and semconfig.semestre:
        avac_pf = semconfig.semestre
    avac_sid_q = db.query(AvacAccess.student_id).filter(AvacAccess.student_id.isnot(None)).distinct()
    if avac_pf not in ("actual", "todos"):
        if avac_pf.startswith("P"):
            avac_variants = (avac_pf, avac_pf[1:])
        else:
            avac_variants = (avac_pf, f"P{avac_pf}")
        avac_sid_q = avac_sid_q.filter(_or(
            AvacAccess.periodo.in_(avac_variants),
            AvacAccess.periodo.is_(None),
        ))
    elif avac_pf == "actual":
        avac_sid_q = avac_sid_q.filter(AvacAccess.periodo.is_(None))
    if carrera and _carrera_sids:
        avac_sid_q = avac_sid_q.filter(AvacAccess.student_id.in_(_carrera_sids))
    avac_student_ids = set(r[0] for r in avac_sid_q.all())

    # Union: estudiantes con grades O enrollments O accesos AVAC
    all_period_sids = grade_student_ids | enroll_student_ids | avac_student_ids

    base_q = db.query(Student)
    if carrera:
        base_q = base_q.filter(func.lower(Student.carrera).contains(carrera.lower()))
    if periodo_filter != "todos":
        base_q = base_q.filter(Student.id.in_(all_period_sids))
    students = base_q.all()

    # Flag: hay calificaciones reales para este período?
    tiene_datos_periodo = len(grades) > 0

    # === Métricas de enrollment ===
    carreras_set = set()
    asignaturas_set = set()
    docentes_enroll_set = set()
    enroll_por_tipo = {}
    enroll_por_nivel = {}
    enroll_pagado = {"SI": 0, "NO": 0, "Otro": 0}
    enroll_repitencias = 0
    for e in enrollments:
        if e.carrera:
            carreras_set.add(e.carrera)
        if e.asignatura:
            asignaturas_set.add(e.asignatura)
        if e.docente:
            docentes_enroll_set.add(e.docente)
        tipo = e.tipo_asignatura or "Sin dato"
        enroll_por_tipo[tipo] = enroll_por_tipo.get(tipo, 0) + 1
        niv = e.nivel or 0
        enroll_por_nivel[niv] = enroll_por_nivel.get(niv, 0) + 1
        if e.pagado:
            key = e.pagado.strip().upper()
            if key == "SI":
                enroll_pagado["SI"] += 1
            elif key == "NO":
                enroll_pagado["NO"] += 1
            else:
                enroll_pagado["Otro"] += 1
        if e.numero_repitencias and e.numero_repitencias > 1:
            enroll_repitencias += 1

    # Carreras from students too
    for s in students:
        if s.carrera:
            carreras_set.add(s.carrera)

    if not students:
        return {"global": {}, "por_carrera": [], "tiene_datos_periodo": tiene_datos_periodo}

    student_ids = set(s.id for s in students)

    reprobados_ids = set()
    repitentes_ids = set()
    # Repitentes y reprobados desde grades
    for g in grades:
        if g.student_id in student_ids:
            if g.nota_final is not None and g.nota_final < nota_aprob:
                reprobados_ids.add(g.student_id)
            if g.numero_repitencias and g.numero_repitencias > 1:
                repitentes_ids.add(g.student_id)
    # Repitentes desde enrollments (complemento cuando no hay grades)
    for e in enrollments:
        if e.student_id in student_ids and e.numero_repitencias and e.numero_repitencias > 1:
            repitentes_ids.add(e.student_id)

    docentes_q = db.query(func.count(distinct(Grade.docente))).filter(
        Grade.docente.isnot(None), Grade.docente != "")
    docentes_q, _ = apply_periodo_filter(docentes_q, periodo, include_null=_include_null)
    if carrera and _carrera_sids:
        docentes_q = docentes_q.filter(Grade.student_id.in_(_carrera_sids))
    total_docentes = docentes_q.scalar() or 0
    # Fallback: si no hay docentes en grades, usar enrollment
    if total_docentes == 0 and enrollments:
        docentes_enroll = set(e.docente for e in enrollments if e.docente)
        total_docentes = len(docentes_enroll)

    def compute_stats(student_list, grade_list):
        total = len(student_list)
        if total == 0:
            return {}

        niveles = {}
        for s in student_list:
            niv = s.nivel_academico or 0
            niveles[niv] = niveles.get(niv, 0) + 1

        riesgo = {"Alto": 0, "Medio": 0, "Bajo": 0}
        for s in student_list:
            r = s.nivel_riesgo
            if r and r in riesgo:
                riesgo[r] += 1

        ciudades = {}
        for s in student_list:
            c = s.ciudad or "Sin dato"
            ciudades[c] = ciudades.get(c, 0) + 1

        sedes = {}
        if periodo_filter not in ("actual", "todos"):
            sede_students = {}
            for g in grade_list:
                sede = g.sede or "Sin dato"
                sede_students.setdefault(sede, set()).add(g.student_id)
            sedes = {k: len(v) for k, v in sede_students.items()}
        else:
            for s in student_list:
                sede = s.sede or "Sin dato"
                sedes[sede] = sedes.get(sede, 0) + 1

        generos = {}
        for s in student_list:
            g = s.genero or "Sin dato"
            generos[g] = generos.get(g, 0) + 1

        etnias = {}
        for s in student_list:
            e = s.autoidentificacion_etnica or "Sin dato"
            etnias[e] = etnias.get(e, 0) + 1

        edades = []
        for s in student_list:
            if s.fecha_nacimiento:
                edades.append((today - s.fecha_nacimiento).days / 365.25)
        promedio_edad = round(sum(edades) / len(edades), 1) if edades else None

        sid_set = set(s.id for s in student_list)
        notas_por_est = {}
        for g in grade_list:
            if g.student_id in sid_set and g.nota_final is not None:
                nf = g.nota_final
                if isinstance(nf, float) and (_math_isnan(nf) or _math_isinf(nf)):
                    continue
                notas_por_est.setdefault(g.student_id, []).append(nf)
        if notas_por_est:
            promedios_ind = [sum(ns) / len(ns) for ns in notas_por_est.values()]
            promedio_calif = round(sum(promedios_ind) / len(promedios_ind), 1)
        else:
            promedio_calif = None

        estados = {}
        for s in student_list:
            est = s.estado_matricula or "Sin dato"
            estados[est] = estados.get(est, 0) + 1

        reprob = len(reprobados_ids & sid_set)
        repit = len(repitentes_ids & sid_set)
        desertores_prob = sum(1 for s in student_list if s.prob_desercion and s.prob_desercion > 0.5)
        compromisos = [s.indice_compromiso for s in student_list
                       if s.indice_compromiso is not None
                       and not (isinstance(s.indice_compromiso, float) and (_math_isnan(s.indice_compromiso) or _math_isinf(s.indice_compromiso)))]
        promedio_comp = round(sum(compromisos) / len(compromisos), 2) if compromisos else None
        con_riesgo = sum(1 for s in student_list if s.nivel_riesgo)
        con_calif = len(notas_por_est)

        return {
            "total_estudiantes": total, "con_riesgo_calculado": con_riesgo,
            "con_calificaciones": con_calif, "por_nivel": dict(sorted(niveles.items())),
            "por_riesgo": riesgo, "reprobados": reprob, "repitentes": repit,
            "desertores_prob": desertores_prob, "promedio_calificaciones": promedio_calif,
            "promedio_edad": promedio_edad, "promedio_compromiso": promedio_comp,
            "por_ciudad": dict(sorted(ciudades.items(), key=lambda x: -x[1])),
            "por_sede": dict(sorted(sedes.items(), key=lambda x: -x[1])),
            "por_genero": generos,
            "por_etnia": dict(sorted(etnias.items(), key=lambda x: -x[1])),
            "por_estado_matricula": estados,
        }

    global_stats = compute_stats(students, grades)
    global_stats["total_docentes"] = total_docentes

    # Métricas de enrollment (carreras, asignaturas, etc.)
    global_stats["total_carreras"] = len(carreras_set)
    global_stats["total_asignaturas"] = len(asignaturas_set)
    # Secciones = combinaciones únicas asignatura × docente
    # Replica exactamente la lógica de Analítica de Asignaturas:
    # 1) Intenta grades GROUP BY (asignatura, docente)
    # 2) Si no hay grades, fallback a enrollment GROUP BY (asignatura, docente)
    secc_q = db.query(Grade.asignatura, Grade.docente)
    secc_q, _ = apply_periodo_filter(secc_q, periodo)
    if carrera and _carrera_sids:
        secc_q = secc_q.filter(Grade.student_id.in_(_carrera_sids))
    secc_q = secc_q.group_by(Grade.asignatura, Grade.docente)
    secciones_count = secc_q.count()
    # Fallback a enrollment (misma lógica que _get_enrollment_results)
    if secciones_count == 0:
        secc_e = db.query(Enrollment.asignatura, Enrollment.docente)
        secc_e, _ = apply_periodo_filter(secc_e, periodo, column=Enrollment.periodo)
        if carrera and _carrera_sids:
            secc_e = secc_e.filter(Enrollment.student_id.in_(_carrera_sids))
        secc_e = secc_e.group_by(Enrollment.asignatura, Enrollment.docente)
        secciones_count = secc_e.count()
    global_stats["total_secciones"] = secciones_count
    global_stats["total_docentes_enrollment"] = len(docentes_enroll_set)
    global_stats["total_matriculas"] = len(enrollments)
    global_stats["por_tipo_asignatura"] = dict(sorted(enroll_por_tipo.items(), key=lambda x: -x[1]))
    global_stats["por_nivel_enrollment"] = dict(sorted(enroll_por_nivel.items()))
    global_stats["matriculas_pagadas"] = enroll_pagado
    global_stats["matriculas_con_repitencia"] = enroll_repitencias
    global_stats["tiene_enrollments"] = len(enrollments) > 0

    # ── Aulas virtuales: contar código_avac distintos en CourseConfig ──
    # Filtrar por semestre activo (consistente con Admin/Cursos)
    aulas_q = db.query(func.count(distinct(CourseConfig.codigo_avac))).filter(
        CourseConfig.codigo_avac.isnot(None),
    )
    if semconfig and semconfig.semestre:
        aulas_q = aulas_q.filter(CourseConfig.semestre == semconfig.semestre)
    if carrera:
        aulas_q = aulas_q.filter(func.lower(CourseConfig.carrera).contains(carrera.lower()))
    global_stats["total_aulas_virtuales"] = aulas_q.scalar() or 0

    # Intervenciones
    interv_base_q = db.query(Intervention)
    if carrera:
        interv_base_q = interv_base_q.filter(func.lower(Intervention.carrera).contains(carrera.lower()))
    if periodo_filter != "todos":
        interv_base_q = interv_base_q.filter(Intervention.student_id.in_(grade_student_ids))

    total_intervenciones = interv_base_q.count()
    por_motivo_interv = interv_base_q.with_entities(Intervention.motivo, func.count(Intervention.id)).group_by(Intervention.motivo).all()
    por_resultado_interv = interv_base_q.with_entities(Intervention.resultado, func.count(Intervention.id)).group_by(Intervention.resultado).all()
    pendientes_seg = interv_base_q.filter(Intervention.requiere_seguimiento == "si").count()
    resueltas = interv_base_q.filter(Intervention.estado == "Recuperado").count()
    interv_por_carrera = interv_base_q.with_entities(Intervention.carrera, func.count(Intervention.id)).group_by(Intervention.carrera).all()

    global_stats["intervenciones"] = {
        "total": total_intervenciones,
        "por_motivo": {m or "Sin motivo": c for m, c in por_motivo_interv},
        "por_resultado": {r or "Sin resultado": c for r, c in por_resultado_interv},
        "pendientes_seguimiento": pendientes_seg, "resueltas": resueltas,
        "por_carrera": {car or "Sin carrera": cnt for car, cnt in interv_por_carrera},
    }

    # Por carrera
    carreras_map = {}
    for s in students:
        carreras_map.setdefault(s.carrera or "Sin carrera", []).append(s)

    docentes_carrera_q = db.query(Student.carrera, func.count(distinct(Grade.docente))).join(
        Grade, Grade.student_id == Student.id).filter(Grade.docente.isnot(None), Grade.docente != "")
    docentes_carrera_q, _ = apply_periodo_filter(docentes_carrera_q, periodo, include_null=_include_null)
    docentes_por_carrera = {r[0]: r[1] for r in docentes_carrera_q.group_by(Student.carrera).all()}

    interv_carrera_motivo = {}
    for inv in interv_base_q.all():
        car = inv.carrera or "Sin carrera"
        interv_carrera_motivo.setdefault(car, {"total": 0, "por_motivo": {}, "pendientes": 0, "resueltas": 0})
        interv_carrera_motivo[car]["total"] += 1
        mot = inv.motivo or "Sin motivo"
        interv_carrera_motivo[car]["por_motivo"][mot] = interv_carrera_motivo[car]["por_motivo"].get(mot, 0) + 1
        if inv.requiere_seguimiento == "si":
            interv_carrera_motivo[car]["pendientes"] += 1
        if inv.estado == "Recuperado":
            interv_carrera_motivo[car]["resueltas"] += 1

    por_carrera = []
    for nombre_carrera, sts in sorted(carreras_map.items()):
        sts_ids = set(s.id for s in sts)
        grades_carrera = [g for g in grades if g.student_id in sts_ids]
        stats = compute_stats(sts, grades_carrera)
        stats["carrera"] = nombre_carrera
        stats["total_docentes"] = docentes_por_carrera.get(nombre_carrera, 0)
        stats["intervenciones"] = interv_carrera_motivo.get(nombre_carrera, {"total": 0, "por_motivo": {}, "pendientes": 0, "resueltas": 0})
        por_carrera.append(stats)

    return {"global": global_stats, "por_carrera": por_carrera, "tiene_datos_periodo": tiene_datos_periodo}


@router.get("/resumen/estudiantes-listado")
def get_estudiantes_listado(
    tipo: str = "repitentes",
    carrera: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista de estudiantes filtrados por tipo: repitentes, riesgo_alto, riesgo_medio, riesgo_bajo.
    Usado por las tarjetas KPI clickeables en Resumen de Datos."""
    from sqlalchemy import or_

    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()

    # Detectar include_null (periodo activo)
    _include_null = False
    if periodo and periodo not in ("actual", "todos"):
        try:
            if semconfig and semconfig.semestre:
                a = semconfig.semestre.strip()
                pn = periodo.strip()
                _include_null = (a == pn or
                                 (a.startswith("P") and a[1:] == pn) or
                                 f"P{a}" == pn)
        except Exception:
            pass

    _carrera_sids = None
    if carrera:
        _carrera_sids = set(s_id for (s_id,) in db.query(Student.id).filter(
            func.lower(Student.carrera).contains(carrera.lower())).all())

    # Obtener student_ids del periodo
    union_sq, periodo_filter = _resumen_period_student_ids(db, periodo, _carrera_sids)
    all_period_sids = set(r[0] for r in union_sq.all())

    base_q = db.query(Student)
    if carrera:
        base_q = base_q.filter(func.lower(Student.carrera).contains(carrera.lower()))
    if periodo_filter != "todos":
        base_q = base_q.filter(Student.id.in_(all_period_sids))

    if tipo in ("riesgo_alto", "riesgo_medio", "riesgo_bajo"):
        nivel_map = {"riesgo_alto": "Alto", "riesgo_medio": "Medio", "riesgo_bajo": "Bajo"}
        base_q = base_q.filter(Student.nivel_riesgo == nivel_map[tipo])
        students = base_q.order_by(Student.nombre).all()
    elif tipo == "repitentes":
        # Repitentes: estudiantes con numero_repitencias > 1 en grades o enrollments
        grades_rep_q = db.query(Grade.student_id, Grade.asignatura).filter(Grade.numero_repitencias > 1)
        grades_rep_q, _ = apply_periodo_filter(grades_rep_q, periodo, include_null=_include_null)
        enroll_rep_q = db.query(Enrollment.student_id, Enrollment.asignatura).filter(Enrollment.numero_repitencias > 1)
        enroll_rep_q, _ = apply_periodo_filter(enroll_rep_q, periodo, column=Enrollment.periodo)

        # Build lookup: student_id → set of asignaturas con repitencia
        asig_repitencia = {}
        for sid, asig in grades_rep_q.all():
            asig_repitencia.setdefault(sid, set()).add(asig or "Sin asignatura")
        for sid, asig in enroll_rep_q.all():
            asig_repitencia.setdefault(sid, set()).add(asig or "Sin asignatura")

        repitente_sids = set(asig_repitencia.keys())
        if carrera and _carrera_sids:
            repitente_sids &= _carrera_sids
        repitente_sids &= all_period_sids

        students = db.query(Student).filter(Student.id.in_(repitente_sids)).order_by(Student.nombre).all()
    else:
        return {"tipo": tipo, "total": 0, "estudiantes": [], "error": "Tipo no válido"}

    resultado = []
    for s in students:
        item = {
            "id": s.id,
            "cedula": s.cedula,
            "nombre": s.nombre,
            "correo_institucional": s.correo_institucional,
            "carrera": s.carrera,
            "nivel_academico": s.nivel_academico,
            "nivel_riesgo": s.nivel_riesgo,
            "indice_compromiso": s.indice_compromiso,
            "promedio_calificaciones": s.promedio_calificaciones,
            "dias_sin_acceso": s.dias_sin_acceso,
            "porcentaje_tareas": s.porcentaje_tareas,
            "estado_matricula": s.estado_matricula,
        }
        if tipo == "repitentes":
            item["asignaturas_repitencia"] = sorted(asig_repitencia.get(s.id, []))
        resultado.append(item)

    return {"tipo": tipo, "total": len(resultado), "estudiantes": resultado}


@router.get("/comparativa")
def get_comparativa(
    carrera: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KPIs por período para gráficos de tendencia."""
    periodos_raw = db.query(Grade.periodo).distinct().order_by(Grade.periodo).all()
    periodos = [p for (p,) in periodos_raw if p is not None]
    periodos.append("actual")

    _comp_sids = None
    if carrera:
        _comp_sids = set(s_id for (s_id,) in db.query(Student.id).filter(
            func.lower(Student.carrera).contains(carrera.lower())).all())

    import math

    def _safe_float(v):
        """Convierte NaN/Inf a None para serialización JSON."""
        if v is None:
            return None
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    result = []
    for per in periodos:
        g_q = db.query(Grade)
        if per == "actual":
            g_q = g_q.filter(Grade.periodo.is_(None))
        else:
            g_q = g_q.filter(Grade.periodo == per)
        if carrera and _comp_sids:
            g_q = g_q.filter(Grade.student_id.in_(_comp_sids))

        gs = g_q.all()
        if not gs:
            continue

        sids = set(g.student_id for g in gs)
        notas_por_est = {}
        for g in gs:
            if g.nota_final is not None and not (isinstance(g.nota_final, float) and (math.isnan(g.nota_final) or math.isinf(g.nota_final))):
                notas_por_est.setdefault(g.student_id, []).append(g.nota_final)

        promedio_calif = None
        tasa_aprob = None
        if notas_por_est:
            promedios = [sum(ns) / len(ns) for ns in notas_por_est.values()]
            promedio_calif = _safe_float(round(sum(promedios) / len(promedios), 1))
            aprobados = sum(1 for ns in notas_por_est.values() if (sum(ns) / len(ns)) >= nota_aprob)
            tasa_aprob = _safe_float(round(aprobados / len(notas_por_est) * 100, 1))

        riesgo_alto = db.query(func.count(Student.id)).filter(
            Student.id.in_(sids), Student.nivel_riesgo == "Alto").scalar() or 0
        docentes_set = set(g.docente for g in gs if g.docente)
        total_interv = db.query(func.count(Intervention.id)).filter(
            Intervention.student_id.in_(sids)).scalar() or 0

        result.append({
            "periodo": per, "label": "Actual" if per == "actual" else per,
            "total_estudiantes": len(sids), "promedio_calificaciones": _safe_float(promedio_calif),
            "tasa_aprobacion": _safe_float(tasa_aprob), "riesgo_alto": riesgo_alto,
            "total_docentes": len(docentes_set), "total_intervenciones": total_interv,
        })

    return result
