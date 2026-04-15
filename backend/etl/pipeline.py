"""
Pipeline ETL principal — orquesta la carga completa a la base de datos.
Reemplaza la actualización manual de Power Query en el Excel.
Soporta filtrado por bloque activo usando SemesterConfig.
"""
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, text as sa_text

from .transformers import (
    transform_ingresos_avac,
    transform_estado_tareas,
    transform_calificaciones,
    transform_calificaciones_historico,
    transform_personales,
    transform_datos_especificos,
    calcular_indicadores_estudiantes,
    extract_courses_from_reporte,
    transform_resumen_general,
    transform_enrollments,
)
from ..models import Student, AvacAccess, TaskSubmission, Grade, ScrapingRun, DocenteTracking, Enrollment
from ..models.course_config import CourseConfig, SemesterConfig
from ..constants import EIB_GRUPO_SEDE
from ..config import settings

logger = logging.getLogger(__name__)


def _clean_str(val) -> str:
    """Convierte a string limpio; retorna '' si el valor es NaN/None/nan."""
    s = str(val or "").strip()
    return "" if s.lower() in ("nan", "none", "null") else s


def _normalize_name(nombre: str) -> str:
    """
    Normaliza un nombre para comparación: elimina tildes, diéresis y caracteres
    especiales, colapsa espacios múltiples y convierte a mayúsculas.

    Ejemplos:
        "ACHIÑA INUCA RUBY MARITHZA" → "ACHINA INUCA RUBY MARITHZA"
        "GARCÍA  LÓPEZ  MARÍA" → "GARCIA LOPEZ MARIA"
        "PÉREZ ÑUÑEZ ANA" → "PEREZ NUNEZ ANA"
    """
    if not nombre:
        return ""
    # Paso 1: mayúsculas y colapsar espacios
    s = re.sub(r"\s+", " ", nombre.strip().upper())
    # Paso 2: descomponer Unicode (NFD) para separar letras base de diacríticos
    # Ej: "Ñ" → "N" + "~" (combining tilde), "á" → "a" + "´" (combining acute)
    s = unicodedata.normalize("NFD", s)
    # Paso 3: eliminar los diacríticos (categoría Unicode "Mn" = Mark, Nonspacing)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


class ETLPipeline:
    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # CONFIG: bloque activo y cursos
    # ─────────────────────────────────────────────────────────────────────────

    def _get_active_semester(self) -> Optional[SemesterConfig]:
        """Devuelve el SemesterConfig activo, o None si no hay ninguno."""
        return (
            self.db.query(SemesterConfig)
            .filter(SemesterConfig.activo == True)
            .first()
        )

    def _auto_activate_semester(self, sem_label: str, logs: list) -> bool:
        """
        Auto-detecta y activa un nuevo período desde el reporte.
        Si el período del reporte (ej. P68) no coincide con el semestre activo,
        desactiva el anterior y crea/activa el nuevo.
        También migra datos del semestre anterior: calificaciones con periodo=NULL
        se etiquetan con el semestre saliente.
        Retorna True si se activó un nuevo semestre.
        """
        from ..models import Grade
        from ..models.course import Course

        current = self._get_active_semester()
        if current and current.semestre == sem_label:
            return False  # ya es el semestre activo

        previous_label = current.semestre if current else None

        # ── Migrar datos del semestre anterior ──
        # Calificaciones con periodo=NULL → periodo del semestre saliente
        if previous_label:
            n_grades = self.db.query(Grade).filter(
                Grade.periodo.is_(None)
            ).update({"periodo": previous_label}, synchronize_session=False)
            if n_grades:
                logs.append(f"  📋 {n_grades} calificaciones migradas de periodo=NULL → {previous_label}")
                logger.info("Migradas %d calificaciones a periodo=%s", n_grades, previous_label)

            # Cursos (Course) sin periodo → asignar periodo anterior
            n_courses = self.db.query(Course).filter(
                Course.periodo.is_(None)
            ).update({"periodo": previous_label}, synchronize_session=False)
            if n_courses:
                logs.append(f"  📋 {n_courses} cursos migrados de periodo=NULL → {previous_label}")

            self.db.flush()

        # Desactivar todos los semestres anteriores
        self.db.query(SemesterConfig).filter(
            SemesterConfig.activo == True
        ).update({"activo": False})

        # Buscar o crear el nuevo semestre
        new_sem = self.db.query(SemesterConfig).filter(
            SemesterConfig.semestre == sem_label
        ).first()
        if not new_sem:
            new_sem = SemesterConfig(
                semestre=sem_label,
                activo=True,
                bloque_actual="1",
                bloque1_inicio=datetime.now(timezone.utc),
            )
            self.db.add(new_sem)
            logs.append(f"  🆕 Nuevo semestre {sem_label} creado y activado automáticamente")
        else:
            new_sem.activo = True
            logs.append(f"  🔄 Semestre {sem_label} activado automáticamente")

        self.db.flush()
        logger.info("SemesterConfig auto-activado: %s", sem_label)
        return True

    def _get_codigos_for_bloque(self, semconfig: Optional[SemesterConfig]) -> Optional[List[str]]:
        """
        Devuelve lista de códigos AVAC activos para el bloque actual.
        Si no hay semconfig configurado, devuelve None (sin filtro → procesa todo).
        """
        if semconfig is None:
            return None

        bloque = semconfig.bloque_actual  # "1", "2", o None

        query = self.db.query(CourseConfig.codigo_avac).filter(
            CourseConfig.semestre == semconfig.semestre,
            CourseConfig.activo == True,
        )

        if bloque:
            query = query.filter(
                (CourseConfig.bloque == bloque) | (CourseConfig.bloque == "ambos")
            )

        codigos = [row[0] for row in query.all()]
        return codigos if codigos else None

    # ─────────────────────────────────────────────────────────────────────────
    # PIPELINE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def run_full(self, triggered_by: str = "manual") -> ScrapingRun:
        """Ejecuta el pipeline completo: ingresos + tareas + calificaciones."""
        run = ScrapingRun(tipo="full", status="running", triggered_by=triggered_by,
                         descripcion="Pipeline ETL completo: ingresos, tareas, calificaciones, reportes")
        self.db.add(run)
        self.db.commit()

        logs = []
        errores = []
        total_registros = 0

        try:
            # Obtener config del semestre/bloque activo
            semconfig = self._get_active_semester()
            codigos_activos = self._get_codigos_for_bloque(semconfig)

            # Flag: si el semestre ya terminó, omitir scraping de AVAC/tareas
            # pero permitir carga de histórico y recálculo ML
            semestre_vigente = True
            if semconfig:
                bloque_info = f"semestre={semconfig.semestre}, bloque={semconfig.bloque_actual}"
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Config activa: {bloque_info}")
                if semconfig.semestre_finalizado:
                    semestre_vigente = False
                    logs.append(
                        f"  ⚠️ Semestre {semconfig.semestre} finalizó el {semconfig.fecha_fin_actual}. "
                        "Los indicadores de acceso AVAC no se actualizarán para evitar alertas falsas."
                    )
                elif codigos_activos:
                    logs.append(f"  → Filtrando por {len(codigos_activos)} cursos del bloque {semconfig.bloque_actual}")
                else:
                    logs.append("  ⚠️ Sin cursos configurados para este bloque — procesando todos los CSVs")
            else:
                semestre_vigente = False
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sin semestre activo — procesando todos los CSVs")

            # 1. Cargar y transformar fuentes
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Leyendo datos personales (reporte.xlsx)...")
            df_personales = transform_personales(settings.DATA_PATH_REPORTE)
            logs.append(f"  → {len(df_personales)} estudiantes con datos personales")

            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Leyendo DatosEspecificos EIB...")
            df_datos_especificos = transform_datos_especificos(settings.DATA_PATH_DATOS_ESPECIFICOS)
            logs.append(f"  → {len(df_datos_especificos)} estudiantes con datos específicos EIB")

            if semestre_vigente:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Leyendo IngresosAVAC...")
                df_ingresos = transform_ingresos_avac(
                    settings.DATA_PATH_INGRESOS,
                    codigos_activos=codigos_activos,
                )
                logs.append(f"  → {len(df_ingresos)} registros de acceso AVAC")

                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Leyendo Tareas...")
                df_tareas = transform_estado_tareas(
                    settings.DATA_PATH_TAREAS,
                    codigos_activos=codigos_activos,
                )
                logs.append(f"  → {len(df_tareas)} registros de tareas")
            else:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏸ Semestre finalizado — omitiendo lectura de IngresosAVAC y Tareas")
                df_ingresos = pd.DataFrame()
                df_tareas = pd.DataFrame()

            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Leyendo Calificaciones...")
            df_calificaciones = transform_calificaciones(settings.DATA_PATH_CALIFICACIONES)

            # Fallback: si calificaciones.csv no existe o está vacío,
            # usar el último archivo del TableauHistorico (P67) como semestre activo
            used_historico_fallback = False
            if df_calificaciones.empty:
                hist_path = Path(settings.DATA_PATH_CALIFICACIONES_HISTORICO)
                hist_files = sorted(hist_path.glob("*.csv"))
                if hist_files:
                    latest_hist = hist_files[-1]  # último archivo (ej. P67)
                    logs.append(f"  ⚠️ calificaciones.csv no encontrado/vacío, usando fallback: {latest_hist.name}")
                    df_calificaciones = transform_calificaciones(str(latest_hist))
                    used_historico_fallback = True
                    # Extraer código de período del nombre para excluirlo del histórico
                    _m = re.search(r'\(P(\d+)\)', latest_hist.name, re.IGNORECASE)
                    self._fallback_periodo = f"P{_m.group(1)}" if _m else None
                else:
                    self._fallback_periodo = None
            else:
                self._fallback_periodo = None

            logs.append(f"  → {len(df_calificaciones)} registros de calificaciones{' (fallback TableauHistorico)' if used_historico_fallback else ''}")

            # Enriquecer calificaciones con NIVEL y NUMERO_REPITENCIAS del reporte si falta
            # (P67 CSV no tiene estas columnas; el reporte.xlsx sí)
            _need_nivel = ("nivel" not in df_calificaciones.columns or df_calificaciones["nivel"].isna().all())
            _need_repitencias = ("numero_repitencias" not in df_calificaciones.columns or df_calificaciones["numero_repitencias"].isna().all())

            if not df_calificaciones.empty and (_need_nivel or _need_repitencias):
                # Construir mapas (nombre, asignatura) → nivel / repitencias desde el reporte
                reporte_path = Path(settings.DATA_PATH_REPORTE)
                _nivel_map = {}
                _rep_map = {}
                if reporte_path.is_dir():
                    for _rf in sorted(reporte_path.glob("*_reporte.xlsx")):
                        try:
                            _rdf = pd.read_excel(_rf, engine="openpyxl")
                            _rdf.columns = [c.strip().upper() for c in _rdf.columns]
                            if "ESTUDIANTES" not in _rdf.columns or "ASIGNATURA" not in _rdf.columns:
                                continue
                            _has_nivel = "NIVEL" in _rdf.columns
                            # NUMERO_REPITENCIAS puede venir con o sin guion bajo
                            _rep_col = next(
                                (c for c in _rdf.columns if "REPITENCIA" in c),
                                None,
                            )
                            for _, _rr in _rdf.iterrows():
                                _nom = re.sub(r"\s+", " ", str(_rr.get("ESTUDIANTES", "")).strip().upper())
                                _asig = str(_rr.get("ASIGNATURA", "")).strip().upper()
                                if not _nom or not _asig:
                                    continue
                                key = (_nom, _asig)
                                if _has_nivel and _need_nivel:
                                    _niv = _rr.get("NIVEL")
                                    if pd.notna(_niv):
                                        try:
                                            _nivel_map[key] = int(_niv)
                                        except (ValueError, TypeError):
                                            pass
                                if _rep_col and _need_repitencias:
                                    _rep = _rr.get(_rep_col)
                                    if pd.notna(_rep):
                                        try:
                                            _rep_map[key] = int(_rep)
                                        except (ValueError, TypeError):
                                            pass
                        except Exception:
                            pass

                def _enrich_key(row):
                    nom = re.sub(r"\s+", " ", str(row.get("nombre_estudiante", "")).strip().upper())
                    asig = str(row.get("asignatura", "")).strip().upper()
                    return (nom, asig)

                if _nivel_map and _need_nivel:
                    df_calificaciones["nivel"] = df_calificaciones.apply(
                        lambda r: _nivel_map.get(_enrich_key(r)), axis=1
                    )
                    df_calificaciones["nivel"] = pd.to_numeric(df_calificaciones["nivel"], errors="coerce").astype("Int64")
                    _filled = df_calificaciones["nivel"].notna().sum()
                    logs.append(f"  → Enriquecido {_filled}/{len(df_calificaciones)} calificaciones con NIVEL del reporte")

                if _rep_map and _need_repitencias:
                    df_calificaciones["numero_repitencias"] = df_calificaciones.apply(
                        lambda r: _rep_map.get(_enrich_key(r)), axis=1
                    )
                    df_calificaciones["numero_repitencias"] = pd.to_numeric(df_calificaciones["numero_repitencias"], errors="coerce").astype("Int64")
                    _filled_rep = df_calificaciones["numero_repitencias"].notna().sum()
                    logs.append(f"  → Enriquecido {_filled_rep}/{len(df_calificaciones)} calificaciones con NUMERO_REPITENCIAS del reporte")

            # 2a. Sembrar datos personales desde reporte.xlsx SIEMPRE
            #     (nivel_academico, grupo, cédula, carrera, etc.)
            #     Esto debe ejecutarse independientemente de si el semestre está vigente,
            #     porque el reporte es la fuente de verdad para datos demográficos.
            # Limpiar cédulas 'nan' heredadas de corridas anteriores con el bug
            self.db.execute(sa_text("UPDATE students SET cedula = NULL WHERE cedula = 'nan'"))
            self.db.flush()

            if not df_personales.empty:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sembrando estudiantes desde reporte.xlsx...")
                n_seed = self._seed_students_from_personales(df_personales)
                logs.append(f"  → {n_seed} estudiantes inicializados desde reporte")

            # Deduplicar estudiantes con mismo nombre (merge orphans)
            n_merged = self._merge_duplicate_students()
            if n_merged:
                logs.append(f"  → {n_merged} estudiantes duplicados fusionados")

            # 2b. Auto-poblar CourseConfig desde CODIGO_GRUPO del reporte
            try:
                df_courses = extract_courses_from_reporte(settings.DATA_PATH_REPORTE)
                if not df_courses.empty:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sincronizando cursos desde reporte ({len(df_courses)} encontrados)...")
                    n_courses = self._sync_course_configs(df_courses, semconfig.semestre if semconfig else None)
                    logs.append(f"  → {n_courses} cursos sincronizados en course_configs")
            except Exception as e:
                logs.append(f"  ⚠ Error sincronizando cursos: {e}")
                logger.error(f"Error en _sync_course_configs: {e}", exc_info=True)

            # 2c. Cargar asignaturas matriculadas (enrollments) desde reporte
            try:
                df_enrollments = transform_enrollments(settings.DATA_PATH_REPORTE)
                if not df_enrollments.empty:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando asignaturas matriculadas ({len(df_enrollments)} registros)...")
                    n_enrollments = self._upsert_enrollments(df_enrollments)
                    logs.append(f"  → {n_enrollments} asignaturas matriculadas cargadas")

                    # Auto-detectar y activar nuevo período desde el reporte
                    periodo_reporte = df_enrollments["periodo"].dropna().mode()
                    if not periodo_reporte.empty:
                        periodo_str = str(int(periodo_reporte.iloc[0]))
                        sem_label = f"P{periodo_str}"
                        updated = self._auto_activate_semester(sem_label, logs)
                        if updated:
                            # Refrescar semconfig para el resto del pipeline
                            semconfig = self._get_active_semester()
                            semestre_vigente = True
            except Exception as e:
                logs.append(f"  ⚠ Error cargando enrollments: {e}")
                logger.error(f"Error en _upsert_enrollments: {e}", exc_info=True)

            # 2c-bis. Migración única: etiquetar registros huérfanos (periodo=NULL) como P67
            # Cualquier dato cargado antes de 2026-03-30 22:29:25 quedó sin periodo;
            # corresponden al semestre P67.
            try:
                from ..models import Grade as _Grade
                from ..models.course import Course as _Course
                _n_g = self.db.query(_Grade).filter(
                    _Grade.periodo.is_(None)
                ).update({"periodo": "P67"}, synchronize_session=False)
                _n_c = self.db.query(_Course).filter(
                    _Course.periodo.is_(None)
                ).update({"periodo": "P67"}, synchronize_session=False)
                _n_a = self.db.query(AvacAccess).filter(
                    AvacAccess.periodo.is_(None)
                ).update({"periodo": "P67"}, synchronize_session=False)
                _n_t = self.db.query(TaskSubmission).filter(
                    TaskSubmission.periodo.is_(None)
                ).update({"periodo": "P67"}, synchronize_session=False)
                if _n_g or _n_c or _n_a or _n_t:
                    self.db.flush()
                    logs.append(f"  🔧 Migración P67: {_n_g} calificaciones + {_n_c} cursos + {_n_a} accesos AVAC + {_n_t} tareas etiquetados como P67")
                    logger.info("Migración P67: %d grades, %d courses, %d avac, %d tasks", _n_g, _n_c, _n_a, _n_t)
            except Exception as e:
                logs.append(f"  ⚠ Error en migración P67: {e}")
                logger.error("Error en migración P67: %s", e, exc_info=True)

            # 2d. Procesar Resumen_General (seguimiento de calificación docente)
            try:
                df_resumen = transform_resumen_general(settings.DATA_PATH_REPORTE)
                if not df_resumen.empty:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Procesando Resumen_General ({len(df_resumen)} registros)...")
                    n_resumen = self._upsert_resumen_general(df_resumen)
                    logs.append(f"  → {n_resumen} registros de seguimiento docente procesados")
            except Exception as e:
                logs.append(f"  ⚠ Error procesando Resumen_General: {e}")
                logger.error(f"Error en _upsert_resumen_general: {e}", exc_info=True)

            if semestre_vigente:
                # 2b. Calcular indicadores
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando indicadores de riesgo...")
                df_master = calcular_indicadores_estudiantes(df_ingresos, df_tareas, df_calificaciones)

                # 3. Upsert estudiantes con indicadores (actualiza los ya creados)
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Actualizando indicadores de estudiantes...")
                n = self._upsert_students(
                    df_ingresos, df_calificaciones, df_master,
                    df_personales, df_datos_especificos,
                )
                total_registros += n
                logs.append(f"  → {n} estudiantes con indicadores actualizados")

                # 4. Upsert accesos AVAC
                active_periodo = semconfig.semestre if semconfig else None
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando accesos AVAC (periodo={active_periodo})...")
                n = self._upsert_avac_accesses(df_ingresos, periodo=active_periodo)
                total_registros += n
                logs.append(f"  → {n} registros de acceso")

                # 5. Upsert tareas
                if not df_tareas.empty:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando submissions de tareas...")
                    n = self._upsert_task_submissions(df_tareas, periodo=active_periodo)
                    total_registros += n
                    logs.append(f"  → {n} submissions de tareas")

            else:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏸ Semestre finalizado — omitiendo cálculo de indicadores, accesos y tareas")
                df_master = pd.DataFrame()

            # 6. Upsert calificaciones (semestre actual, sin período)
            #    Se ejecuta siempre que haya calificaciones (incluyendo fallback de
            #    TableauHistorico) para que Grade.nivel quede poblado desde el reporte.
            if not df_calificaciones.empty:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando calificaciones...")
                n = self._upsert_grades(df_calificaciones)
                total_registros += n
                logs.append(f"  → {n} registros de calificaciones")

            # 6b. Calcular sede/centro de apoyo EIB por voto mayoritario de grupo
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando sedes EIB por grupo...")
            n_sedes = self._compute_eib_sedes()
            logs.append(f"  → {n_sedes} estudiantes EIB con sede asignada por grupo")

            # 7. Upsert calificaciones históricas (TableauHistorico P60–P67+)
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Leyendo calificaciones históricas (TableauHistorico)...")
            df_cal_historico = transform_calificaciones_historico(settings.DATA_PATH_CALIFICACIONES_HISTORICO)
            logs.append(f"  → {len(df_cal_historico)} registros históricos EIB ({df_cal_historico['periodo'].nunique() if not df_cal_historico.empty and 'periodo' in df_cal_historico.columns else 0} períodos)")
            if not df_cal_historico.empty:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando calificaciones históricas...")
                n = self._upsert_grades_historico(df_cal_historico)
                total_registros += n
                logs.append(f"  → {n} registros históricos cargados")

            # 7b. Segunda pasada de deduplicación (grades pueden crear orphans nuevos)
            n_merged2 = self._merge_duplicate_students()
            if n_merged2:
                logs.append(f"  → {n_merged2} estudiantes duplicados fusionados (post-grades)")

            # 7c. Backfill Grade.carrera desde Student.carrera donde sea NULL
            #     Esto asegura que el filtro estricto de malla canónica funcione
            #     correctamente (solo incluye grades con carrera explícita).
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Backfill Grade.carrera desde Student.carrera...")
            n_backfill = self.db.execute(
                sa_text("""
                    UPDATE grades
                    SET carrera = s.carrera
                    FROM students s
                    WHERE grades.student_id = s.id
                      AND (grades.carrera IS NULL OR grades.carrera = '')
                      AND s.carrera IS NOT NULL
                      AND s.carrera != ''
                """)
            ).rowcount
            self.db.commit()
            if n_backfill:
                logs.append(f"  → {n_backfill} calificaciones con carrera backfilled desde estudiante")

            # 7d. Invalidar caché de malla canónica (datos frescos)
            try:
                from ..routes.students import _canonical_cache
                _canonical_cache.clear()
                logs.append("  → Caché de malla canónica invalidado")
            except Exception:
                pass

            # 7e. Prácticas preprofesionales (si hay datos en ./data/Practicas)
            try:
                from .practicas import run_practicas_etl
                practicas_path = Path(settings.DATA_PATH_PRACTICAS)
                if practicas_path.exists() and any(practicas_path.glob("*.xlsx")):
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Procesando Prácticas Preprofesionales...")
                    pstats = run_practicas_etl(self.db, str(practicas_path))
                    sin_est = pstats["sin_estudiante"]
                    suffix = f", {sin_est} sin match de estudiante" if sin_est else ""
                    logs.append(
                        f"  → {pstats['escuelas_cargadas']} escuelas, "
                        f"{pstats['practicas_cargadas']} prácticas asignadas{suffix}"
                    )
                else:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sin datos de Prácticas Preprofesionales — omitiendo")
            except Exception as prac_err:
                logs.append(f"  ⚠️ Error en Prácticas Preprofesionales (no crítico): {prac_err}")
                logger.error("Error en ETL de prácticas: %s", prac_err, exc_info=True)

            # 8. Reentrenar modelos ML con datos históricos actualizados
            try:
                from ..ml.train import train_models
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Reentrenando modelos ML (por carrera)...")
                train_result = train_models(self.db)
                if train_result.get("status") == "ok":
                    carreras_modelo = len(train_result.get("carreras_con_modelo", []))
                    carreras_fallback = len(train_result.get("carreras_fallback", []))
                    logs.append(
                        f"  → Modelos entrenados: {carreras_modelo} por carrera, "
                        f"{carreras_fallback} usando global ({train_result.get('estudiantes', 0)} estudiantes)"
                    )
                else:
                    logs.append(f"  ⚠️ Entrenamiento ML: {train_result.get('message', 'sin resultado')}")
            except Exception as train_err:
                logs.append(f"  ⚠️ Error en entrenamiento ML (no crítico): {train_err}")

            # 9. Ejecutar predicciones ML con modelos recién entrenados
            try:
                from ..ml.predict import Predictor
                predictor = Predictor.get_instance()
                # Forzar recarga de modelos recién entrenados
                predictor._loaded = False
                if predictor.load_models():
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Ejecutando predicciones ML...")
                    ml_result = predictor.predict_batch(self.db)
                    if ml_result.get("status") == "ok":
                        por_carrera = ml_result.get("por_carrera", 0)
                        global_fb = ml_result.get("global_fallback", 0)
                        logs.append(
                            f"  → Predicciones actualizadas: {ml_result['updated']} estudiantes "
                            f"({por_carrera} por carrera, {global_fb} global)"
                        )
                    else:
                        logs.append(f"  ⚠️ ML: {ml_result.get('message', 'sin resultado')}")
                else:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sin modelo ML — omitiendo predicciones")
            except Exception as ml_err:
                logs.append(f"  ⚠️ Error en predicciones ML (no crítico): {ml_err}")

            run.status = "success"

        except Exception as e:
            logger.exception("Error en ETL pipeline")
            run.status = "error"
            errores.append({"error": str(e)})
            logs.append(f"ERROR CRÍTICO: {e}")

        finally:
            run.registros_insertados = total_registros
            run.errores = errores if errores else None
            run.log_output = "\n".join(logs)
            run.finished_at = datetime.now(timezone.utc)
            self.db.commit()

        return run

    # ─────────────────────────────────────────────────────────────────────────
    # UPSERTS
    # ─────────────────────────────────────────────────────────────────────────

    def _get_or_create_student(self, correo: str) -> Optional[Student]:
        """Busca estudiante por correo institucional."""
        return self.db.query(Student).filter(Student.correo_institucional == correo).first()

    def _seed_students_from_personales(self, df_personales: pd.DataFrame) -> int:
        """
        Crea registros Student mínimos para todos los estudiantes del reporte
        que aún no existen en la BD (p.ej. recién matriculados sin actividad AVAC).
        No sobreescribe datos si el estudiante ya existe.
        """
        if df_personales.empty:
            return 0

        count = 0
        for _, pr in df_personales.iterrows():
            ci = str(pr.get("correo_institucional", "")).strip()
            if not ci or "@" not in ci:
                continue

            student = self._get_or_create_student(ci)
            is_new = student is None
            if is_new:
                student = Student(correo_institucional=ci)
                self.db.add(student)

            # Solo poblar campos vacíos (no sobreescribir los ya calculados)
            cedula = _clean_str(pr.get("cedula"))
            if cedula and not student.cedula:
                student.cedula = cedula

            nombre = str(pr.get("nombre", "") or "").strip()
            if nombre and not student.nombre:
                student.nombre = nombre

            correo_p = str(pr.get("correo", "") or "").strip()
            if correo_p and "@" in correo_p and not student.correo:
                student.correo = correo_p

            tel = str(pr.get("telefono", "") or "").strip()
            if tel and not student.telefono:
                student.telefono = tel

            carrera = str(pr.get("carrera", "") or "").strip()
            if carrera and not student.carrera:
                student.carrera = carrera

            estado = str(pr.get("estado_matricula", "") or "").strip()
            if estado and not student.estado_matricula:
                student.estado_matricula = estado

            # ── Datos personales del reporte institucional ──────────────
            # Estos SIEMPRE se actualizan (no solo para nuevos) porque el
            # reporte es la fuente de verdad para datos demográficos,
            # nivel académico y grupo.

            # Nivel académico del reporte (moda de NIVEL por estudiante)
            # SIEMPRE actualizar — el reporte es fuente de verdad
            nivel_val = pr.get("nivel_academico")
            if nivel_val is not None and pd.notna(nivel_val):
                try:
                    niv = int(nivel_val)
                    if 1 <= niv <= 12:
                        student.nivel_academico = niv
                except (ValueError, TypeError):
                    pass

            # Grupo académico — SIEMPRE actualizar desde el reporte
            grupo_val = pr.get("grupo")
            if grupo_val is not None and pd.notna(grupo_val):
                grupo_str = str(grupo_val).strip()
                if grupo_str and grupo_str.lower() not in ("nan", "none", ""):
                    student.grupo = grupo_str

            fn = pr.get("fecha_nacimiento")
            if fn is not None and pd.notna(fn):
                try:
                    student.fecha_nacimiento = pd.Timestamp(fn).date()
                except Exception:
                    pass

            for col in ("genero", "autoidentificacion_etnica"):
                val = pr.get(col)
                if val is not None and pd.notna(val):
                    val_str = str(val).strip()
                    if val_str and val_str.lower() not in ("nan", "none", ""):
                        setattr(student, col, val_str)

            # ── Residencia (SIEMPRE actualizar desde reporte) ──────────────
            for campo in ("pais", "provincia", "ciudad", "barrio"):
                val = str(pr.get(campo, "") or "").strip()
                if val and val.lower() not in ("nan", "none", "", "s/n"):
                    setattr(student, campo, val)

            # ── WhatsApp (si no lo tenemos aún) ──────────────────────────
            wa = str(pr.get("whatsapp", "") or "").strip()
            if wa and wa.lower() not in ("nan", "none", "") and not student.whatsapp:
                student.whatsapp = wa

            if is_new:
                count += 1

        self.db.commit()
        return count

    def _find_student_by_name(self, nombre: str) -> Optional["Student"]:
        """
        Busca un estudiante por nombre con 3 niveles de fallback:
          1. Búsqueda exacta por nombre
          2. Búsqueda colapsando dobles espacios en la BD
          3. Búsqueda por nombre normalizado sin tildes (ACHIÑA → ACHINA)

        Si encuentra con nombre diferente, corrige el nombre en la BD al canónico.
        """
        if not nombre:
            return None

        # Nivel 1: búsqueda exacta
        student = self.db.query(Student).filter(Student.nombre == nombre).first()
        if student:
            return student

        # Nivel 2: colapsando dobles espacios
        student = (
            self.db.query(Student)
            .filter(func.replace(Student.nombre, "  ", " ") == nombre)
            .first()
        )
        if student:
            if student.nombre != nombre:
                student.nombre = nombre
            return student

        # Nivel 3: búsqueda sin tildes (ACHIÑA == ACHINA)
        nombre_sin_tildes = _normalize_name(nombre)
        all_candidates = self.db.query(Student).filter(Student.nombre.isnot(None)).all()
        for candidate in all_candidates:
            if _normalize_name(candidate.nombre) == nombre_sin_tildes:
                # Encontrado por tildes — preferir la versión sin tildes como canónica
                # (los sistemas institucionales generalmente usan ASCII)
                nombre_limpio = _normalize_name(nombre)
                if candidate.nombre != nombre_limpio:
                    logger.info(f"  Nombre corregido: '{candidate.nombre}' → '{nombre_limpio}' (tildes eliminadas)")
                    candidate.nombre = nombre_limpio
                return candidate

        return None

    def _merge_duplicate_students(self) -> int:
        """
        Detecta y fusiona estudiantes duplicados en DOS pasadas:

        PASADA 1 — Orphans sin correo:
        Busca estudiantes sin correo_institucional (orphans) y los fusiona con
        el estudiante "bueno" que SÍ tiene correo y el mismo nombre normalizado.

        PASADA 2 — Duplicados por tildes/diacríticos:
        Busca estudiantes con nombres que solo difieren por tildes o caracteres
        especiales. Ej: "ACHIÑA INUCA" vs "ACHINA INUCA" son la misma persona.
        Se queda con el que tiene más datos (correo, cédula) y fusiona el otro.

        En ambas pasadas se mueven grades, accesos AVAC, tareas, intervenciones
        y alertas del duplicado al registro principal antes de eliminarlo.
        """
        from ..models.grade import Grade
        from ..models.alert_event import AlertEvent
        from ..models import Intervention

        merged = 0

        # ── PASADA 1: Orphans sin correo ─────────────────────────────────────
        orphans = (
            self.db.query(Student)
            .filter(
                (Student.correo_institucional.is_(None)) | (Student.correo_institucional == "")
            )
            .all()
        )

        for orphan in orphans:
            if not orphan.nombre:
                continue

            nombre_norm = re.sub(r"\s+", " ", orphan.nombre.strip().upper())

            good = (
                self.db.query(Student)
                .filter(
                    Student.id != orphan.id,
                    Student.correo_institucional.isnot(None),
                    Student.correo_institucional != "",
                    func.replace(Student.nombre, "  ", " ") == nombre_norm,
                )
                .first()
            )
            if not good:
                continue

            merged += self._absorb_student(good, orphan)

        # ── PASADA 2: Duplicados por tildes/diacríticos ───────────────────────
        # Construir mapa nombre_normalizado_sin_tildes → [students]
        all_students = self.db.query(Student).filter(Student.nombre.isnot(None)).all()
        name_groups: dict[str, list] = {}
        for s in all_students:
            key = _normalize_name(s.nombre)
            if key:
                name_groups.setdefault(key, []).append(s)

        for key, group in name_groups.items():
            if len(group) < 2:
                continue

            # Elegir el "mejor" registro: prioridad a quien tiene correo + cédula + más datos
            group.sort(key=lambda s: (
                bool(s.correo_institucional),  # preferir con correo
                bool(s.cedula),                # preferir con cédula
                s.id,                          # preferir ID más bajo (creado antes)
            ), reverse=True)

            best = group[0]
            for dup in group[1:]:
                logger.info(f"  Duplicado por tildes: '{dup.nombre}' (id={dup.id}) → '{best.nombre}' (id={best.id})")
                merged += self._absorb_student(best, dup)

        if merged:
            self.db.flush()
            self.db.commit()

        return merged

    def _absorb_student(self, good: "Student", orphan: "Student") -> int:
        """
        Fusiona un estudiante duplicado (orphan) en el registro principal (good).
        Mueve todos los datos relacionados y elimina el duplicado.
        Retorna 1 si se fusionó, 0 si no.
        """
        from ..models.grade import Grade
        from ..models.alert_event import AlertEvent
        from ..models import Intervention

        # Mover calificaciones
        self.db.query(Grade).filter(Grade.student_id == orphan.id).update(
            {Grade.student_id: good.id}, synchronize_session=False
        )
        # Mover accesos AVAC
        self.db.query(AvacAccess).filter(AvacAccess.student_id == orphan.id).update(
            {AvacAccess.student_id: good.id}, synchronize_session=False
        )
        # Mover tareas
        self.db.query(TaskSubmission).filter(TaskSubmission.student_id == orphan.id).update(
            {TaskSubmission.student_id: good.id}, synchronize_session=False
        )
        # Mover intervenciones
        self.db.query(Intervention).filter(Intervention.student_id == orphan.id).update(
            {Intervention.student_id: good.id}, synchronize_session=False
        )
        # Mover alertas
        self.db.query(AlertEvent).filter(AlertEvent.student_id == orphan.id).update(
            {AlertEvent.student_id: good.id}, synchronize_session=False
        )

        # Copiar datos del orphan que el good no tiene
        if not good.carrera and orphan.carrera:
            good.carrera = orphan.carrera
        if not good.cedula and orphan.cedula:
            good.cedula = orphan.cedula
        if not good.correo_institucional and orphan.correo_institucional:
            good.correo_institucional = orphan.correo_institucional
        if not good.telefono and orphan.telefono:
            good.telefono = orphan.telefono

        logger.info(f"  Fusionado: '{orphan.nombre}' (id={orphan.id}) → '{good.nombre}' (id={good.id})")

        # Eliminar el duplicado
        self.db.delete(orphan)
        self.db.flush()
        return 1

        return merged

    def _upsert_students(
        self,
        df_ingresos: pd.DataFrame,
        df_calificaciones: pd.DataFrame,
        df_master: pd.DataFrame,
        df_personales: Optional[pd.DataFrame] = None,
        df_datos_especificos: Optional[pd.DataFrame] = None,
    ) -> int:
        """
        Crea o actualiza registros de Student con indicadores calculados.

        Prioridad de datos personales:
          1. df_personales (reporte.xlsx) — cedula, telefono, estado matrícula, residencia básica
          2. df_datos_especificos (DatosEspecificos EIB) — nivel académico, sede, whatsapp,
             residencia granular (cantón, parroquia), nombre (apellidos + nombres)
          3. df_ingresos (AVAC) — nombre y correo institucional
          4. df_calificaciones (Tableau) — carrera como fallback

        Campos residencia:
          reporte.xlsx aporta: pais, provincia, ciudad (CIUDAD_DOM), barrio (BARRIO)
          DatosEspecificos aporta: pais, provincia, ciudad (Cantón), parroquia, barrio
          Si ambos tienen datos, reporte gana en pais/provincia/barrio y
          DatosEspecificos gana en ciudad (Cantón es más granular que CIUDAD_DOM)
          y agrega parroquia que el reporte no tiene.
        """
        import math

        def _nan_to_none(val):
            """Convierte NaN/inf de pandas a None para inserción segura en BD."""
            if val is None:
                return None
            try:
                return None if math.isnan(float(val)) or math.isinf(float(val)) else val
            except (TypeError, ValueError):
                return val

        # ── Construir mapa correo → datos personales (reporte.xlsx) ────────────
        personales_map: dict = {}
        if df_personales is not None and not df_personales.empty:
            for _, pr in df_personales.iterrows():
                ci = str(pr.get("correo_institucional", "")).strip()
                if ci and "@" in ci:
                    personales_map[ci] = pr

        # ── Construir mapa correo → DatosEspecificos EIB ─────────────────────
        datos_esp_map: dict = {}
        if df_datos_especificos is not None and not df_datos_especificos.empty:
            for _, de in df_datos_especificos.iterrows():
                ci = str(de.get("correo_institucional", "")).strip()
                if ci and "@" in ci:
                    datos_esp_map[ci] = de

        # ── Construir mapa nombre → calificaciones (fallback de carrera) ────────
        cal_map: dict = {}
        if not df_calificaciones.empty and "nombre_estudiante" in df_calificaciones.columns:
            for _, row in df_calificaciones.iterrows():
                nombre = str(row.get("nombre_estudiante", "")).strip().upper()
                cal_map[nombre] = row

        count = 0
        for _, row in df_master.iterrows():
            correo = str(row.get("correo", "")).strip()
            if not correo or "@" not in correo:
                continue

            student = self._get_or_create_student(correo)
            if not student:
                student = Student(correo_institucional=correo)
                self.db.add(student)

            # ── Datos personales desde reporte.xlsx (prioridad 1) ───────────────
            pr = personales_map.get(correo)
            if pr is not None:
                # Cedula: solo sobreescribir si aún no está en BD
                cedula = _clean_str(pr.get("cedula"))
                if cedula and not student.cedula:
                    student.cedula = cedula

                # Nombre: preferir reporte > AVAC
                nombre_rep = str(pr.get("nombre", "") or "").strip()
                if nombre_rep:
                    student.nombre = nombre_rep

                # Correo personal
                correo_personal = str(pr.get("correo", "") or "").strip()
                if correo_personal and "@" in correo_personal:
                    student.correo = correo_personal

                # Teléfono
                telefono = str(pr.get("telefono", "") or "").strip()
                if telefono:
                    student.telefono = telefono

                # WhatsApp (si el reporte lo incluye)
                wa = str(pr.get("whatsapp", "") or "").strip()
                if wa and not student.whatsapp:
                    student.whatsapp = wa

                # Carrera desde reporte (más fiable que AVAC)
                carrera_rep = str(pr.get("carrera", "") or "").strip()
                if carrera_rep:
                    student.carrera = carrera_rep

                # Estado matrícula
                estado = str(pr.get("estado_matricula", "") or "").strip()
                if estado:
                    student.estado_matricula = estado

                # Residencia desde reporte (pais, provincia, ciudad, barrio)
                for campo in ("pais", "provincia", "ciudad", "barrio"):
                    val = str(pr.get(campo, "") or "").strip()
                    if val and val.lower() not in ("nan", "none", ""):
                        setattr(student, campo, val)

                # ── Datos demográficos del reporte 2505060014 (Paso 4) ──────
                # fecha_nacimiento (ya es datetime/NaT desde transform_personales)
                fn = pr.get("fecha_nacimiento")
                if fn is not None and pd.notna(fn):
                    try:
                        student.fecha_nacimiento = pd.Timestamp(fn).date()
                    except Exception:
                        pass

                # genero, autoidentificacion_etnica (strings)
                for col in ("genero", "autoidentificacion_etnica"):
                    val = _nan_to_none(pr.get(col))
                    if val is not None:
                        val_str = str(val).strip()
                        if val_str and val_str.lower() not in ("nan", "none", ""):
                            setattr(student, col, val_str)

                # grupo académico (del reporte, "3" etc.)
                grupo_val = _nan_to_none(pr.get("grupo"))
                if grupo_val is not None:
                    grupo_str = str(grupo_val).strip()
                    if grupo_str and grupo_str.lower() not in ("nan", "none", ""):
                        student.grupo = grupo_str

                # Nivel académico (moda de NIVEL del reporte) — prioridad 1
                nivel_rep = _nan_to_none(pr.get("nivel_academico"))
                if nivel_rep is not None:
                    try:
                        niv = int(nivel_rep)
                        if 1 <= niv <= 12:
                            student.nivel_academico = niv
                    except (ValueError, TypeError):
                        pass

            else:
                # ── Fallback: nombre desde AVAC (prioridad 2) ───────────────────
                nombre_avac = str(row.get("nombre_avac", "")).strip()
                if nombre_avac and not student.nombre:
                    student.nombre = nombre_avac

                # Carrera desde calificaciones (prioridad 3)
                if nombre_avac in cal_map:
                    cal_row = cal_map[nombre_avac]
                    student.carrera = student.carrera or str(cal_row.get("carrera", "")).strip() or None

            # ── DatosEspecificos EIB (nivel académico, sede, whatsapp, residencia granular) ──
            de = datos_esp_map.get(correo)
            if de is not None:
                # Nivel académico (entero 1–8) — DatosEspecificos como fallback
                # (reporte.xlsx ya lo estableció arriba si existía)
                if not student.nivel_academico:
                    nivel = de.get("nivel_academico")
                    if nivel is not None and not (isinstance(nivel, float) and pd.isna(nivel)):
                        try:
                            student.nivel_academico = int(nivel)
                        except (ValueError, TypeError):
                            pass

                # Sede / Centro de apoyo (más directo que majority-vote por grupo)
                sede_de = str(de.get("sede", "") or "").strip()
                if sede_de and sede_de.lower() not in ("nan", "none", ""):
                    student.sede = sede_de

                # WhatsApp (si no lo tenemos ya del reporte)
                wa_de = str(de.get("whatsapp", "") or "").strip()
                if wa_de and not student.whatsapp:
                    student.whatsapp = wa_de

                # Nombre (Apellidos + Nombres del formulario) — solo si no vino del reporte
                nombre_de = str(de.get("nombre", "") or "").strip()
                if nombre_de and not student.nombre:
                    student.nombre = nombre_de

                # Cédula (si no vino del reporte)
                cedula_de = _clean_str(de.get("cedula"))
                if cedula_de and not student.cedula:
                    student.cedula = cedula_de

                # Residencia granular: parroquia (solo en DatosEspecificos)
                parroquia = str(de.get("parroquia", "") or "").strip()
                if parroquia and parroquia.lower() not in ("nan", "none", ""):
                    student.parroquia = parroquia

                # Cantón como ciudad — solo si el reporte no lo tiene
                ciudad_de = str(de.get("ciudad", "") or "").strip()
                if ciudad_de and ciudad_de.lower() not in ("nan", "none", "") and not student.ciudad:
                    student.ciudad = ciudad_de

                # Barrio — solo si el reporte no lo tiene
                barrio_de = str(de.get("barrio", "") or "").strip()
                if barrio_de and barrio_de.lower() not in ("nan", "none", "") and not student.barrio:
                    student.barrio = barrio_de

                # País y Provincia — solo si el reporte no los tiene
                for campo in ("pais", "provincia"):
                    val_de = str(de.get(campo, "") or "").strip()
                    if val_de and val_de.lower() not in ("nan", "none", ""):
                        if not getattr(student, campo):
                            setattr(student, campo, val_de)

            # ── Indicadores de riesgo (siempre desde df_master) ────────────────
            dias = _nan_to_none(row.get("dias_sin_acceso_max"))
            student.dias_sin_acceso = int(dias) if dias is not None else None
            student.indice_compromiso = _nan_to_none(row.get("indice_compromiso"))
            student.nivel_riesgo = row.get("nivel_riesgo")
            student.porcentaje_tareas = _nan_to_none(row.get("porcentaje_tareas"))

            # Promedio de calificaciones (del transformer, escala 0-100)
            promedio_cal = _nan_to_none(row.get("promedio_notas"))
            if promedio_cal is not None:
                student.promedio_calificaciones = round(float(promedio_cal), 2)

            count += 1

        self.db.commit()
        return count

    # Mapeo importado desde backend.constants (fuente única)

    def _compute_eib_sedes(self) -> int:
        """Asigna sede a estudiantes EIB por voto mayoritario del grupo en calificaciones.

        Lógica idéntica al Excel original:
        Si >50% de las materias del estudiante pertenecen a un grupo (1-6),
        se asigna el centro de apoyo correspondiente.
        Solo aplica para la carrera de Educación Intercultural Bilingüe.
        """
        from ..models.grade import Grade as _Grade
        from collections import Counter

        # Estudiantes EIB con calificaciones del semestre actual
        eib_grades = (
            self.db.query(_Grade.student_id, _Grade.grupo)
            .filter(
                _Grade.periodo.is_(None),
                _Grade.grupo.isnot(None),
                func.lower(_Grade.carrera).contains("intercultural"),
            )
            .all()
        )
        if not eib_grades:
            return 0

        # Agrupar grupos por estudiante
        student_grupos: dict[int, list[int]] = {}
        for sid, grupo_str in eib_grades:
            m = re.search(r"(\d+)", str(grupo_str))
            if m:
                student_grupos.setdefault(sid, []).append(int(m.group(1)))

        # Voto mayoritario (>50%)
        count = 0
        sids = list(student_grupos.keys())
        students = self.db.query(Student).filter(Student.id.in_(sids)).all()
        student_map = {s.id: s for s in students}

        for sid, grupos in student_grupos.items():
            student = student_map.get(sid)
            if not student:
                continue
            counter = Counter(grupos)
            most_common_grupo, freq = counter.most_common(1)[0]
            if freq / len(grupos) > 0.5 and most_common_grupo in EIB_GRUPO_SEDE:
                student.sede = EIB_GRUPO_SEDE[most_common_grupo]
                count += 1
            else:
                # Grupos 7+ o sin mayoría clara
                if not student.sede:
                    student.sede = None

        self.db.commit()
        return count

    def _upsert_avac_accesses(self, df_ingresos: pd.DataFrame, periodo: Optional[str] = None) -> int:
        """Carga accesos AVAC preservando snapshots históricos.

        Solo borra registros del MISMO DÍA (evita duplicados si se corre 2 veces),
        pero conserva snapshots de días anteriores para análisis de tendencias.
        """
        if df_ingresos.empty:
            return 0

        from datetime import date as date_type
        today = date_type.today()
        count = 0

        # Solo borrar snapshot de hoy (para evitar duplicados), preservar días anteriores
        del_filter = AvacAccess.snapshot_date == today
        if periodo:
            del_filter = del_filter & (AvacAccess.periodo == periodo)
        deleted = self.db.query(AvacAccess).filter(del_filter).delete(synchronize_session=False)
        if deleted:
            logger.info(f"  Snapshot AVAC {today}: eliminados {deleted} registros del mismo día")

        for _, row in df_ingresos.iterrows():
            correo = str(row.get("correo", "")).strip()
            student = self._get_or_create_student(correo)
            if not student:
                continue

            acceso = AvacAccess(
                student_id=student.id,
                codigo_curso=str(row.get("codigo_curso", "")).strip(),
                periodo=periodo,
                snapshot_date=today,
                nombre_estudiante_avac=row.get("nombre_avac"),
                ultimo_acceso_texto=row.get("ultimo_acceso_texto"),
                dias_sin_acceso=row.get("dias_sin_acceso"),
                estado_avac=row.get("estado_avac"),
                fecha_extraccion=row.get("fecha_extraccion"),
            )
            self.db.add(acceso)
            count += 1

        self.db.commit()
        return count

    def _upsert_task_submissions(self, df_tareas: pd.DataFrame, periodo: Optional[str] = None) -> int:
        """Carga submissions de tareas preservando snapshots históricos.

        Solo borra registros del MISMO DÍA (evita duplicados), preserva días
        anteriores para análisis de tendencias y seguimiento docente.
        """
        if df_tareas.empty:
            return 0

        from datetime import date as date_type
        today = date_type.today()
        count = 0

        # Solo borrar snapshot de hoy, preservar días anteriores
        del_filter = TaskSubmission.snapshot_date == today
        if periodo:
            del_filter = del_filter & (TaskSubmission.periodo == periodo)
        deleted = self.db.query(TaskSubmission).filter(del_filter).delete(synchronize_session=False)
        if deleted:
            logger.info(f"  Snapshot tareas {today}: eliminados {deleted} registros del mismo día")

        for _, row in df_tareas.iterrows():
            correo = str(row.get("correo", "")).strip()
            student = self._get_or_create_student(correo)
            if not student:
                continue

            sub = TaskSubmission(
                student_id=student.id,
                codigo_curso=str(row.get("codigo_curso", "")).strip(),
                unidad=str(row.get("unidad", "")).strip(),
                periodo=periodo,
                snapshot_date=today,
            )
            sub.estado = row.get("estado")
            sub.calificacion = row.get("calificacion")
            sub.calificacion_maxima = row.get("calificacion_maxima")
            sub.calificacion_final = row.get("calificacion_final")
            sub.entregada = bool(row.get("entregada", False))
            sub.calificada = bool(row.get("calificada", False))
            sub.retrasada = bool(row.get("retrasada", False))
            sub.archivos_enviados = row.get("archivos_enviados")
            sub.comentarios_retroalimentacion = row.get("comentarios_retroalimentacion")
            sub.total_curso = row.get("total_curso")
            sub.fecha_extraccion = row.get("fecha_extraccion")
            self.db.add(sub)
            count += 1

        self.db.commit()
        return count

    def _upsert_grades(self, df_calificaciones: pd.DataFrame) -> int:
        """Carga calificaciones institucionales del semestre actual.

        Estrategia full-refresh: elimina registros del periodo activo (o NULL)
        antes de recargar, evitando duplicados acumulativos.
        Ahora etiqueta los grades con el periodo activo para que las queries
        por periodo los encuentren correctamente.
        """
        if df_calificaciones.empty or "nombre_estudiante" not in df_calificaciones.columns:
            return 0

        from ..models.grade import Grade as _Grade
        from sqlalchemy import or_

        # Determinar periodo: si es fallback del histórico, usar el periodo
        # original del archivo (ej. P67) en vez del activo (ej. P68)
        fallback_p = getattr(self, "_fallback_periodo", None)
        if fallback_p:
            active_periodo = fallback_p
            logger.info(f"  _upsert_grades: usando periodo fallback '{fallback_p}' (archivo histórico como semestre activo)")
        else:
            active_sem = self._get_active_semester()
            active_periodo = active_sem.semestre.strip() if active_sem and active_sem.semestre else None

        # Full-refresh: eliminar calificaciones del periodo antes de recargar
        # Cuando es fallback, NO borrar periodo=NULL (esos son legacy, no del archivo)
        if active_periodo:
            if fallback_p:
                # Fallback: solo borrar el periodo específico (P67 / 67)
                if active_periodo.startswith("P"):
                    del_filter = or_(
                        _Grade.periodo == active_periodo,
                        _Grade.periodo == active_periodo[1:],
                    )
                else:
                    del_filter = or_(
                        _Grade.periodo == active_periodo,
                        _Grade.periodo == f"P{active_periodo}",
                    )
            else:
                # Normal: borrar periodo activo + NULL (migración gradual)
                if active_periodo.startswith("P"):
                    del_filter = or_(
                        _Grade.periodo.is_(None),
                        _Grade.periodo == active_periodo,
                        _Grade.periodo == active_periodo[1:],
                    )
                else:
                    del_filter = or_(
                        _Grade.periodo.is_(None),
                        _Grade.periodo == active_periodo,
                        _Grade.periodo == f"P{active_periodo}",
                    )
        else:
            del_filter = _Grade.periodo.is_(None)

        deleted = (
            self.db.query(_Grade)
            .filter(del_filter)
            .delete(synchronize_session=False)
        )
        if deleted:
            logger.info(f"  Grades periodo {active_periodo or 'NULL'}: eliminados {deleted} registros previos (full-refresh)")
        self.db.flush()

        count = 0
        for _, row in df_calificaciones.iterrows():
            nombre = re.sub(r"\s+", " ", str(row.get("nombre_estudiante", "")).strip().upper())
            if not nombre:
                continue

            student = self._find_student_by_name(nombre)
            if not student:
                student = Student(
                    nombre=nombre,
                    carrera=str(row.get("carrera", "")).strip() or None,
                )
                self.db.add(student)
                self.db.flush()

            if not student.carrera and row.get("carrera"):
                student.carrera = str(row.get("carrera", "")).strip()

            from ..models.grade import Grade
            # numero_repitencias: puede venir como Int64 (nullable int) de pandas
            _repitencias = row.get("numero_repitencias")
            repitencias_val = int(_repitencias) if _repitencias is not None and not (hasattr(_repitencias, '__class__') and str(_repitencias) == '<NA>') else None

            # nivel: nivel académico de la asignatura (Int64 nullable)
            _nivel = row.get("nivel")
            nivel_val = int(_nivel) if _nivel is not None and not (hasattr(_nivel, '__class__') and str(_nivel) == '<NA>') else None

            grade = Grade(
                student_id=student.id,
                asignatura=str(row.get("asignatura", "")).strip(),
                carrera=str(row.get("carrera", "")).strip() or None,
                grupo=str(row.get("grupo", "")).strip() or None,
                docente=str(row.get("docente", "")).strip() or None,
                nota_final=row.get("nota_final"),
                sede=str(row.get("sede", "")).strip() or None,
                numero_repitencias=repitencias_val,
                nivel=nivel_val,
                periodo=active_periodo,  # etiquetar con periodo activo (ej. "P68")
            )
            self.db.add(grade)
            count += 1

        self.db.commit()
        return count

    def _upsert_grades_historico(self, df_historico: pd.DataFrame) -> int:
        """
        Carga calificaciones históricas por período (P60–P67+) desde TableauHistorico.

        Estrategia: por cada período en el DataFrame, elimina los registros existentes
        de ese período y los recarga (full-refresh por período).

        Join a estudiante por nombre (APELLIDOS NOMBRES, mayúsculas).
        Escala de Nota Final: 0–100 (diferente a AVAC que usa 0–40).
        """
        from ..models.grade import Grade

        if df_historico.empty or "nombre_estudiante" not in df_historico.columns:
            return 0

        # Si el fallback del pipeline ya cargó un período como semestre actual,
        # excluirlo del histórico para evitar duplicados
        fallback_periodo = getattr(self, "_fallback_periodo", None)
        if fallback_periodo and fallback_periodo in df_historico["periodo"].values:
            logger.info(f"  Excluyendo {fallback_periodo} del histórico (ya cargado como semestre actual)")
            df_historico = df_historico[df_historico["periodo"] != fallback_periodo].copy()
            if df_historico.empty:
                return 0

        # Períodos presentes en el DataFrame
        periodos_presentes = df_historico["periodo"].unique().tolist()

        # Full-refresh por período: eliminar calificaciones existentes de estos períodos
        deleted = (
            self.db.query(Grade)
            .filter(Grade.periodo.in_(periodos_presentes))
            .delete(synchronize_session=False)
        )
        if deleted:
            logger.info(f"  Eliminados {deleted} registros históricos de {periodos_presentes}")
        self.db.flush()

        count = 0
        for _, row in df_historico.iterrows():
            nombre = re.sub(r"\s+", " ", str(row.get("nombre_estudiante", "")).strip().upper())
            if not nombre:
                continue

            periodo = str(row.get("periodo", "")).strip() or None

            student = self._find_student_by_name(nombre)
            if not student:
                student = Student(
                    nombre=nombre,
                    carrera=str(row.get("carrera", "")).strip() or None,
                )
                self.db.add(student)
                self.db.flush()

            if not student.carrera and row.get("carrera"):
                student.carrera = str(row.get("carrera", "")).strip()

            grade = Grade(
                student_id=student.id,
                asignatura=str(row.get("asignatura", "")).strip(),
                carrera=str(row.get("carrera", "")).strip() or None,
                grupo=str(row.get("grupo", "")).strip() or None,
                docente=str(row.get("docente", "")).strip() or None,
                nota_final=row.get("nota_final"),
                sede=str(row.get("sede", "")).strip() or None,
                periodo=periodo,
            )
            self.db.add(grade)
            count += 1

            # Commit en lotes para evitar transacciones enormes
            if count % 500 == 0:
                self.db.flush()

        self.db.commit()
        return count

    # ─────────────────────────────────────────────────────────────────────────
    # CourseConfig auto-population from reporte.xlsx
    # ─────────────────────────────────────────────────────────────────────────

    def _sync_course_configs(self, df_courses: pd.DataFrame, semestre: Optional[str] = None) -> int:
        """
        Sincroniza course_configs con los cursos extraídos del reporte.
        - Crea nuevos registros para códigos AVAC que no existen
        - Actualiza datos (nombre, docente, nivel, grupo) de los existentes
        - NO elimina cursos que ya no aparecen (pueden ser de bloques anteriores)
        """
        if df_courses.empty:
            return 0

        count_new = 0
        count_updated = 0
        for _, row in df_courses.iterrows():
            codigo = str(row.get("codigo_avac", "")).strip()
            if not codigo:
                continue

            existing = self.db.query(CourseConfig).filter(
                CourseConfig.codigo_avac == codigo,
            ).first()

            if existing:
                # Actualizar datos si hay nueva info
                if row.get("nombre_asignatura") and pd.notna(row["nombre_asignatura"]):
                    existing.asignatura = str(row["nombre_asignatura"]).strip()
                if row.get("carrera") and pd.notna(row["carrera"]):
                    existing.carrera = str(row["carrera"]).strip()
                if row.get("docente") and pd.notna(row["docente"]):
                    existing.docente = str(row["docente"]).strip()
                if row.get("correo_docente") and pd.notna(row["correo_docente"]):
                    existing.correo_docente = str(row["correo_docente"]).strip()
                if row.get("nivel") and pd.notna(row["nivel"]):
                    try:
                        existing.nivel = int(row["nivel"])
                    except (ValueError, TypeError):
                        pass
                if row.get("grupo") and pd.notna(row["grupo"]):
                    existing.grupo = str(row["grupo"]).strip()
                if semestre:
                    existing.semestre = semestre
                count_updated += 1
            else:
                correo_doc = str(row.get("correo_docente", "")).strip() or None
                cc = CourseConfig(
                    codigo_avac=codigo,
                    asignatura=str(row.get("nombre_asignatura", "")).strip() or None,
                    carrera=str(row.get("carrera", "")).strip() or None,
                    docente=str(row.get("docente", "")).strip() or None,
                    correo_docente=correo_doc,
                    semestre=semestre,
                    activo=True,
                )
                if row.get("nivel") and pd.notna(row["nivel"]):
                    try:
                        cc.nivel = int(row["nivel"])
                    except (ValueError, TypeError):
                        pass
                if row.get("grupo") and pd.notna(row["grupo"]):
                    cc.grupo = str(row["grupo"]).strip()
                self.db.add(cc)
                count_new += 1

            if (count_new + count_updated) % 100 == 0:
                self.db.flush()

        self.db.commit()
        logger.info(f"_sync_course_configs: {count_new} nuevos, {count_updated} actualizados")
        return count_new + count_updated

    # ─────────────────────────────────────────────────────────────────────────
    # Resumen_General — seguimiento de calificación docente
    # ─────────────────────────────────────────────────────────────────────────

    def _upsert_resumen_general(self, df_resumen: pd.DataFrame) -> int:
        """
        Carga datos de Resumen_General en docente_tracking.
        Full-refresh: borra registros anteriores del mismo semestre y recarga.
        """
        if df_resumen.empty:
            return 0

        semconfig = self._get_active_semester()
        semestre = semconfig.semestre if semconfig else None

        # Full-refresh del semestre actual
        if semestre:
            self.db.query(DocenteTracking).filter(
                DocenteTracking.semestre == semestre
            ).delete()
            self.db.flush()

        count = 0
        for _, row in df_resumen.iterrows():
            codigo = str(row.get("codigo_curso", row.get("codigo", ""))).strip()
            nombre = str(row.get("nombre_curso", row.get("curso", ""))).strip()
            actividad = str(row.get("actividad", row.get("nombre_actividad", ""))).strip()
            tipo = str(row.get("tipo_actividad", row.get("tipo", ""))).strip()

            cal_raw = row.get("calificada", row.get("estado", None))
            calificada = None
            if cal_raw is not None and pd.notna(cal_raw):
                cal_str = str(cal_raw).strip().lower()
                if cal_str in ("sí", "si", "yes", "true", "1"):
                    calificada = True
                elif cal_str in ("no", "false", "0"):
                    calificada = False

            docente = str(row.get("docente", row.get("profesor", ""))).strip()
            if docente.lower() in ("nan", "none", ""):
                docente = None

            fecha_limite = pd.to_datetime(
                row.get("fecha_limite", row.get("fecha_entrega")), errors="coerce"
            )
            fecha_cal = pd.to_datetime(row.get("fecha_calificacion"), errors="coerce")

            dias_retraso = None
            if pd.notna(fecha_limite) and pd.notna(fecha_cal):
                dias_retraso = (fecha_cal - fecha_limite).total_seconds() / 86400

            dt = DocenteTracking(
                codigo_curso=codigo or None,
                nombre_curso=nombre or None,
                actividad=actividad or None,
                tipo_actividad=tipo or None,
                calificada=calificada,
                fecha_limite=fecha_limite if pd.notna(fecha_limite) else None,
                fecha_calificacion=fecha_cal if pd.notna(fecha_cal) else None,
                docente=docente,
                dias_retraso=dias_retraso,
                semestre=semestre,
                fuente=str(row.get("_fuente", "")).strip() or None,
            )
            self.db.add(dt)
            count += 1

            if count % 500 == 0:
                self.db.flush()

        self.db.commit()
        logger.info(f"_upsert_resumen_general: {count} registros de seguimiento docente")
        return count

    # ─────────────────────────────────────────────────────────────────────────
    # Enrollments — asignaturas matriculadas desde reporte.xlsx
    # ─────────────────────────────────────────────────────────────────────────

    def _upsert_enrollments(self, df_enrollments: pd.DataFrame) -> int:
        """
        Carga asignaturas matriculadas desde el reporte.
        Full-refresh por periodo: borra enrollments del periodo actual y recarga.
        Cada fila = 1 estudiante × 1 asignatura matriculada.
        """
        if df_enrollments.empty:
            return 0

        # Determinar periodo del reporte (tomar el más frecuente)
        periodo_vals = df_enrollments["periodo"].dropna().unique()
        periodo = str(periodo_vals[0]) if len(periodo_vals) > 0 else None

        # Full-refresh del periodo actual
        if periodo:
            self.db.query(Enrollment).filter(
                Enrollment.periodo == periodo
            ).delete()
            self.db.flush()

        # Construir mapa correo → student_id
        student_map: dict[str, int] = {}
        students = self.db.query(Student.id, Student.correo_institucional).filter(
            Student.correo_institucional.isnot(None)
        ).all()
        for sid, ci in students:
            if ci:
                student_map[ci.strip().lower()] = sid

        count = 0
        for _, row in df_enrollments.iterrows():
            ci = str(row.get("correo_institucional", "")).strip().lower()
            student_id = student_map.get(ci)
            if not student_id:
                continue

            codigo_grupo = str(row.get("codigo_grupo", "")).strip()
            asignatura = str(row.get("asignatura", "")).strip()
            if not codigo_grupo or not asignatura:
                continue

            enrollment = Enrollment(
                student_id=student_id,
                codigo_grupo=codigo_grupo,
                codigo_asignatura=_clean_str(row.get("codigo_asignatura")),
                asignatura=asignatura,
                tipo_asignatura=_clean_str(row.get("tipo_asignatura")) or None,
                carrera=_clean_str(row.get("carrera")) or None,
                nivel=int(row["nivel"]) if pd.notna(row.get("nivel")) else None,
                nombre_grupo=_clean_str(row.get("nombre_grupo")) or None,
                bloque=int(row["bloque"]) if pd.notna(row.get("bloque")) else None,
                docente=_clean_str(row.get("docente")) or None,
                correo_docente=_clean_str(row.get("correo_docente")) or None,
                numero_repitencias=int(row["numero_repitencias"]) if pd.notna(row.get("numero_repitencias")) else None,
                pagado=_clean_str(row.get("pagado")) or None,
                estado_matriculado=_clean_str(row.get("estado_matriculado")) or None,
                periodo=periodo,
                fecha_matricula=row["fecha_matricula"] if pd.notna(row.get("fecha_matricula")) else None,
            )
            self.db.add(enrollment)
            count += 1

            if count % 500 == 0:
                self.db.flush()

        self.db.commit()
        logger.info(f"_upsert_enrollments: {count} asignaturas matriculadas cargadas (periodo={periodo})")
        return count
