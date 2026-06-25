"""
Épica 5.2b: Clustering de Perfiles de Riesgo

K-Means clustering sobre features de estudiantes para descubrir
perfiles de riesgo emergentes (3-7 clusters).
"""
from __future__ import annotations

import logging
from typing import Optional
import numpy as np
from sqlalchemy.orm import Session

from ..models.student import Student

logger = logging.getLogger(__name__)

CLUSTER_FEATURES = [
    "indice_compromiso", "dias_sin_acceso", "porcentaje_tareas",
    "prob_desercion", "prob_reprobacion", "score_recuperabilidad",
]

# Cache de resultados
_CLUSTER_CACHE: dict = {}


def run_clustering(db: Session, n_clusters: int = 5, periodo: Optional[str] = None) -> dict:
    """Ejecuta K-Means clustering sobre estudiantes activos.

    Args:
        db: sesión de base de datos
        n_clusters: número de clusters (3-7)
        periodo: filtrar por período

    Returns:
        dict con clusters, centroids, descriptions, silhouette_score
    """
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score

    n_clusters = max(3, min(7, n_clusters))

    # Obtener estudiantes
    q = db.query(Student).filter(Student.nivel_riesgo.isnot(None))
    if periodo:
        q = q.filter(Student.periodo == periodo)
    students = q.all()

    if len(students) < n_clusters * 3:
        return {
            "status": "insufficient_data",
            "n_students": len(students),
            "min_required": n_clusters * 3,
        }

    # Construir matrix de features
    X = []
    student_ids = []
    for s in students:
        row = [
            float(s.indice_compromiso or 0),
            float(s.dias_sin_acceso or 0),
            float(s.porcentaje_tareas or 0),
            float(s.prob_desercion or 0),
            float(s.prob_reprobacion or 0),
            float(s.score_recuperabilidad or 50),
        ]
        X.append(row)
        student_ids.append(s.id)

    X = np.array(X)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # K-Means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Silhouette score
    if len(set(labels)) >= 2:
        sil_score = float(silhouette_score(X_scaled, labels))
    else:
        sil_score = 0.0

    # Centroids en escala original
    centroids_original = scaler.inverse_transform(kmeans.cluster_centers_)

    # Construir descripción de cada cluster
    clusters = []
    for i in range(n_clusters):
        mask = labels == i
        cluster_X = X[mask]
        cluster_students = [student_ids[j] for j in range(len(labels)) if labels[j] == i]

        profile = {}
        for j, feat in enumerate(CLUSTER_FEATURES):
            vals = cluster_X[:, j]
            profile[feat] = {
                "mean": round(float(np.mean(vals)), 3),
                "std": round(float(np.std(vals)), 3),
            }

        # Auto-descripción del perfil
        desc = _describe_cluster(profile)

        clusters.append({
            "cluster_id": i,
            "n_students": int(mask.sum()),
            "porcentaje": round(int(mask.sum()) / len(students) * 100, 1),
            "profile": profile,
            "descripcion": desc,
            "centroid": {feat: round(float(v), 3) for feat, v in zip(CLUSTER_FEATURES, centroids_original[i])},
            "student_ids": cluster_students[:50],  # Limitar para no sobrecargar
        })

    clusters.sort(key=lambda c: c["n_students"], reverse=True)

    result = {
        "status": "success",
        "n_clusters": n_clusters,
        "n_students": len(students),
        "silhouette_score": round(sil_score, 3),
        "clusters": clusters,
    }

    _CLUSTER_CACHE["latest"] = result
    return result


def _describe_cluster(profile: dict) -> str:
    """Genera descripción textual automática del perfil de un cluster."""
    compromiso = profile.get("indice_compromiso", {}).get("mean", 0)
    dias = profile.get("dias_sin_acceso", {}).get("mean", 0)
    tareas = profile.get("porcentaje_tareas", {}).get("mean", 0)
    desercion = profile.get("prob_desercion", {}).get("mean", 0)
    recuperabilidad = profile.get("score_recuperabilidad", {}).get("mean", 50)

    parts = []

    if compromiso >= 0.7:
        parts.append("alto compromiso")
    elif compromiso >= 0.4:
        parts.append("compromiso moderado")
    else:
        parts.append("bajo compromiso")

    if dias > 14:
        parts.append("inactivos prolongados")
    elif dias > 7:
        parts.append("inactividad reciente")
    else:
        parts.append("activos")

    if tareas >= 70:
        parts.append("buen cumplimiento de tareas")
    elif tareas >= 40:
        parts.append("cumplimiento parcial de tareas")
    else:
        parts.append("tareas muy atrasadas")

    if desercion > 0.7:
        parts.append("riesgo crítico de deserción")
    elif desercion > 0.4:
        parts.append("riesgo moderado")
    else:
        parts.append("bajo riesgo")

    if recuperabilidad >= 65:
        parts.append("alta recuperabilidad")
    elif recuperabilidad < 35:
        parts.append("difícil recuperación")

    return "Estudiantes con " + ", ".join(parts)


def get_cluster_status() -> dict:
    """Retorna el último resultado de clustering."""
    cached = _CLUSTER_CACHE.get("latest")
    if not cached:
        return {"status": "not_run", "message": "Clustering no ejecutado aún"}
    return {
        "status": cached["status"],
        "n_clusters": cached["n_clusters"],
        "n_students": cached["n_students"],
        "silhouette_score": cached["silhouette_score"],
    }
