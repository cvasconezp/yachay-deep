import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { YachayLogo } from "../components/YachayLogo";

/* ── Data ─────────────────────────────────────────────── */

const STATS = [
  { value: "2,300+", label: "Estudiantes monitoreados" },
  { value: "18", label: "Carreras virtuales" },
  { value: "8", label: "Períodos académicos" },
  { value: "5", label: "Fases implementadas" },
];

const CAPAS = [
  {
    name: "Learning Analytics",
    desc: "Recopila, mide e interpreta datos de comportamiento educativo y compromiso académico: accesos al LMS, tareas, calificaciones e interacción.",
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
  {
    name: "Early Warning System",
    desc: "Identifica señales de riesgo antes del fracaso: inactividad, bajo compromiso, incumplimiento de actividades y factores administrativos.",
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
    ),
  },
  {
    name: "Decision Support System",
    desc: "Convierte la analítica en acción: fichas de estudiantes, dashboards, listas de tutoría, recomendaciones automáticas y derivación a Bienestar.",
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
  },
];

const PHASES = [
  { phase: "Fase 1", title: "Analítica descriptiva y diagnóstica", status: "completed",
    desc: "Dashboards de riesgo, fichas de estudiante, analítica por asignatura y docente, tutorías e intervenciones." },
  { phase: "Fase 2", title: "Analítica predictiva", status: "completed",
    desc: "Modelos de machine learning (Logistic Regression, Random Forest) entrenados con 8 períodos históricos." },
  { phase: "Fase 3", title: "Explicación del riesgo (XAI)", status: "completed",
    desc: "Cada predicción incluye los 3 factores principales que la explican, comparados con la media de la carrera." },
  { phase: "Fase 4", title: "Recomendaciones automáticas", status: "completed",
    desc: "10 categorías de recomendación priorizadas (urgente / importante / sugerida) con acción, motivo y destinatario." },
  { phase: "Fase 5", title: "Intervenciones de ciclo cerrado", status: "completed",
    desc: "Registro, seguimiento, derivación a Bienestar Estudiantil y trazabilidad completa de cada intervención." },
];

const NIVELES = [
  { level: "Estudiante", emoji: "\uD83E\uDDD1\u200D\uD83C\uDF93", desc: "Accesos, tareas, calificaciones, historial, predicciones ML" },
  { level: "Asignatura", emoji: "\uD83D\uDCDA", desc: "Promedios, aprobación, repitencia, materias críticas" },
  { level: "Docente", emoji: "\uD83D\uDC68\u200D\uD83C\uDFEB", desc: "Carga académica, gestión de cursos, concentración de riesgo" },
  { level: "Administrativo", emoji: "\uD83C\uDFDB\uFE0F", desc: "Matrícula, deuda, bloqueos financieros" },
  { level: "Intervención", emoji: "\uD83E\uDD1D", desc: "Acciones institucionales, seguimiento, impacto" },
];

const EVOLUTION = [
  {
    period: "2023 - 2025",
    title: "MonitorP67 en Excel",
    desc: "Sistema de inteligencia académica con 41 hojas, 57 consultas Power Query, 31 tablas estructuradas, macros VBA, dashboard FichaEst con resolución automática de identidad, árbol de decisión de riesgo y 11 formatos condicionales.",
  },
  {
    period: "2025 - 2026",
    title: "Plataforma web Yachay Deep",
    desc: "Migración a FastAPI + React + PostgreSQL. Pipeline ETL automatizado, 28 endpoints REST, modelos predictivos por carrera, XAI, recomendaciones automáticas, ciclo cerrado de intervención y soporte multi-carrera.",
  },
];

const PODCASTS = [
  {
    title: "Yachay Deep: Un framework multinivel de inteligencia académica para la retención estudiantil",
    description: "Una visión general de Yachay Deep como sistema de soporte a la decisión con alerta temprana impulsado por analítica del aprendizaje.",
    file: "/Yachay Deep A Multilevel Intelligence Framework for Student Retention.m4a",
  },
  {
    title: "IA para evitar el abandono universitario",
    description: "Cómo la inteligencia artificial y la analítica del aprendizaje pueden anticipar el riesgo de deserción.",
    file: "/IA_para_evitar_el_abandono_universitario.m4a",
  },
  {
    title: "El Excel que frena el abandono universitario",
    description: "El origen de Yachay Deep: un sistema en Excel con macros VBA que evolucionó hacia una plataforma web.",
    file: "/El_Excel_que_frena_el_abandono_universitario.m4a",
  },
];

const TECH = [
  { cat: "Backend", items: "FastAPI, Python 3.11+, SQLAlchemy, Pandas" },
  { cat: "Frontend", items: "React 18, Vite, Tailwind CSS, Recharts" },
  { cat: "Base de datos", items: "PostgreSQL (prod), SQLite (dev)" },
  { cat: "ML / XAI", items: "scikit-learn, joblib, SHAP-style" },
  { cat: "Exportación", items: "openpyxl (Excel), ReportLab (PDF)" },
  { cat: "Despliegue", items: "Railway, Vercel, GitHub" },
];

/* ── Component ────────────────────────────────────────── */

export default function Landing() {
  const navigate = useNavigate();
  const [playingIdx, setPlayingIdx] = useState(null);

  return (
    <div className="min-h-screen bg-white">
      {/* ── Navbar ── */}
      <nav className="fixed top-0 w-full bg-white/90 backdrop-blur-sm border-b border-gray-100 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <YachayLogo size={36} />
            <span className="font-bold text-brand text-lg">Yachay Deep</span>
          </div>
          <div className="flex items-center gap-3">
            <a href="#features" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Funcionalidades</a>
            <a href="#evolution" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Evolución</a>
            <a href="#podcasts" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Podcasts</a>
            <a href="#contact" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Contacto</a>
            <button
              onClick={() => navigate("/login")}
              className="bg-brand-gold text-brand-dark font-semibold text-sm px-5 py-2 rounded-lg hover:bg-brand-gold-light transition-colors"
            >
              Iniciar sesión
            </button>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="pt-32 pb-20 bg-gradient-to-br from-brand via-brand-dark to-brand">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <div className="flex justify-center mb-6">
            <YachayLogo size={100} />
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 leading-tight">
            Inteligencia académica preventiva<br />para la retención estudiantil
          </h1>
          <p className="text-brand-ice text-lg md:text-xl max-w-3xl mx-auto mb-4">
            Learning Analytics-Driven Early Warning Decision Support System
          </p>
          <p className="text-blue-200 max-w-2xl mx-auto mb-10 text-sm leading-relaxed">
            Yachay Deep identifica, predice, explica y atiende el riesgo académico
            mediante un framework multinivel con IA explicable, recomendaciones automáticas
            y trazabilidad de intervenciones de ciclo cerrado.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-14">
            <button
              onClick={() => navigate("/login")}
              className="bg-brand-gold text-brand-dark font-semibold px-8 py-3 rounded-xl text-base hover:bg-brand-gold-light transition-colors shadow-lg"
            >
              Acceder a la plataforma
            </button>
            <a
              href="#features"
              className="border-2 border-white/30 text-white font-semibold px-8 py-3 rounded-xl text-base hover:bg-white/10 transition-colors"
            >
              Conocer más
            </a>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
            {STATS.map((s, i) => (
              <div key={i} className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/10">
                <div className="text-3xl font-bold text-brand-gold">{s.value}</div>
                <div className="text-blue-200 text-xs mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pacha Tech banner ── */}
      <section className="bg-gray-50 border-b border-gray-100 py-6">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-center gap-3 text-center">
          <span className="text-sm text-gray-500">Diseñado y desarrollado por</span>
          <span className="font-bold text-brand text-lg tracking-wide">Pacha Tech</span>
          <span className="text-sm text-gray-400 hidden sm:inline">|</span>
          <span className="text-sm text-gray-500">Soluciones de inteligencia académica para carreras virtuales</span>
        </div>
      </section>

      {/* ── 3 Capas ── */}
      <section id="features" className="py-20">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="Tres capas integradas"
            subtitle="Yachay Deep no es solo un dashboard ni solo un sistema de alerta. Es la integración de Learning Analytics, Early Warning y Decision Support en un único sistema."
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
            {CAPAS.map((c, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-2xl p-6 hover:shadow-lg transition-shadow">
                <div className="w-14 h-14 bg-gradient-to-br from-brand to-brand-light rounded-xl flex items-center justify-center text-white mb-4">
                  {c.icon}
                </div>
                <h3 className="font-bold text-gray-900 text-lg mb-2">{c.name}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{c.desc}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 bg-gray-50 rounded-xl p-4 text-center">
            <span className="font-mono text-xs text-gray-500">
              Datos educativos &rarr; Learning Analytics &rarr; Modelo de riesgo &rarr; Early Warning &rarr; Decision Support &rarr; Intervención
            </span>
          </div>
        </div>
      </section>

      {/* ── Enfoque multinivel ── */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="Enfoque multinivel"
            subtitle="El abandono y el bajo rendimiento son fenómenos multicausales. Yachay Deep analiza cinco niveles simultáneamente."
          />
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-12">
            {NIVELES.map((n, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-xl p-5 text-center hover:shadow-md transition-shadow">
                <div className="text-3xl mb-3">{n.emoji}</div>
                <div className="font-semibold text-gray-800 text-sm">{n.level}</div>
                <div className="text-xs text-gray-500 mt-1 leading-relaxed">{n.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 5 Fases ── */}
      <section className="py-20">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="Cinco fases de madurez analítica"
            subtitle="Desde la analítica descriptiva hasta las intervenciones de ciclo cerrado. Todas implementadas y operativas."
          />
          <div className="mt-12 space-y-4">
            {PHASES.map((p, i) => (
              <div key={i} className="flex gap-4 items-start bg-white border border-green-200 rounded-xl p-5 hover:shadow-md transition-shadow">
                <div className="flex-shrink-0 w-10 h-10 bg-green-600 text-white rounded-full flex items-center justify-center font-bold text-sm">
                  {i + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="font-bold text-gray-900">{p.title}</span>
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">Completada</span>
                  </div>
                  <p className="text-gray-500 text-sm leading-relaxed">{p.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Evolucion ── */}
      <section id="evolution" className="py-20 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="De Excel a plataforma web"
            subtitle="Yachay Deep nació como un sistema sofisticado en Excel con Power Query, macros VBA y dashboard dinámico. Hoy es una plataforma web completa."
          />
          <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-6">
            {EVOLUTION.map((e, i) => (
              <div key={i} className={`rounded-2xl p-6 border ${i === 0 ? "bg-white border-gray-200" : "bg-gradient-to-br from-brand to-brand-light text-white border-transparent"}`}>
                <div className={`text-xs font-semibold uppercase tracking-wider mb-2 ${i === 0 ? "text-brand-gold" : "text-brand-ice"}`}>
                  {e.period}
                </div>
                <h3 className={`text-xl font-bold mb-3 ${i === 0 ? "text-gray-900" : "text-white"}`}>{e.title}</h3>
                <p className={`text-sm leading-relaxed ${i === 0 ? "text-gray-500" : "text-blue-100"}`}>{e.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tech stack ── */}
      <section className="py-20">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader title="Stack tecnológico" />
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mt-10">
            {TECH.map((t, i) => (
              <div key={i} className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                <div className="font-semibold text-gray-800 text-sm mb-1">{t.cat}</div>
                <div className="text-xs text-gray-500">{t.items}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Podcasts ── */}
      <section id="podcasts" className="py-20 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="Podcasts"
            subtitle="Episodios que explican el contexto, motivación y evolución de Yachay Deep."
          />
          <div className="mt-12 space-y-4">
            {PODCASTS.map((pod, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-gradient-to-br from-brand to-brand-light rounded-xl flex items-center justify-center flex-shrink-0">
                    <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM8 11a4 4 0 0 0 8 0h2a6 6 0 0 1-5 5.91V20h3v2H8v-2h3v-3.09A6 6 0 0 1 6 11h2z" />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 text-sm">{pod.title}</h3>
                    <p className="text-xs text-gray-500 mt-1">{pod.description}</p>
                    <audio controls className="mt-3 w-full" onPlay={() => setPlayingIdx(i)} preload="none">
                      <source src={pod.file} type="audio/mp4" />
                    </audio>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA / Contact ── */}
      <section id="contact" className="py-20 bg-gradient-to-br from-brand via-brand-dark to-brand">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Lleva Yachay Deep a tu institución
          </h2>
          <p className="text-blue-200 mb-10 max-w-2xl mx-auto leading-relaxed">
            Yachay Deep es adaptable a cualquier institución de educación superior con modalidad virtual o híbrida.
            Contacta a Pacha Tech para explorar cómo implementarlo.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <a
              href="mailto:cvasconezp@gmail.com"
              className="bg-brand-gold text-brand-dark font-semibold px-8 py-3 rounded-xl text-base hover:bg-brand-gold-light transition-colors shadow-lg inline-flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              cvasconezp@gmail.com
            </a>
            <a
              href="https://www.linkedin.com/in/cvasconezp/"
              target="_blank"
              rel="noopener noreferrer"
              className="border-2 border-white/30 text-white font-semibold px-8 py-3 rounded-xl text-base hover:bg-white/10 transition-colors inline-flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
              </svg>
              LinkedIn
            </a>
          </div>

          {/* Creator card */}
          <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 max-w-lg mx-auto border border-white/10">
            <div className="flex items-center gap-4 mb-3">
              <div className="w-14 h-14 bg-white/20 rounded-full flex items-center justify-center text-xl font-bold text-white border-2 border-white/30">
                CV
              </div>
              <div className="text-left">
                <div className="font-bold text-white">Carlos Vasconez-Paredes</div>
                <div className="text-blue-200 text-xs">Creador de Yachay Deep | Pacha Tech</div>
              </div>
            </div>
            <p className="text-blue-200 text-xs leading-relaxed text-left">
              Docente, gestor de Analítica del Aprendizaje e investigador. Su trabajo integra pedagogía,
              ciencia de datos y tecnologías emergentes para mejorar la permanencia estudiantil en educación superior.
            </p>
            <div className="flex gap-3 mt-4">
              <a href="https://orcid.org/0000-0002-1574-346X" target="_blank" rel="noopener noreferrer"
                className="text-xs bg-white/10 text-white px-3 py-1.5 rounded-lg hover:bg-white/20 transition-colors">ORCID</a>
              <a href="https://scholar.google.com/citations?user=w46QDacAAAAJ&hl=es" target="_blank" rel="noopener noreferrer"
                className="text-xs bg-white/10 text-white px-3 py-1.5 rounded-lg hover:bg-white/20 transition-colors">Google Académico</a>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-brand-dark py-8 border-t border-white/5">
        <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <YachayLogo size={28} />
            <span className="text-white font-semibold text-sm">Yachay Deep</span>
          </div>
          <div className="text-gray-400 text-xs text-center">
            &copy; {new Date().getFullYear()} Carlos Vasconez-Paredes | Pacha Tech | Soluciones de inteligencia académica para carreras virtuales
          </div>
          <button
            onClick={() => navigate("/login")}
            className="text-brand-gold text-sm font-medium hover:text-brand-gold-light transition-colors"
          >
            Iniciar sesión &rarr;
          </button>
        </div>
      </footer>
    </div>
  );
}

/* ── Helpers ───────────────────────────────────────────── */

function SectionHeader({ title, subtitle }) {
  return (
    <div className="text-center">
      <h2 className="text-2xl md:text-3xl font-bold text-gray-900">{title}</h2>
      {subtitle && <p className="text-gray-500 mt-3 max-w-2xl mx-auto leading-relaxed">{subtitle}</p>}
    </div>
  );
}
