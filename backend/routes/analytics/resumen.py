"""
Módulos 8.5: Resumen de Datos + Comparativa + Períodos.
Separado de analytics.py monolítico — [ARCH-03] Remediación.

Contiene: /analytics/periodos, /analytics/resumen, /analytics/comparativa
"""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from ...database import get_db
from ...models import Student, Grade, Intervention
from ...auth.jwt import get_current_user
from ...models.user import User
from ._helpers import apply_periodo_filter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/periodos")
def get_periodos_disponibles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista de períodos disponibles en calificaciones."""
    periodos_raw = db.query(Grade.periodo).distinct().all()
    periodos = []
    for (p,) in periodos_raw:
        if p is None:
            periodos.append({"key": "actual", "label": "Semestre actual"})
        else:
            periodos.append({"key": p, "label": p})
    periodos.sort(key=lambda x: ("0" if x["key"] == "actual" else "1" + x["key"]), reverse=True)
    periodos.reverse()
    return periodos


@router.get("/resumen")
def get_resumen_datos(
    carrera: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen estadístico general y por carrera."""
    today = date.today()

    _carrera_sids = None
    if carrera:
        _carrera_sids = set(s_id for (s_id,) in db.query(Student.id).filter(
            func.lower(Student.carrera).contains(carrera.lower())).all())

    grades_q = db.query(Grade)
    grades_q, periodo_filter = apply_periodo_filter(grades_q, periodo)
    if carrera and _carrera_sids:
        grades_q = grades_q.filter(Grade.student_id.in_(_carrera_sids))
    grades = grades_q.all()
    grade_student_ids = set(g.student_id for g in grades)

    base_q = db.query(Student)
    if carrera:
        base_q = base_q.filter(func.lower(Student.carrera).contains(carrera.lower()))
    if periodo_filter != "todos":
        base_q = base_q.filter(Student.id.in_(grade_student_ids))
    students = base_q.all()

    if not students:
        return {"global": {}, "por_carrera": [], "periodos_disponibles": []}

    student_ids = set(s.id for s in students)

    reprobados_ids = set()
    repitentes_ids = set()
    for g in grades:
        if g.student_id in student_ids:
            if g.nota_final is not None and g.nota_final < 70:
                reprobados_ids.add(g.student_id)
            if g.numero_repitencias and g.numero_repitencias > 0:
                repitentes_ids.add(g.student_id)

    docentes_q = db.query(func.count(distinct(Grade.docente))).filter(
        Grade.docente.isnot(None), Grade.docente != "")
    docentes_q, _ = apply_periodo_filter(docentes_q, periodo)
    if carrera and _carrera_sids:
        docentes_q = docentes_q.filter(Grade.student_id.in_(_carrera_sids))
    total_docentes = docentes_q.scalar() or 0

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
                notas_por_est.setdefault(g.student_id, []).append(g.nota_final)
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
        compromisos = [s.indice_compromiso for s in student_list if s.indice_compromiso is not None]
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
    docentes_carrera_q, _ = apply_periodo_filter(docentes_carrera_q, periodo)
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

    return {"global": global_stats, "por_carrera": por_carrera}


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
            if g.nota_final is not None:
                notas_por_est.setdefault(g.student_id, []).append(g.nota_final)

        promedio_calif = None
        tasa_aprob = None
        if notas_por_est:
            promedios = [sum(ns) / len(ns) for ns in notas_por_est.values()]
            promedio_calif = round(sum(promedios) / len(promedios), 1)
            aprobados = sum(1 for ns in notas_por_est.values() if (sum(ns) / len(ns)) >= 70)
            tasa_aprob = round(aprobados / len(notas_por_est) * 100, 1)

        riesgo_alto = db.query(func.count(Student.id)).filter(
            Student.id.in_(sids), Student.nivel_riesgo == "Alto").scalar() or 0
        docentes_set = set(g.docente for g in gs if g.docente)
        total_interv = db.query(func.count(Intervention.id)).filter(
            Intervention.student_id.in_(sids)).scalar() or 0

        result.append({
            "periodo": per, "label": "Actual" if per == "actual" else per,
            "total_estudiantes": len(sids), "promedio_calificaciones": promedio_calif,
            "tasa_aprobacion": tasa_aprob, "riesgo_alto": riesgo_alto,
            "total_docentes": len(docentes_set), "total_intervenciones": total_interv,
        })

    return result
