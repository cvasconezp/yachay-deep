"""
Pipeline ETL principal — orquesta la carga completa a la base de datos.
Reemplaza la actualización manual de Power Query en el Excel.
Soporta filtrado por bloque activo usando SemesterConfig.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import pandas as pd
from sqlalchemy.orm import Session

from .transformers import (
    transform_ingresos_avac,
    transform_estado_tareas,
    transform_calificaciones,
    calcular_indicadores_estudiantes,
)
from ..models import Student, AvacAccess, TaskSubmission, Grade, ScrapingRun
from ..models.course_config import CourseConfig, SemesterConfig
from ..config import settings

logger = logging.getLogger(__name__)


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

            if semconfig:
                bloque_info = f"semestre={semconfig.semestre}, bloque={semconfig.bloque_actual}"
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Config activa: {bloque_info}")
                if codigos_activos:
                    logs.append(f"  → Filtrando por {len(codigos_activos)} cursos del bloque {semconfig.bloque_actual}")
                else:
                    logs.append("  ⚠️ Sin cursos configurados para este bloque — procesando todos los CSVs")
            else:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sin semestre activo — procesando todos los CSVs")

            # 1. Cargar y transformar fuentes
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

            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Leyendo Calificaciones...")
            df_calificaciones = transform_calificaciones(settings.DATA_PATH_CALIFICACIONES)
            logs.append(f"  → {len(df_calificaciones)} registros de calificaciones")

            # 2. Calcular indicadores
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando indicadores de riesgo...")
            df_master = calcular_indicadores_estudiantes(df_ingresos, df_tareas, df_calificaciones)

            # 3. Upsert estudiantes
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando estudiantes a BD...")
            n = self._upsert_students(df_ingresos, df_calificaciones, df_master)
            total_registros += n
            logs.append(f"  → {n} estudiantes actualizados")

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

            # 6. Upsert calificaciones
            if not df_calificaciones.empty:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando calificaciones...")
                n = self._upsert_grades(df_calificaciones)
                total_registros += n
                logs.append(f"  → {n} registros de calificaciones")

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
            run.finished_at = datetime.utcnow()
            self.db.commit()

        return run

    # ─────────────────────────────────────────────────────────────────────────
    # UPSERTS
    # ─────────────────────────────────────────────────────────────────────────

    def _get_or_create_student(self, correo: str) -> Optional[Student]:
        """Busca estudiante por correo institucional."""
        return self.db.query(Student).filter(Student.correo_institucional == correo).first()

    def _upsert_students(
        self,
        df_ingresos: pd.DataFrame,
        df_calificaciones: pd.DataFrame,
        df_master: pd.DataFrame,
    ) -> int:
        """Crea o actualiza registros de Student con indicadores calculados."""
        count = 0

        cal_map = {}
        if not df_calificaciones.empty and "nombre_estudiante" in df_calificaciones.columns:
            for _, row in df_calificaciones.iterrows():
                nombre = str(row.get("nombre_estudiante", "")).strip().upper()
                cal_map[nombre] = row

        for _, row in df_master.iterrows():
            correo = str(row.get("correo", "")).strip()
            if not correo or "@" not in correo:
                continue

            student = self._get_or_create_student(correo)
            if not student:
                student = Student(correo_institucional=correo)
                self.db.add(student)

            nombre_avac = str(row.get("nombre_avac", "")).strip()
            if nombre_avac and not student.nombre:
                student.nombre = nombre_avac

            student.dias_sin_acceso = row.get("dias_sin_acceso_max")
            student.indice_compromiso = row.get("indice_compromiso")
            student.nivel_riesgo = row.get("nivel_riesgo")
            student.porcentaje_tareas = row.get("porcentaje_tareas")

            if nombre_avac in cal_map:
                cal_row = cal_map[nombre_avac]
                student.carrera = student.carrera or str(cal_row.get("carrera", "")).strip()

            count += 1

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
        """Carga calificaciones institucionales."""
        if df_calificaciones.empty or "nombre_estudiante" not in df_calificaciones.columns:
            return 0

        count = 0
        for _, row in df_calificaciones.iterrows():
            nombre = str(row.get("nombre_estudiante", "")).strip().upper()
            if not nombre:
                continue

            student = self.db.query(Student).filter(Student.nombre == nombre).first()
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
            grade = Grade(
                student_id=student.id,
                asignatura=str(row.get("asignatura", "")).strip(),
                carrera=str(row.get("carrera", "")).strip() or None,
                grupo=str(row.get("grupo", "")).strip() or None,
                docente=str(row.get("docente", "")).strip() or None,
                nota_final=row.get("nota_final"),
                sede=str(row.get("sede", "")).strip() or None,
            )
            self.db.add(grade)
            count += 1

        self.db.commit()
        return count
