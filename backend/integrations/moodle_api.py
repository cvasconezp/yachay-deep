"""
Épica 5.3: Integración Moodle REST API

Conector para la API REST de Moodle como alternativa al scraping.
Funciones principales: obtener cursos, calificaciones, accesos, tareas.
Fallback automático a scraping si la API no responde.
"""
from __future__ import annotations

import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


class MoodleAPIClient:
    """Cliente para la API REST de Moodle (Web Services)."""

    def __init__(self, base_url: str, token: str, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.ws_url = f"{self.base_url}/webservice/rest/server.php"

    def _call(self, function: str, **params) -> dict:
        payload = {
            "wstoken": self.token,
            "wsfunction": function,
            "moodlewsrestformat": "json",
            **params,
        }
        try:
            resp = httpx.get(self.ws_url, params=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "exception" in data:
                raise MoodleAPIError(data.get("message", data.get("exception", "Unknown error")))
            return data
        except httpx.HTTPError as e:
            raise MoodleAPIError(f"HTTP error: {e}")

    def get_site_info(self) -> dict:
        return self._call("core_webservice_get_site_info")

    def get_courses(self) -> list[dict]:
        return self._call("core_course_get_courses")

    def get_enrolled_users(self, course_id: int) -> list[dict]:
        return self._call("core_enrol_get_enrolled_users", courseid=course_id)

    def get_grades(self, course_id: int, user_ids: list[int] = None) -> dict:
        params = {"courseid": course_id}
        if user_ids:
            for i, uid in enumerate(user_ids):
                params[f"userids[{i}]"] = uid
        return self._call("gradereport_user_get_grade_items", **params)

    def get_course_activities(self, course_id: int) -> list[dict]:
        data = self._call("core_course_get_contents", courseid=course_id)
        activities = []
        for section in data if isinstance(data, list) else []:
            for module in section.get("modules", []):
                activities.append({
                    "id": module.get("id"),
                    "name": module.get("name"),
                    "modname": module.get("modname"),
                    "url": module.get("url"),
                })
        return activities

    def get_assignments(self, course_ids: list[int]) -> list[dict]:
        params = {}
        for i, cid in enumerate(course_ids):
            params[f"courseids[{i}]"] = cid
        data = self._call("mod_assign_get_assignments", **params)
        assignments = []
        for course in data.get("courses", []):
            for a in course.get("assignments", []):
                assignments.append({
                    "id": a.get("id"),
                    "course_id": course.get("id"),
                    "name": a.get("name"),
                    "duedate": a.get("duedate"),
                    "cutoffdate": a.get("cutoffdate"),
                })
        return assignments

    def get_user_last_access(self, course_id: int) -> list[dict]:
        users = self.get_enrolled_users(course_id)
        return [{
            "user_id": u.get("id"),
            "fullname": u.get("fullname"),
            "lastaccess": u.get("lastaccess", 0),
            "lastcourseaccess": u.get("lastcourseaccess", 0),
        } for u in users]


class MoodleAPIError(Exception):
    pass


def create_moodle_client(db=None) -> Optional[MoodleAPIClient]:
    if db:
        try:
            from ..models.system_setting import SystemSetting
            url_setting = db.query(SystemSetting).filter(SystemSetting.key == "moodle_api_url").first()
            token_setting = db.query(SystemSetting).filter(SystemSetting.key == "moodle_api_token").first()
            if url_setting and token_setting:
                return MoodleAPIClient(url_setting.value, token_setting.value)
        except Exception:
            pass
    return None


def fetch_with_fallback(db, moodle_func: str, scraping_func, **kwargs):
    """Intenta Moodle API, si falla usa scraping. Returns (data, source)."""
    client = create_moodle_client(db)
    if client:
        try:
            method = getattr(client, moodle_func)
            data = method(**kwargs)
            logger.info(f"Moodle API: {moodle_func} exitoso")
            return data, "api"
        except (MoodleAPIError, Exception) as e:
            logger.warning(f"Moodle API falló ({moodle_func}): {e}. Usando scraping.")
    try:
        data = scraping_func(**kwargs)
        return data, "scraping"
    except Exception as e:
        logger.error(f"Scraping también falló: {e}")
        raise
