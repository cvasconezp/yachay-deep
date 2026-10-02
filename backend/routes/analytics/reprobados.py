"""
Módulo: Analítica de Reprobados.

Informe por período · carrera · nivel de los estudiantes que REPROBARON al menos
una asignatura (Grade.nota_final < umbral de aprobación), con los indicadores que
dan "luces" sobre el porqué y el posible abandono:

- Académicos: nº de asignaturas reprobadas y cuáles (con su nota), promedio del
  período, repitencia / 3ra matrícula.
- Conductuales (desconexión): índice de compromiso, días desde el último acceso a
  AVAC, % de tareas entregadas.
- Administrativos: estado de matrícula.
- Seguimiento: nº de intervenciones registradas, última fecha y si quedó sin
  respuesta / con seguimiento pendiente.
- Predictivos: prob. de reprobación, prob. de deserción y score de recuperabilidad.
- `causa_probable`: una etiqueta heurística (Administrativa / Desconexión /
  Académica) para priorizar la lectura; los indicadores crudos permiten matizarla.

Sigue las convenciones del módulo Grupos: carrera vía Student, filtros de período
dual-format, umbrales configurables. Solo rol admin (require_admin).
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...database import get_db
from ...models import Student, Grade, Enrollment, Intervention
from ...auth.jwt import require_admin
from ...models.user import User
from ._helpers import apply_periodo_filter, get_umbrales, normalize_riesgo

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AsignaturaReprobada(BaseModel):
    asignatura: str
    nota: Optional[float] = None


class ReprobadoEstudiante(BaseModel):
    student_id: int
    nombre: Optional[str] = None
    carrera: Optional[str] = None
    nivel: Optional[int] = None
    grupo: Optional[str] = None
    # Académico
    num_reprobadas: int = 0
    reprobadas: list[AsignaturaReprobada] = []
    promedio: Optional[float] = None
    es_tercera_matricula: bool = False
    es_repitente: bool = False
    # Conductual / riesgo
    nivel_riesgo: Optional[str] = None
    indice_compromiso: Optional[float] = None
    dias_sin_acceso: Optional[int] = None       # último acceso real (MÍN entre aulas)
    porcentaje_tareas: Optional[float] = None
    estado_matricula: Optional[str] = None
    # Predictivo
    prob_reprobacion: Optional[float] = None
    prob_desercion: Optional[float] = None
    score_recuperabilidad: Optional[float] = None
    # Seguimiento
    num_intervenciones: int = 0
    ultima_intervencion: Optional[str] = None
    intervencion_sin_respuesta: bool = False
    sin_intervencion: bool = True
    # Síntesis
    causa_probable: Optional[str] = None


class ReprobadosKPIs(BaseModel):
    total_reprobados: int = 0
    total_asignaturas_reprobadas: int = 0
    promedio_reprobados: Optional[float] = None
    riesgo_alto: int = 0
    sin_intervencion: int = 0
    por_causa: dict[str, int] = {}


class ReprobadosAnalytics(BaseModel):
    periodo: Optional[str] = None
    carrera: Optional[str] = None
    nivel: Optional[int] = None
    nota_aprobacion: float = 70.0
    estudiantes: list[ReprobadoEstudiante] = []
    kpis: ReprobadosKPIs = ReprobadosKPIs()

    class Config:
        from_attributes = True


# Resultados de intervención que indican que el estudiante NO respondió / sigue abierto.
_SIN_RESPUESTA = {
    "no contesto", "no contestó", "no contactado", "sin respuesta", "sna",
    "no respondio", "no respondió", "pendiente", "sin contactar",
}


def _clasificar_causa(est: dict, umbrales: dict) -> str:
    """Etiqueta heurística de la causa probable (para priorizar la lectura).

    Prioridad: Administrativa (compuerta) → Desconexión → Académica. Si no hay
    señales conductuales ni administrativas, se asume académica (bajó notas pese a
    mantenerse conectado). 'Sin datos' cuando faltan los indicadores base.
    """
    estado = (est.get("estado_matricula") or "").strip().lower()
    admin_irregular = bool(estado) and "matriculad" not in estado

    ic = est.get("indice_compromiso")
    dias = est.get("dias_sin_acceso")
    tareas = est.get("porcentaje_tareas")
    desconexion = (
        (ic is not None and ic < umbrales["compromiso_minimo"]) or
        (dias is not None and dias >= umbrales["dias_inactividad"]) or
        (tareas is not None and tareas < umbrales["tareas_minimo"])
    )

    if admin_irregular:
        return "Administrativa"
    if desconexion:
        return "Desconexión"
    if ic is None and dias is None and tareas is None:
        return "Sin datos"
    return "Académica"


@router.get("/reprobados", response_model=ReprobadosAnalytics)
def get_reprobados_analytics(
    periodo: Optional[str] = None,
    carrera: Optional[str] = None,
    nivel: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Informe de reprobados (período · carrera · nivel) con indicadores de porqué."""
    umbrales = get_umbrales(db)
    nota_aprob = umbrales["nota_aprobacion"]

    # ── Carrera vía Student (Grade.carrera suele venir vacío), igual que Grupos ──
    carrera_sids: Optional[list[int]] = None
    if carrera:
        carrera_sids = [
            sid for (sid,) in db.query(Student.id).filter(
                func.lower(Student.carrera).contains(carrera.lower())
            ).all()
        ]
        if not carrera_sids:
            _, periodo_norm = apply_periodo_filter(db.query(Grade.id), periodo)
            return ReprobadosAnalytics(
                periodo=periodo_norm, carrera=carrera, nivel=nivel,
                nota_aprobacion=nota_aprob,
            )

    # ── Calificaciones del período ──
    gq = db.query(
        Grade.student_id, Grade.asignatura, Grade.nota_final,
        Grade.nivel, Grade.numero_repitencias,
    ).filter(Grade.nota_final.isnot(None))
    gq, periodo_norm = apply_periodo_filter(gq, periodo, include_null=True)
    if carrera_sids is not None:
        gq = gq.filter(Grade.student_id.in_(carrera_sids))
    if nivel is not None:
        gq = gq.filter(Grade.nivel == nivel)
    grade_rows = gq.all()

    # ── Agregar por estudiante: notas, reprobadas, nivel, repitencia ──
    agg: dict[int, dict] = {}
    for sid, asig, nota, niv, nrep in grade_rows:
        a = agg.setdefault(sid, {
            "notas": [], "reprobadas": [], "nivel": None, "repitente": False,
        })
        if nota is not None:
            a["notas"].append(float(nota))
            if float(nota) < nota_aprob:
                a["reprobadas"].append((str(asig or "").strip(), float(nota)))
        if niv is not None and a["nivel"] is None:
            a["nivel"] = int(niv)
        if nrep is not None and int(nrep) > 1:
            a["repitente"] = True

    reprobado_sids = [sid for sid, a in agg.items() if a["reprobadas"]]
    if not reprobado_sids:
        return ReprobadosAnalytics(
            periodo=periodo_norm, carrera=carrera, nivel=nivel,
            nota_aprobacion=nota_aprob,
        )

    # ── Datos del estudiante (bulk) ──
    students = {
        s.id: s for s in db.query(Student).filter(Student.id.in_(reprobado_sids)).all()
    }

    # ── Grupo/paralelo y repitencia desde Enrollment del período (bulk) ──
    grupo_by_sid: dict[int, str] = {}
    eq = db.query(Enrollment.student_id, Enrollment.nombre_grupo, Enrollment.numero_repitencias)
    eq, _ = apply_periodo_filter(eq, periodo, column=Enrollment.periodo)
    eq = eq.filter(Enrollment.student_id.in_(reprobado_sids))
    for sid, nombre_grupo, nrep in eq.all():
        if sid not in grupo_by_sid and nombre_grupo:
            grupo_by_sid[sid] = str(nombre_grupo).strip()
        if nrep and int(nrep) > 1 and sid in agg:
            agg[sid]["repitente"] = True

    # ── Intervenciones (bulk): conteo, última y si quedó sin respuesta ──
    interv: dict[int, dict] = {}
    iq = (
        db.query(Intervention)
        .filter(Intervention.student_id.in_(reprobado_sids))
        .order_by(Intervention.student_id, Intervention.created_at)
        .all()
    )
    for iv in iq:
        d = interv.setdefault(iv.student_id, {"count": 0, "ultima": None, "last": None})
        d["count"] += 1
        d["ultima"] = iv.created_at
        d["last"] = iv

    estudiantes: list[ReprobadoEstudiante] = []
    kpi_causa: dict[str, int] = {}
    total_asig_rep = 0
    sin_interv_count = 0
    riesgo_alto = 0
    promedios_acum: list[float] = []

    for sid in reprobado_sids:
        a = agg[sid]
        s = students.get(sid)
        if s is None:
            continue
        reprobadas = sorted(a["reprobadas"], key=lambda x: x[1])  # peor nota primero
        promedio = round(sum(a["notas"]) / len(a["notas"]), 1) if a["notas"] else None
        total_asig_rep += len(reprobadas)
        if promedio is not None:
            promedios_acum.append(promedio)

        iv = interv.get(sid)
        num_interv = iv["count"] if iv else 0
        ultima = iv["ultima"].date().isoformat() if iv and iv["ultima"] else None
        sin_respuesta = False
        if iv and iv["last"] is not None:
            last = iv["last"]
            resultado = (last.resultado or "").strip().lower()
            req_seg = (last.requiere_seguimiento or "").strip().lower()
            sin_respuesta = (resultado in _SIN_RESPUESTA) or (req_seg == "si")
        sin_interv = num_interv == 0
        if sin_interv:
            sin_interv_count += 1

        est_dict = {
            "estado_matricula": s.estado_matricula,
            "indice_compromiso": s.indice_compromiso,
            "dias_sin_acceso": s.dias_desde_ultimo_acceso,  # último acceso real
            "porcentaje_tareas": s.porcentaje_tareas,
        }
        causa = _clasificar_causa(est_dict, umbrales)
        kpi_causa[causa] = kpi_causa.get(causa, 0) + 1

        nr = normalize_riesgo(s.nivel_riesgo)
        if nr == "Alto":
            riesgo_alto += 1

        estudiantes.append(ReprobadoEstudiante(
            student_id=sid,
            nombre=s.nombre,
            carrera=s.carrera,
            nivel=a["nivel"],
            grupo=grupo_by_sid.get(sid) or s.grupo,
            num_reprobadas=len(reprobadas),
            reprobadas=[AsignaturaReprobada(asignatura=n, nota=nt) for n, nt in reprobadas],
            promedio=promedio,
            es_tercera_matricula=bool(s.es_tercera_matricula),
            es_repitente=bool(a["repitente"]),
            nivel_riesgo=nr,
            indice_compromiso=s.indice_compromiso,
            dias_sin_acceso=s.dias_desde_ultimo_acceso,
            porcentaje_tareas=s.porcentaje_tareas,
            estado_matricula=s.estado_matricula,
            prob_reprobacion=s.prob_reprobacion,
            prob_desercion=s.prob_desercion,
            score_recuperabilidad=s.score_recuperabilidad,
            num_intervenciones=num_interv,
            ultima_intervencion=ultima,
            intervencion_sin_respuesta=sin_respuesta,
            sin_intervencion=sin_interv,
            causa_probable=causa,
        ))

    # Ordenar: más asignaturas reprobadas primero, luego peor promedio
    estudiantes.sort(key=lambda e: (-e.num_reprobadas, e.promedio if e.promedio is not None else 999))

    kpis = ReprobadosKPIs(
        total_reprobados=len(estudiantes),
        total_asignaturas_reprobadas=total_asig_rep,
        promedio_reprobados=round(sum(promedios_acum) / len(promedios_acum), 1) if promedios_acum else None,
        riesgo_alto=riesgo_alto,
        sin_intervencion=sin_interv_count,
        por_causa=kpi_causa,
    )

    return ReprobadosAnalytics(
        periodo=periodo_norm, carrera=carrera, nivel=nivel,
        nota_aprobacion=nota_aprob, estudiantes=estudiantes, kpis=kpis,
    )
