import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { YachayLogo } from "../components/YachayLogo";

/* ── Animated Counter Hook ───────────────────────────── */

function useCountUp(end, duration = 2000, startOnView = true) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const started = useRef(false);

  const animate = useCallback(() => {
    if (started.current) return;
    started.current = true;
    const startTime = performance.now();
    const step = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * end));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [end, duration]);

  useEffect(() => {
    if (!startOnView) { animate(); return; }
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { animate(); obs.disconnect(); } },
      { threshold: 0.3 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [animate, startOnView]);

  return { count, ref };
}

/* ── Data ─────────────────────────────────────────────── */

const STATS = [
  { target: 3040, suffix: "+", label: "Estudiantes monitoreados" },
  { target: 25, suffix: "", label: "Carreras virtuales" },
  { target: 334, suffix: "", label: "Asignaturas analizadas" },
  { target: 740, suffix: "+", label: "Aulas virtuales" },
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
    desc: "Factores explicativos, alertas conductuales, escenarios contrafactuales y análisis What-If para cada estudiante." },
  { phase: "Fase 4", title: "Recomendaciones automáticas", status: "completed",
    desc: "10 categorías de recomendación priorizadas con acción, motivo, medio y destinatario. Exportación Excel configurable." },
  { phase: "Fase 5", title: "Intervenciones inteligentes y ciclo cerrado", status: "completed",
    desc: "Registro con snapshots, medición de impacto antes/después, feedback loop ML y derivación a Bienestar Estudiantil." },
  { phase: "Fase 6", title: "Integración LMS completa", status: "upcoming",
    desc: "APIs de Moodle/Canvas, actualización en tiempo real, notificaciones automatizadas y trazabilidad institucional." },
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
    title: "El Excel que frena el abandono universitario",
    description: "El origen de Yachay Deep: un sistema en Excel con macros VBA que evolucionó hacia una plataforma web.",
    file: "/El_Excel_que_frena_el_abandono_universitario_02.mp3",
  },
  {
    title: "IA para evitar el abandono universitario",
    description: "Cómo la inteligencia artificial y la analítica del aprendizaje pueden anticipar el riesgo de deserción.",
    file: "/IA_para_evitar_el_abandono_universitario.m4a",
  },
  {
    title: "Yachay Deep: Un framework multinivel de inteligencia académica para la retención estudiantil",
    description: "Una visión general de Yachay Deep como sistema de soporte a la decisión con alerta temprana impulsado por analítica del aprendizaje.",
    file: "/Yachay Deep A Multilevel Intelligence Framework for Student Retention.m4a",
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

const PLANS = [
  {
    name: "Profesional",
    desc: "IA predictiva + gestión de intervenciones",
    totalSem: "5,000",
    totalAnn: "8,000",
    perStudent: "$6/estudiante activo",
    periodLabel: "/semestre",
    periodLabelAnn: "/año",
    features: [
      { text: "Dashboard de riesgo en tiempo real", ok: true },
      { text: "Alertas académicas configurables", ok: true },
      { text: "Predicciones ML con 87%+ precisión", ok: true },
      { text: "Simulaciones What-If y contrafactuales", ok: true },
      { text: "Gestión de intervenciones + impacto", ok: true },
      { text: "Fichas estudiantiles completas", ok: true },
      { text: "Exportaciones Excel/PDF", ok: true },
      { text: "Analytics de docentes y asignaturas", ok: true },
      { text: "10 usuarios · Soporte email + chat", ok: true },
    ],
    cta: "Agendar demostración",
    featured: true,
  },
  {
    name: "Enterprise",
    desc: "Control total para universidades grandes",
    totalSem: "15,000",
    totalAnn: "24,000",
    perStudent: "$10/est (≤5K) · $5/est (>5K)",
    periodLabel: "/semestre",
    periodLabelAnn: "/año",
    features: [
      { text: "Todo del plan Profesional", ok: true },
      { text: "Tracking avanzado de docentes", ok: true },
      { text: "Comparativa multi-periodo", ok: true },
      { text: "API de integración REST", ok: true },
      { text: "Instancia dedicada opcional", ok: true },
      { text: "Usuarios ilimitados", ok: true },
      { text: "Soporte dedicado 24/7", ok: true },
      { text: "SLA 99.9% disponibilidad", ok: true },
    ],
    cta: "Contactar Ventas",
    featured: false,
  },
];

const FAQS = [
  { q: "¿Cuánto toma la implementación?", a: "El proceso completo toma entre 2 y 4 semanas, dependiendo de la disponibilidad de datos históricos y la complejidad de integración con tu LMS. Incluye configuración, calibración de modelos ML, capacitación del equipo y acompañamiento en go-live." },
  { q: "¿Funciona con mi Moodle actual?", a: "Sí. Yachay Deep se integra con cualquier instalación de Moodle mediante scraping automatizado de datos de actividad. No requiere plugins adicionales ni cambios en tu Moodle. También soportamos importación por Excel/CSV para otros sistemas." },
  { q: "¿Qué precisión tienen las predicciones?", a: "Nuestros modelos alcanzan un 87%+ de precisión en predicción de aprobación/deserción, entrenados con datos reales de tu institución. La precisión mejora conforme acumulamos más datos históricos." },
  { q: "¿Puedo probar antes de comprar?", a: "Primero agendamos una demostración donde te mostramos la plataforma en acción. Si hay interés, activamos un piloto gratuito de 30 días con el plan Profesional usando tus propios datos, incluyendo onboarding completo y soporte prioritario. Sin compromiso de compra." },
  { q: "¿Mis datos están seguros?", a: "Absolutamente. Usamos cifrado TLS 1.3 en tránsito y AES-256 en reposo. Autenticación con cookies HttpOnly, control de acceso por roles (RBAC), y cumplimiento con la Ley Orgánica de Protección de Datos Personales de Ecuador." },
  { q: "¿Cuántos estudiantes se necesitan como mínimo?", a: "Nuestros planes están diseñados para instituciones con 500+ estudiantes activos. El modelo de ML requiere un mínimo de datos históricos para funcionar con precisión. Durante el piloto gratuito evaluamos la viabilidad con tus datos reales." },
  { q: "¿Cómo se calcula el precio de mi institución?", a: "El precio se calcula multiplicando la tarifa del plan por el número de estudiantes activos. Cada plan tiene un mínimo semestral que cubre los costos base de infraestructura y soporte: si el cálculo es menor al mínimo, se cobra el mínimo. Por ejemplo, un instituto con 500 estudiantes en el plan Profesional ($6/est): 500 × $6 = $3,000, pero el mínimo es $5,000, así que paga $5,000/semestre. Una universidad con 3,000 estudiantes en Profesional: 3,000 × $6 = $18,000/semestre. El plan Enterprise incluye tarifa degresiva: $10/est para los primeros 5,000 y $5/est a partir del 5,001. La contratación anual tiene un 20% de descuento." },
];

export default function Landing() {
  const navigate = useNavigate();
  const [playingIdx, setPlayingIdx] = useState(null);
  const [annual, setAnnual] = useState(false);
  const [openFaq, setOpenFaq] = useState(null);

  return (
    <div className="min-h-screen bg-white">
      {/* ── Navbar ── */}
      <nav className="fixed top-0 w-full bg-white/90 backdrop-blur-sm border-b border-gray-100 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Navbar bg is white → CLARO header. Sized responsively to feel
                like the dominant brand element on the top bar. */}
            <YachayLogo variant="light" className="h-10 sm:h-11 lg:h-12 w-auto" />
          </div>
          <div className="flex items-center gap-3">
            <a href="#features" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Funcionalidades</a>
            <a href="#evolution" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Evolución</a>
            <a href="#pricing" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Planes</a>
            <a href="#podcasts" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Podcasts</a>
            <a href="#contact" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Contacto</a>
            <a href="https://pachatech.vercel.app/" target="_blank" rel="noopener noreferrer" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Pacha Tech</a>
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
          <div className="flex justify-center mb-10">
            {/* Hero bg is dark gradient → use OSCURO directly (white "Deep"
                wordmark reads with full contrast on the navy gradient).
                Logo is the dominant focal point; scales fluidly with viewport. */}
            <YachayLogo
              variant="dark"
              className="block w-[min(92vw,34rem)] sm:w-[min(80vw,44rem)] lg:w-[min(65vw,56rem)] h-auto drop-shadow-2xl"
            />
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

          {/* Stats — animated counters */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
            {STATS.map((s, i) => (
              <AnimatedStat key={i} target={s.target} suffix={s.suffix} label={s.label} delay={i * 150} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Pacha Tech banner ── */}
      <section className="bg-gray-50 border-b border-gray-100 py-8">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6 bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-brand to-brand-light rounded-xl flex items-center justify-center flex-shrink-0">
                <span className="text-white font-bold text-lg">PT</span>
              </div>
              <div className="text-center sm:text-left">
                <div className="font-bold text-brand text-lg tracking-wide">Pacha Tech</div>
                <p className="text-sm text-gray-500 max-w-md">
                  Soluciones de inteligencia académica, analítica del aprendizaje y tecnologías emergentes para educación superior.
                </p>
              </div>
            </div>
            <a
              href="https://pachatech.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="bg-brand text-white font-semibold text-sm px-6 py-2.5 rounded-lg hover:bg-brand-light transition-colors inline-flex items-center gap-2 flex-shrink-0"
            >
              Visitar Pacha Tech
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
            </a>
          </div>
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
      <section id="podcasts" className="py-20 bg-gradient-to-br from-brand-dark via-brand to-brand-light">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-1.5 rounded-full mb-4">
              <svg className="w-4 h-4 text-brand-gold" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM8 11a4 4 0 0 0 8 0h2a6 6 0 0 1-5 5.91V20h3v2H8v-2h3v-3.09A6 6 0 0 1 6 11h2z" />
              </svg>
              <span className="text-xs font-semibold text-brand-gold tracking-wider uppercase">Podcast</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-bold text-white">Escucha Yachay Deep</h2>
            <p className="text-blue-200 mt-3 max-w-2xl mx-auto leading-relaxed">
              Episodios que explican el contexto, motivación y evolución del framework.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {PODCASTS.map((pod, i) => (
              <div
                key={i}
                className={`relative rounded-2xl overflow-hidden transition-all duration-300 ${
                  playingIdx === i
                    ? "bg-white shadow-2xl shadow-brand-gold/20 ring-2 ring-brand-gold/40 scale-[1.02]"
                    : "bg-white/10 backdrop-blur-sm border border-white/15 hover:bg-white/15 hover:border-white/25"
                }`}
              >
                <div className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold ${
                      playingIdx === i ? "bg-brand-gold text-brand-dark" : "bg-white/15 text-white"
                    }`}>
                      {playingIdx === i ? (
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                        </svg>
                      ) : (
                        <span>{i + 1}</span>
                      )}
                    </div>
                    <span className={`text-xs font-medium uppercase tracking-wider ${
                      playingIdx === i ? "text-brand-gold" : "text-brand-ice/70"
                    }`}>
                      Episodio {i + 1}
                    </span>
                  </div>
                  <h3 className={`font-bold text-base mb-2 leading-snug ${
                    playingIdx === i ? "text-gray-900" : "text-white"
                  }`}>
                    {pod.title}
                  </h3>
                  <p className={`text-xs leading-relaxed mb-4 ${
                    playingIdx === i ? "text-gray-500" : "text-blue-200/80"
                  }`}>
                    {pod.description}
                  </p>
                  <audio
                    controls
                    className="w-full"
                    onPlay={() => setPlayingIdx(i)}
                    onPause={() => { if (playingIdx === i) setPlayingIdx(null); }}
                    onEnded={() => { if (playingIdx === i) setPlayingIdx(null); }}
                    preload="none"
                  >
                    <source src={pod.file} type={pod.file.endsWith('.mp3') ? 'audio/mpeg' : pod.file.endsWith('.wav') ? 'audio/wav' : 'audio/mp4'} />
                  </audio>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="py-20 bg-white">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 bg-brand/5 px-4 py-1.5 rounded-full mb-4">
              <span className="text-xs font-semibold text-brand tracking-wider uppercase">Planes y precios</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3">
              Planes que se adaptan a tu institución
            </h2>
            <p className="text-gray-500 max-w-2xl mx-auto leading-relaxed">
              Inversión clara por semestre. Sin costos ocultos. Precio escala con tu matrícula.
            </p>

            {/* Toggle */}
            <div className="flex items-center justify-center gap-3 mt-6">
              <span className={`text-sm font-medium ${!annual ? "text-gray-900" : "text-gray-400"}`}>Semestral</span>
              <button
                onClick={() => setAnnual(!annual)}
                className={`relative w-12 h-6 rounded-full transition-colors ${annual ? "bg-brand" : "bg-gray-300"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${annual ? "translate-x-6" : ""}`} />
              </button>
              <span className={`text-sm font-medium ${annual ? "text-gray-900" : "text-gray-400"}`}>Anual</span>
              <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-semibold">Ahorra 20%</span>
            </div>
          </div>

          {/* Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {PLANS.map((plan, i) => (
              <div
                key={i}
                className={`relative rounded-2xl p-8 transition-all duration-200 hover:-translate-y-1 ${
                  plan.featured
                    ? "bg-white border-2 border-brand shadow-xl shadow-brand/10 hover:shadow-2xl"
                    : "bg-white border border-gray-200 hover:shadow-lg"
                }`}
              >
                {plan.featured && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-brand-gold text-brand-dark text-xs font-bold px-4 py-1 rounded-full">
                    Más Popular
                  </div>
                )}
                <div className="mb-6">
                  <h3 className="text-xl font-bold text-gray-900">{plan.name}</h3>
                  <p className="text-sm text-gray-500 mt-1">{plan.desc}</p>
                </div>
                <div className="mb-1">
                  <span className="text-sm text-gray-500">Desde </span>
                  <span className="text-4xl font-extrabold text-gray-900">${annual ? plan.totalAnn : plan.totalSem}</span>
                  <span className="text-gray-500 text-sm ml-1">{annual ? plan.periodLabelAnn : plan.periodLabel}</span>
                </div>
                <p className="text-xs text-gray-400 mb-6">{plan.perStudent} · descuento anual 20%</p>
                <ul className="space-y-3 mb-8">
                  {plan.features.map((f, j) => (
                    <li key={j} className="flex items-start gap-2.5 text-sm">
                      {f.ok ? (
                        <svg className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5 text-gray-300 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                      <span className={f.ok ? "text-gray-700" : "text-gray-400"}>{f.text}</span>
                    </li>
                  ))}
                </ul>
                <a
                  href="#contact"
                  className={`block w-full text-center py-3 rounded-xl font-semibold transition-colors ${
                    plan.featured
                      ? "bg-brand-gold text-brand-dark hover:bg-brand-gold-light"
                      : "bg-gray-100 text-gray-800 hover:bg-gray-200"
                  }`}
                >
                  {plan.cta}
                </a>
              </div>
            ))}
          </div>

          {/* Guarantees */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-6 mt-10 text-sm text-gray-500">
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
              Demostración sin compromiso
            </span>
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
              Sin tarjeta de crédito
            </span>
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
              Garantía de satisfacción 60 días
            </span>
          </div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-3xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3">Preguntas frecuentes</h2>
            <p className="text-gray-500">Todo lo que necesitas saber sobre Yachay Deep</p>
          </div>
          <div className="space-y-0">
            {FAQS.map((faq, i) => (
              <div key={i} className="border-b border-gray-200">
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between py-5 text-left"
                >
                  <span className="font-semibold text-gray-900 pr-4">{faq.q}</span>
                  <svg
                    className={`w-5 h-5 text-brand flex-shrink-0 transition-transform ${openFaq === i ? "rotate-45" : ""}`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                </button>
                <div className={`overflow-hidden transition-all duration-300 ${openFaq === i ? "max-h-60 pb-5" : "max-h-0"}`}>
                  <p className="text-gray-500 text-sm leading-relaxed">{faq.a}</p>
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
            Empieza a retener estudiantes hoy
          </h2>
          <p className="text-blue-200 mb-10 max-w-2xl mx-auto leading-relaxed">
            Agenda una demostración personalizada y conoce cómo Yachay Deep puede ayudar a tu institución.
            Si decides avanzar, incluimos 30 días de prueba gratuita con tus propios datos.
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
            <a
              href="https://pachatech.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="border-2 border-white/30 text-white font-semibold px-8 py-3 rounded-xl text-base hover:bg-white/10 transition-colors inline-flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 003 12c0-1.605.42-3.113 1.157-4.418" />
              </svg>
              Pacha Tech
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
            <YachayLogo variant="dark" className="h-7 sm:h-8 w-auto" />
          </div>
          <div className="text-gray-400 text-xs text-center">
            &copy; {new Date().getFullYear()} Carlos Vasconez-Paredes |{" "}
            <a href="https://pachatech.vercel.app/" target="_blank" rel="noopener noreferrer" className="text-brand-ice hover:text-white transition-colors">Pacha Tech</a>
            {" "}| Soluciones de inteligencia académica para carreras virtuales
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

function AnimatedStat({ target, suffix, label, delay = 0 }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          obs.disconnect();
          setTimeout(() => {
            const duration = 2000;
            const startTime = performance.now();
            const step = (now) => {
              const elapsed = now - startTime;
              const progress = Math.min(elapsed / duration, 1);
              const eased = 1 - Math.pow(1 - progress, 3);
              setCount(Math.round(eased * target));
              if (progress < 1) requestAnimationFrame(step);
            };
            requestAnimationFrame(step);
          }, delay);
        }
      },
      { threshold: 0.3 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [target, delay]);

  const formatted = count.toLocaleString("es-EC");

  return (
    <div ref={ref} className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/10">
      <div className="text-3xl font-bold text-brand-gold">
        {formatted}{suffix}
      </div>
      <div className="text-blue-200 text-xs mt-1">{label}</div>
    </div>
  );
}
