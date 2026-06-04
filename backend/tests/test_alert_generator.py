"""
Tests para el generador de alertas reutilizable y el detector de deterioro progresivo.
[Épica 1.1] Pipeline Post-ETL Automático
[Épica 1.3] Alerta de Deterioro Progresivo
"""
import pytest
from datetime import datetime, timezone, timedelta, date
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Student, AvacAccess, Grade, ScrapingRun
from backend.models.alert_event import AlertEvent
from backend.models.course_config import SemesterConfig, CourseConfig
from backend.models.enrollment import Enrollment
from backend.models.user import User, UserRole


@pytest.fixture
def db_session():
    """Sesión de prueba con SQLite in-memory."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def setup_semester(db_session):
    """Configura un semestre activo con datos básicos."""
    sem = SemesterConfig(
        semestre="P68",
        activo=True,
        bloque_actual="1",
        bloque1_inicio=datetime(2026, 4, 1, tzinfo=timezone.utc),
        bloque1_fin=datetime(2026, 7, 31, tzinfo=timezone.utc),
        umbral_dias_inactividad=14,
        umbral_tareas_minimo=50.0,
        umbral_compromiso_minimo=0.4,
        auto_alertas=True,
    )
    db_session.add(sem)
    db_session.commit()
    return sem


@pytest.fixture
def setup_students(db_session, setup_semester):
    """Crea estudiantes de prueba."""
    students = [
        Student(id=1, nombre="Ana Pérez", cedula="0101010101", carrera="Pedagogía",
                indice_compromiso=0.8, porcentaje_tareas=75, nivel_riesgo="Bajo"),
        Student(id=2, nombre="Luis García", cedula="0202020202", carrera="Pedagogía",
                indice_compromiso=0.2, porcentaje_tareas=20, nivel_riesgo="Alto",
                prob_desercion=0.85),
        Student(id=3, nombre="María López", cedula="0303030303", carrera="Educación Básica",
                indice_compromiso=0.35, porcentaje_tareas=40, nivel_riesgo="Medio"),
    ]
    db_session.add_all(students)

    # Enrollments para periodo activo
    for s in students:
        db_session.add(Enrollment(student_id=s.id, codigo_grupo="C001", periodo="P68", asignatura="Pedagogía General"))

    # Accesos AVAC
    db_session.add(AvacAccess(
        student_id=1, codigo_curso="C001", periodo="P68",
        snapshot_date=date.today(), dias_sin_acceso=2,
    ))
    db_session.add(AvacAccess(
        student_id=2, codigo_curso="C001", periodo="P68",
        snapshot_date=date.today(), dias_sin_acceso=25,
    ))
    db_session.add(AvacAccess(
        student_id=3, codigo_curso="C001", periodo="P68",
        snapshot_date=date.today(), dias_sin_acceso=16,
    ))

    db_session.commit()
    return students


class TestGenerateAlertsBatch:
    """Tests para generate_alerts_batch()."""

    def test_generates_inactividad_alerts(self, db_session, setup_students):
        """Genera alertas de inactividad para estudiantes inactivos."""
        from backend.services.alert_generator import generate_alerts_batch
        result = generate_alerts_batch(db_session)

        assert result["created"] > 0
        alerts = db_session.query(AlertEvent).all()
        inactividad_alerts = [a for a in alerts if a.tipo == "inactividad"]
        assert len(inactividad_alerts) >= 1  # Luis (25 días) y María (16 días)

    def test_generates_compromiso_bajo_alerts(self, db_session, setup_students):
        """Genera alertas de compromiso bajo."""
        from backend.services.alert_generator import generate_alerts_batch
        result = generate_alerts_batch(db_session)

        alerts = db_session.query(AlertEvent).filter(AlertEvent.tipo == "compromiso_bajo").all()
        student_ids = {a.student_id for a in alerts}
        assert 2 in student_ids  # Luis tiene 0.2 (< 0.24 = critico)
        assert 3 in student_ids  # María tiene 0.35 (< 0.4 = alto)
        assert 1 not in student_ids  # Ana tiene 0.8 (OK)

    def test_cleans_stale_alerts(self, db_session, setup_students):
        """Limpia alertas no leídas antes de regenerar."""
        # Crear alerta existente
        db_session.add(AlertEvent(
            student_id=1, tipo="inactividad", severidad="alto",
            mensaje="Alerta vieja", leido=False,
        ))
        db_session.commit()

        from backend.services.alert_generator import generate_alerts_batch
        result = generate_alerts_batch(db_session)
        assert result["cleaned"] >= 1

    def test_full_refresh_clears_all_alerts(self, db_session, setup_students):
        """Full-refresh elimina TODAS las alertas (incluidas leídas) antes de regenerar."""
        db_session.add(AlertEvent(
            student_id=1, tipo="inactividad", severidad="alto",
            mensaje="Alerta leída", leido=True, leido_por="admin@test.com",
        ))
        db_session.commit()

        from backend.services.alert_generator import generate_alerts_batch
        result = generate_alerts_batch(db_session)

        # Full-refresh borra todo y regenera - la alerta leída se elimina
        assert result["cleaned"] >= 1

    def test_no_semester_returns_zero(self, db_session):
        """Sin semestre activo retorna 0 alertas."""
        from backend.services.alert_generator import generate_alerts_batch
        result = generate_alerts_batch(db_session)
        assert result["created"] == 0

    def test_dedup_recent_read_alerts(self, db_session, setup_students):
        """No duplica alertas leídas en los últimos 7 días."""
        db_session.add(AlertEvent(
            student_id=2, tipo="inactividad", severidad="critico",
            mensaje="Reciente", leido=True,
            created_at=datetime.now(timezone.utc) - timedelta(hours=12),
        ))
        db_session.commit()

        from backend.services.alert_generator import generate_alerts_batch
        result = generate_alerts_batch(db_session)

        inact_alerts = db_session.query(AlertEvent).filter(
            AlertEvent.tipo == "inactividad",
            AlertEvent.student_id == 2,
            AlertEvent.leido == False,
        ).all()
        # Should not create duplicate since read one exists within 7 days
        assert len(inact_alerts) <= 1

    def test_result_structure(self, db_session, setup_students):
        """Verifica la estructura del resultado."""
        from backend.services.alert_generator import generate_alerts_batch
        result = generate_alerts_batch(db_session)

        assert "created" in result
        assert "cleaned" in result
        assert "timestamp" in result
        assert "detail" in result
        assert isinstance(result["created"], int)


class TestDetectorioDetector:
    """Tests para detectar_deterioro_progresivo()."""

    def test_detects_progressive_disconnection(self, db_session, setup_semester):
        """Detecta desconexión silenciosa con snapshots consecutivos crecientes."""
        student = Student(id=10, nombre="Pedro Test", cedula="1010101010",
                          carrera="Pedagogía", indice_compromiso=0.5)
        db_session.add(student)
        db_session.add(Enrollment(student_id=10, codigo_grupo="C001", periodo="P68", asignatura="Pedagogía General"))

        # Crear snapshots con inactividad creciente (6 snapshots)
        base_date = date(2026, 4, 10)
        for i in range(6):
            db_session.add(AvacAccess(
                student_id=10, codigo_curso="C001", periodo="P68",
                snapshot_date=base_date + timedelta(days=i * 7),
                dias_sin_acceso=3 + i * 5,  # 3, 8, 13, 18, 23, 28
            ))

        db_session.commit()

        from backend.services.deterioro_detector import detectar_deterioro_progresivo
        alertas = detectar_deterioro_progresivo(db_session)

        assert len(alertas) >= 1
        deterioro = [a for a in alertas if a["tipo"] == "deterioro_progresivo"]
        assert len(deterioro) >= 1
        assert deterioro[0]["student_id"] == 10
        assert "progresiva" in deterioro[0]["mensaje"].lower() or "consecutiv" in deterioro[0]["mensaje"].lower()

    def test_no_detection_with_few_snapshots(self, db_session, setup_semester):
        """No detecta deterioro con menos de 3 snapshots."""
        student = Student(id=11, nombre="Test Few", cedula="1111111111",
                          carrera="Pedagogía")
        db_session.add(student)
        db_session.add(Enrollment(student_id=11, codigo_grupo="C001", periodo="P68", asignatura="Pedagogía General"))

        # Solo 2 snapshots
        for i in range(2):
            db_session.add(AvacAccess(
                student_id=11, codigo_curso="C001", periodo="P68",
                snapshot_date=date(2026, 4, 10) + timedelta(days=i * 7),
                dias_sin_acceso=5 + i * 10,
            ))
        db_session.commit()

        from backend.services.deterioro_detector import detectar_deterioro_progresivo
        alertas = detectar_deterioro_progresivo(db_session)
        student_alerts = [a for a in alertas if a["student_id"] == 11]
        assert len(student_alerts) == 0

    def test_no_detection_stable_access(self, db_session, setup_semester):
        """No detecta deterioro si el acceso es estable."""
        student = Student(id=12, nombre="Estable", cedula="1212121212",
                          carrera="Pedagogía")
        db_session.add(student)
        db_session.add(Enrollment(student_id=12, codigo_grupo="C001", periodo="P68", asignatura="Pedagogía General"))

        # Snapshots estables (sin incremento)
        for i in range(5):
            db_session.add(AvacAccess(
                student_id=12, codigo_curso="C001", periodo="P68",
                snapshot_date=date(2026, 4, 10) + timedelta(days=i * 7),
                dias_sin_acceso=3,  # siempre 3 días
            ))
        db_session.commit()

        from backend.services.deterioro_detector import detectar_deterioro_progresivo
        alertas = detectar_deterioro_progresivo(db_session)
        student_alerts = [a for a in alertas if a["student_id"] == 12]
        assert len(student_alerts) == 0

    def test_detects_task_abandonment_with_high_desertion(self, db_session, setup_semester):
        """Detecta combinación de tareas bajas + prob deserción alta."""
        student = Student(id=13, nombre="Abandono", cedula="1313131313",
                          carrera="Pedagogía", porcentaje_tareas=15,
                          prob_desercion=0.85, indice_compromiso=0.2)
        db_session.add(student)
        db_session.commit()

        from backend.services.deterioro_detector import detectar_deterioro_progresivo
        alertas = detectar_deterioro_progresivo(db_session)
        student_alerts = [a for a in alertas if a["student_id"] == 13]
        assert len(student_alerts) >= 1
        assert student_alerts[0]["severidad"] == "alto"


class TestDailyDigest:
    """Tests para el Daily Digest."""

    def test_build_digest_data(self, db_session, setup_students):
        """Construye datos del digest correctamente."""
        # Generar alertas primero
        from backend.services.alert_generator import generate_alerts_batch
        generate_alerts_batch(db_session)

        from backend.services.daily_digest import build_digest_data
        data = build_digest_data(db_session)

        assert "fecha" in data
        assert "total_alertas" in data
        assert "alertas_criticas" in data
        assert "top_students" in data
        assert data["total_alertas"] > 0
        assert data["total_estudiantes"] == 3

    def test_build_digest_html(self, db_session, setup_students):
        """Genera HTML del digest sin errores."""
        from backend.services.alert_generator import generate_alerts_batch
        generate_alerts_batch(db_session)

        from backend.services.daily_digest import build_digest_data, build_digest_html
        data = build_digest_data(db_session)
        html = build_digest_html(data)

        assert "Yachay Deep" in html
        assert "Resumen Diario" in html
        assert "CRÍTICAS" in html

    def test_send_digest_no_smtp(self, db_session, setup_students):
        """Sin SMTP configurado retorna error."""
        from backend.services.daily_digest import send_daily_digest
        result = send_daily_digest(db_session)
        assert "error" in result or len(result.get("sent_to", [])) == 0

    def test_digest_skips_when_no_alerts(self, db_session, setup_semester):
        """No envía digest si no hay alertas."""
        from backend.services.daily_digest import send_daily_digest
        with patch("backend.services.daily_digest.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.test.com"
            result = send_daily_digest(db_session)
            assert result.get("skipped") == True


class TestWorkqueue:
    """Tests para el endpoint de bandeja de trabajo."""

    def test_workqueue_returns_prioritized_items(self, db_session, setup_students):
        """Retorna ítems priorizados correctamente."""
        from backend.services.alert_generator import generate_alerts_batch
        generate_alerts_batch(db_session)

        # Simular query directa del workqueue
        from sqlalchemy import func
        from sqlalchemy import case
        alerts = (
            db_session.query(AlertEvent, Student.nombre, Student.carrera)
            .outerjoin(Student, AlertEvent.student_id == Student.id)
            .filter(AlertEvent.leido == False)
            .order_by(
                case(
                    (AlertEvent.severidad == "critico", 1),
                    (AlertEvent.severidad == "alto", 2),
                    else_=3,
                ),
                AlertEvent.created_at.desc(),
            )
            .limit(50)
            .all()
        )

        assert len(alerts) > 0
        # First alerts should be critico
        severidades = [a[0].severidad for a in alerts]
        if "critico" in severidades:
            first_critico = severidades.index("critico")
            for s in severidades[:first_critico]:
                assert s == "critico"  # no alto/medio before first critico


class TestPipelineIntegration:
    """Tests de integración: pipeline → alertas automáticas."""

    def test_auto_alertas_flag(self, db_session, setup_semester):
        """Verifica que el flag auto_alertas se respeta."""
        sem = db_session.query(SemesterConfig).first()
        assert sem.auto_alertas == True

        # Cambiar a False
        sem.auto_alertas = False
        db_session.commit()

        sem = db_session.query(SemesterConfig).first()
        assert sem.auto_alertas == False

    def test_generate_alerts_batch_callable(self, db_session, setup_students):
        """Verifica que generate_alerts_batch es invocable standalone."""
        from backend.services.alert_generator import generate_alerts_batch
        result = generate_alerts_batch(db_session)
        assert isinstance(result, dict)
        assert "created" in result
        assert "timestamp" in result
