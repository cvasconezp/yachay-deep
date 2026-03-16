"""
Pipeline ETL principal — orquesta la carga completa a la base de datos.
Reemplaza la actualización manual de Power Query en el Excel.
Soporta filtrado por bloque activo usando SemesterConfig.
"""
import logging
import re
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
)
from ..models import Student, AvacAccess, TaskSubmission, Grade, ScrapingRun
from ..models.course_config import CourseConfig, SemesterConfig
from ..constants import EIB_GRUPO_SEDE
from ..config import settings

logger = logging.getLogger(__name__)


def _clean_str(val) -> str:
    """Convierte a string limpio; retorna '' si el valor es NaN/None/nan."""
    s = str(val or "").strip()
    return "" if s.lower() in ("nan", "none", "null") else s


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
        run = ScrapingRun(tipo="full", status="running", triggered_by=triggered_by)
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

            if semestre_vigente:
                # 2. Calcular indicadores
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando indicadores de riesgo...")
                df_master = calcular_indicadores_estudiantes(df_ingresos, df_tareas, df_calificaciones)

                # 3a. Crear registros base para todos los estudiantes del reporte
                #     (aunque aún no tengan actividad AVAC)
                # Limpiar cédulas 'nan' heredadas de corridas anteriores con el bug
                self.db.execute(sa_text("UPDATE students SET cedula = NULL WHERE cedula = 'nan'"))
                self.db.flush()

                if not df_personales.empty:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sembrando estudiantes desde reporte.xlsx...")
                    n_seed = self._seed_students_from_personales(df_personales)
                    logs.append(f"  → {n_seed} estudiantes inicializados desde reporte")

                # 3a-bis. Deduplicar estudiantes con mismo nombre (merge orphans)
                n_merged = self._merge_duplicate_students()
                if n_merged:
                    logs.append(f"  → {n_merged} estudiantes duplicados fusionados")

                # 3b. Upsert estudiantes con indicadores (actualiza los ya creados)
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Actualizando indicadores de estudiantes...")
                n = self._upsert_students(
                    df_ingresos, df_calificaciones, df_master,
                    df_personales, df_datos_especificos,
                )
                total_registros += n
                logs.append(f"  → {n} estudiantes con indicadores actualizados")

                # 4. Upsert accesos AVAC
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando accesos AVAC...")
                n = self._upsert_avac_accesses(df_ingresos)
                total_registros += n
                logs.append(f"  → {n} registros de acceso")

                # 5. Upsert tareas
                if not df_tareas.empty:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando submissions de tareas...")
                    n = self._upsert_task_submissions(df_tareas)
                    total_registros += n
                    logs.append(f"  → {n} submissions de tareas")

            else:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏸ Semestre finalizado — omitiendo cálculo de indicadores, accesos y tareas")
                df_master = pd.DataFrame()

            # 6. Upsert calificaciones (semestre actual, sin período)
            if semestre_vigente and not df_calificaciones.empty:
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

            # Nivel académico del reporte (moda de NIVEL por estudiante)
            nivel_val = pr.get("nivel_academico")
            if nivel_val is not None and pd.notna(nivel_val):
                try:
                    niv = int(nivel_val)
                    if 1 <= niv <= 12 and not student.nivel_academico:
                        student.nivel_academico = niv
                except (ValueError, TypeError):
                    pass

            # ── Datos personales del reporte institucional ──────────────
            # Estos SIEMPRE se actualizan (no solo para nuevos) porque el
            # reporte es la fuente de verdad para datos demográficos.
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

            grupo_val = pr.get("grupo")
            if grupo_val is not None and pd.notna(grupo_val):
                grupo_str = str(grupo_val).strip()
                if grupo_str and grupo_str.lower() not in ("nan", "none", ""):
                    student.grupo = grupo_str

            if is_new:
                count += 1

        self.db.commit()
        return count

    def _merge_duplicate_students(self) -> int:
        """
        Detecta y fusiona estudiantes duplicados creados por desajuste de nombres.

        Escenario típico: _seed_students_from_personales crea Student A con
        correo_institucional + datos personales. Luego _upsert_grades no lo
        encuentra (nombre con doble espacio) y crea Student B con solo
        nombre + carrera (sin correo_institucional).

        Estrategia: para cada Student sin correo_institucional, buscar otro
        con el mismo nombre normalizado que SÍ tenga correo. Si existe,
        mover grades/accesos/tareas del orphan al "bueno" y eliminar el orphan.
        """
        from ..models.grade import Grade

        # Buscar orphans: Students sin correo_institucional
        orphans = (
            self.db.query(Student)
            .filter(
                (Student.correo_institucional.is_(None)) | (Student.correo_institucional == "")
            )
            .all()
        )
        if not orphans:
            return 0

        merged = 0
        for orphan in orphans:
            if not orphan.nombre:
                continue

            # Normalizar nombre del orphan
            nombre_norm = re.sub(r"\s+", " ", orphan.nombre.strip().upper())

            # Buscar el "bueno" con correo_institucional y mismo nombre normalizado
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

            # Mover grades del orphan al good
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

            # Copiar datos del orphan que el good no tiene
            if not good.carrera and orphan.carrera:
                good.carrera = orphan.carrera

            # Eliminar el orphan
            self.db.delete(orphan)
            merged += 1
            logger.info(f"  Fusionado orphan '{orphan.nombre}' (id={orphan.id}) → '{good.nombre}' (id={good.id}, correo={good.correo_institucional})")

        if merged:
            self.db.flush()
            self.db.commit()

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

    def _upsert_avac_accesses(self, df_ingresos: pd.DataFrame) -> int:
        """Limpia y recarga los accesos AVAC (full refresh por período de extracción)."""
        if df_ingresos.empty:
            return 0

        count = 0
        fecha_max_extraccion = df_ingresos["fecha_extraccion"].max()

        self.db.query(AvacAccess).filter(
            AvacAccess.fecha_extraccion >= fecha_max_extraccion.replace(hour=0, minute=0, second=0)
            if pd.notna(fecha_max_extraccion) else True
        ).delete(synchronize_session=False)

        for _, row in df_ingresos.iterrows():
            correo = str(row.get("correo", "")).strip()
            student = self._get_or_create_student(correo)
            if not student:
                continue

            acceso = AvacAccess(
                student_id=student.id,
                codigo_curso=str(row.get("codigo_curso", "")).strip(),
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

    def _upsert_task_submissions(self, df_tareas: pd.DataFrame) -> int:
        """Carga submissions de tareas."""
        if df_tareas.empty:
            return 0

        count = 0
        for _, row in df_tareas.iterrows():
            correo = str(row.get("correo", "")).strip()
            student = self._get_or_create_student(correo)
            if not student:
                continue

            existing = self.db.query(TaskSubmission).filter(
                TaskSubmission.student_id == student.id,
                TaskSubmission.codigo_curso == str(row.get("codigo_curso", "")),
                TaskSubmission.unidad == str(row.get("unidad", "")),
            ).first()

            if existing:
                sub = existing
            else:
                sub = TaskSubmission(
                    student_id=student.id,
                    codigo_curso=str(row.get("codigo_curso", "")).strip(),
                    unidad=str(row.get("unidad", "")).strip(),
                )
                self.db.add(sub)

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
            count += 1

        self.db.commit()
        return count

    def _upsert_grades(self, df_calificaciones: pd.DataFrame) -> int:
        """Carga calificaciones institucionales del semestre actual (sin período).

        Estrategia full-refresh: elimina TODOS los registros con periodo=NULL
        antes de recargar, evitando duplicados acumulativos.
        """
        if df_calificaciones.empty or "nombre_estudiante" not in df_calificaciones.columns:
            return 0

        from ..models.grade import Grade as _Grade
        # Full-refresh: eliminar calificaciones del semestre actual antes de recargar
        deleted = (
            self.db.query(_Grade)
            .filter(_Grade.periodo.is_(None))
            .delete(synchronize_session=False)
        )
        if deleted:
            logger.info(f"  Grades semestre actual: eliminados {deleted} registros previos (full-refresh)")
        self.db.flush()

        count = 0
        for _, row in df_calificaciones.iterrows():
            nombre = re.sub(r"\s+", " ", str(row.get("nombre_estudiante", "")).strip().upper())
            if not nombre:
                continue

            # Buscar por nombre exacto (ya normalizado sin dobles espacios)
            student = self.db.query(Student).filter(Student.nombre == nombre).first()
            if not student:
                # Fallback: buscar colapsando espacios en BD (por si hay registros viejos)
                student = (
                    self.db.query(Student)
                    .filter(func.replace(Student.nombre, "  ", " ") == nombre)
                    .first()
                )
                if student and student.nombre != nombre:
                    # Corregir el nombre con doble espacio en BD
                    student.nombre = nombre
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
                periodo=None,  # sin período = semestre actual
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

            # Buscar estudiante por nombre (normalizado sin dobles espacios)
            student = self.db.query(Student).filter(Student.nombre == nombre).first()
            if not student:
                # Fallback: buscar colapsando espacios en BD
                student = (
                    self.db.query(Student)
                    .filter(func.replace(Student.nombre, "  ", " ") == nombre)
                    .first()
                )
                if student and student.nombre != nombre:
                    student.nombre = nombre
            if not student:
                # Crear estudiante mínimo si no existe (puede enriquecerse en runs posteriores)
                student = Student(
                    nombre=nombre,
                    carrera=str(row.get("carrera", "")).strip() or None,
                )
                self.db.add(student)
                self.db.flush()

            # Actualizar carrera si el estudiante no la tiene aún
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
