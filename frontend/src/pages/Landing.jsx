import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
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
  { target: 25, suffix: "", label: "Carreras analizadas" },
  { target: 334, suffix: "", label: "Asignaturas analizadas" },
  { target: 740, suffix: "+", label: "Cursos en el LMS" },
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
    desc: "Convierte la analítica en acción: fichas de estudiantes, dashboards ejecutivos, colas de trabajo, tutorías, recomendaciones automáticas y derivación a Bienestar.",
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
    desc: "9 categorías de recomendación priorizadas con acción, motivo, medio y destinatario. Exportación Excel configurable." },
  { phase: "Fase 5", title: "Intervenciones inteligentes y ciclo cerrado", status: "completed",
    desc: "Registro con snapshots, medición de impacto antes/después, feedback loop ML y derivación a Bienestar Estudiantil." },
  { phase: "Fase 6", title: "Integración LMS completa", status: "upcoming",
    desc: "APIs de Moodle/Canvas, actualización en tiempo real, notificaciones automatizadas y trazabilidad institucional." },
];

const NIVELES = [
  { level: "Estudiante", emoji: "\uD83E\uDDD1\u200D\uD83C\uDF93", desc: "Accesos, tareas, calificaciones, historial, predicciones ML" },
  { level: "Asignatura", emoji: "\uD83D\uDCDA", desc: "Promedios, aprobación, repitencia, materias críticas" },
  { level: "Docente", emoji: "\uD83D\uDC68\u200D\uD83C\uDFEB", desc: "Carga académica, efectividad, seguimiento y concentración de riesgo" },
  { level: "Administrativo", emoji: "\uD83C\uDFDB\uFE0F", desc: "Matrícula, terceras matrículas, reportes ejecutivos, prácticas" },
  { level: "Intervención", emoji: "\uD83E\uDD1D", desc: "Acciones institucionales, colas de trabajo, seguimiento e impacto" },
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
    desc: "Migración a FastAPI + React + PostgreSQL. Pipeline ETL automatizado, 125+ endpoints REST, modelos predictivos por carrera, XAI, recomendaciones automáticas, ciclo cerrado de intervención, reportes ejecutivos, seguimiento docente y soporte multi-institución.",
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

const PLANS_INST = [
  {
    name: "Esencial",
    desc: "Hasta 1,000 estudiantes",
    priceAnn: "4,800",
    priceFirstYear: "3,840",
    priceSem: "2,400",
    features: [
      { text: "Dashboard de riesgo en tiempo real", ok: true },
      { text: "Alertas académicas configurables", ok: true },
      { text: "Fichas estudiantiles completas", ok: true },
      { text: "Analítica por asignatura y docente", ok: true },
      { text: "Exportaciones Excel/PDF", ok: true },
      { text: "5 usuarios · Soporte email", ok: true },
      { text: "Predicciones ML", ok: false },
      { text: "Simulaciones What-If", ok: false },
    ],
    cta: "Agendar demostración",
    featured: false,
  },
  {
    name: "Profesional",
    desc: "Más de 1,000 estudiantes · IA predictiva",
    priceAnn: "7,200",
    priceFirstYear: "5,760",
    priceSem: "3,600",
    features: [
      { text: "Todo del plan Esencial", ok: true },
      { text: "Predicciones ML con 87%+ precisión", ok: true },
      { text: "Explicabilidad del riesgo (XAI)", ok: true },
      { text: "Simulaciones What-If y contrafactuales", ok: true },
      { text: "Recomendaciones automáticas", ok: true },
      { text: "Gestión de intervenciones + impacto", ok: true },
      { text: "10 usuarios · Soporte email + chat", ok: true },
    ],
    cta: "Agendar demostración",
    featured: true,
  },
];

const PLANS_UNI = [
  {
    name: "Profesional",
    desc: "Hasta 2,000 estudiantes",
    priceAnn: "12,000",
    priceFirstYear: "9,600",
    priceSem: "6,000",
    features: [
      { text: "Dashboard de riesgo en tiempo real", ok: true },
      { text: "Alertas académicas configurables", ok: true },
      { text: "Predicciones ML con 87%+ precisión", ok: true },
      { text: "Explicabilidad del riesgo (XAI)", ok: true },
      { text: "Simulaciones What-If y contrafactuales", ok: true },
      { text: "Recomendaciones automáticas", ok: true },
      { text: "Gestión de intervenciones + impacto", ok: true },
      { text: "Fichas estudiantiles completas", ok: true },
      { text: "10 usuarios · Soporte email + chat", ok: true },
    ],
    cta: "Agendar demostración",
    featured: false,
  },
  {
    name: "Enterprise",
    desc: "De 2,001 a 10,000 estudiantes",
    priceAnn: "24,000",
    priceFirstYear: "19,200",
    priceSem: "12,000",
    features: [
      { text: "Todo del plan Profesional", ok: true },
      { text: "Tracking avanzado de docentes", ok: true },
      { text: "Comparativa multi-periodo", ok: true },
      { text: "API de integración REST", ok: true },
      { text: "Usuarios ilimitados", ok: true },
      { text: "Soporte prioritario + chat", ok: true },
      { text: "SLA 99.5% disponibilidad", ok: true },
    ],
    cta: "Contactar Ventas",
    featured: true,
  },
  {
    name: "Enterprise+",
    desc: "Más de 10,000 estudiantes · Instancia dedicada",
    priceAnn: "48,000",
    priceFirstYear: "38,400",
    priceSem: "24,000",
    features: [
      { text: "Todo del plan Enterprise", ok: true },
      { text: "Instancia dedicada", ok: true },
      { text: "Personalización de modelos ML", ok: true },
      { text: "Integración LMS avanzada", ok: true },
      { text: "Consultoría de retención", ok: true },
      { text: "Soporte dedicado 24/7", ok: true },
      { text: "SLA 99.9% disponibilidad", ok: true },
    ],
    cta: "Contactar Ventas",
    featured: false,
  },
];

/* ── Beneficios para decisores ────────────────────────── */

const BENEFITS = [
  {
    title: "Reduce la deserción",
    desc: "Identifica estudiantes en riesgo antes de que abandonen. Intervenciones oportunas basadas en evidencia, no en intuición.",
    icon: (
      <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.94" />
      </svg>
    ),
  },
  {
    title: "Cumple con el CACES",
    desc: "Genera evidencia auditable de seguimiento, retención y bienestar estudiantil para los 32 indicadores del modelo MEEUEP 2023.",
    icon: (
      <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
  },
  {
    title: "Ahorra recursos",
    desc: "Cada estudiante retenido es matrícula recuperada. La inversión se paga reteniendo entre 3 y 5 estudiantes por año.",
    icon: (
      <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    title: "Decisiones con evidencia",
    desc: "Dashboards ejecutivos, reportes de riesgo por carrera y trazabilidad completa de intervenciones. Información clara para el consejo directivo.",
    icon: (
      <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
      </svg>
    ),
  },
];

const STEPS = [
  { step: "1", title: "Conecta tus datos", desc: "Importamos los datos de tu Moodle o LMS sin instalar nada. Solo necesitamos acceso de lectura." },
  { step: "2", title: "La IA analiza y predice", desc: "Nuestros modelos identifican estudiantes en riesgo con 87%+ de precisión y explican por qué." },
  { step: "3", title: "Tu equipo actúa a tiempo", desc: "Reciben alertas, recomendaciones y herramientas para intervenir antes de que sea tarde." },
];

const COMPLIANCE = [
  { norm: "LOES", desc: "Art. 5, 71, 86: derecho a educación de calidad, bienestar estudiantil y seguimiento académico." },
  { norm: "CACES / MEEUEP", desc: "Indicadores de retención, seguimiento a estudiantes y bienestar dentro del modelo de acreditación 2023." },
  { norm: "CES", desc: "Reglamento de Régimen Académico: seguimiento de aprobación, repitencia y terceras matrículas." },
  { norm: "LOPD Ecuador", desc: "Protección de datos personales: cifrado TLS 1.3, AES-256, control de acceso RBAC." },
];

const FAQS = [
  { q: "¿Cuánto toma la implementación?", a: "El proceso completo toma entre 2 y 4 semanas, dependiendo de la disponibilidad de datos históricos y la complejidad de integración con tu LMS. Incluye configuración, calibración de modelos ML, capacitación del equipo y acompañamiento en go-live." },
  { q: "¿Funciona con mi Moodle actual?", a: "Sí. Yachay Deep se integra con cualquier instalación de Moodle mediante captura automatizada de datos de actividad. No requiere plugins adicionales ni cambios en tu Moodle. También soportamos importación por Excel/CSV para otros sistemas." },
  { q: "¿Qué precisión tienen las predicciones?", a: "Nuestros modelos alcanzan un 87%+ de precisión en predicción de aprobación/deserción, entrenados con datos reales de tu institución. La precisión mejora conforme acumulamos más datos históricos." },
  { q: "¿Puedo probar antes de comprar?", a: "Sí. Agendamos una demostración personalizada y, si hay interés, activamos un piloto gratuito de 30 días con el plan Profesional usando tus propios datos, incluyendo onboarding completo y soporte prioritario. Sin compromiso de compra." },
  { q: "¿Mis datos están seguros?", a: "Absolutamente. Usamos cifrado TLS 1.3 en tránsito y AES-256 en reposo. Autenticación con cookies HttpOnly, control de acceso por roles (RBAC), y cumplimiento con la Ley Orgánica de Protección de Datos Personales de Ecuador." },
  { q: "¿Ayuda con la acreditación del CACES?", a: "Sí. Yachay Deep genera evidencia auditable de seguimiento académico, retención estudiantil y bienestar que se alinea con los indicadores del modelo de evaluación MEEUEP 2023 del CACES. Los reportes ejecutivos y la trazabilidad de intervenciones facilitan la preparación para evaluaciones externas." },
  { q: "¿Cómo se calcula el precio?", a: "El plan depende del tipo de institución y la cantidad de estudiantes. Para institutos tecnológicos: Esencial (hasta 1,000 estudiantes, $4,800/año) o Profesional (más de 1,000, $7,200/año). Para universidades: Profesional (hasta 2,000 estudiantes, $12,000/año), Enterprise (2,001 a 10,000, $24,000/año) o Enterprise+ (más de 10,000, $48,000/año con instancia dedicada). Todos los planes incluyen un 20% de descuento en el primer año como Early Adopter." },
];

export default function Landing() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [playingIdx, setPlayingIdx] = useState(null);
  const [segment, setSegment] = useState("uni");
  const [period, setPeriod] = useState("firstYear");
  const [openFaq, setOpenFaq] = useState(null);
  const [showTech, setShowTech] = useState(false);
  const plans = segment === "inst" ? PLANS_INST : PLANS_UNI;

  const ctaLabel = user ? "Ir al Dashboard" : "Iniciar sesión";
  const ctaTarget = user ? "/dashboard" : "/login";

  return (
    <div className="min-h-screen bg-white">
      {/* ── Navbar ── */}
      <nav className="fixed top-0 w-full bg-white/90 backdrop-blur-sm border-b border-gray-100 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <YachayLogo variant="light" className="h-10 sm:h-11 lg:h-12 w-auto" />
          </div>
          <div className="flex items-center gap-3">
            <a href="#benefits" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Beneficios</a>
            <a href="#how" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Cómo funciona</a>
            <a href="#pricing" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Planes</a>
            <a href="#compliance" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Normativa</a>
            <a href="#contact" className="hidden sm:inline text-sm text-gray-600 hover:text-brand transition-colors px-3 py-1">Contacto</a>
            <a
              href="#contact"
              className="bg-brand-gold text-brand-dark font-semibold text-sm px-5 py-2 rounded-lg hover:bg-brand-gold-light transition-colors"
            >
              Agendar demo
            </a>
          </div>
        </div>
      </nav>

      {/* ── Hero: dolor + solución ── */}
      <section className="pt-32 pb-20 bg-gradient-to-br from-brand via-brand-dark to-brand">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <div className="flex justify-center mb-8">
            <YachayLogo
              variant="dark"
              className="block w-[min(70vw,28rem)] sm:w-[min(60vw,36rem)] lg:w-[min(50vw,44rem)] h-auto drop-shadow-2xl"
            />
          </div>
          <h1 className="text-3xl md:text-5xl font-bold text-white mb-4 leading-tight">
            ¿Cuántos estudiantes pierdes<br />cada semestre sin saberlo?
          </h1>
          <p className="text-brand-ice text-lg md:text-xl max-w-3xl mx-auto mb-3">
            En Ecuador, 1 de cada 5 universitarios abandona su carrera.
          </p>
          <p className="text-blue-200 max-w-2xl mx-auto mb-10 text-sm leading-relaxed">
            Yachay Deep identifica estudiantes en riesgo antes de que deserten,
            explica por qué están en peligro y le da a tu equipo las herramientas
            para intervenir a tiempo. Con inteligencia artificial y evidencia auditable.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-14">
            <a
              href="#contact"
              className="bg-brand-gold text-brand-dark font-semibold px-8 py-3 rounded-xl text-base hover:bg-brand-gold-light transition-colors shadow-lg"
            >
              Agendar demostración gratuita
            </a>
            <a
              href="#benefits"
              className="border-2 border-white/30 text-white font-semibold px-8 py-3 rounded-xl text-base hover:bg-white/10 transition-colors"
            >
              Ver beneficios
            </a>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
            {STATS.map((s, i) => (
              <AnimatedStat key={i} target={s.target} suffix={s.suffix} label={s.label} delay={i * 150} />
            ))}
          </div>
        </div>
      </section>

      {/* ── El Problema ── */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="Un problema que cuesta millones"
            subtitle="La deserción estudiantil no solo afecta a los estudiantes. Impacta los ingresos, la acreditación y la reputación de tu institución."
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10">
            <div className="bg-white rounded-2xl p-6 border border-red-100 text-center">
              <div className="text-4xl font-extrabold text-red-500 mb-2">20.4%</div>
              <div className="text-sm font-semibold text-gray-800 mb-1">Deserción promedio</div>
              <p className="text-xs text-gray-500">Tasa de deserción universitaria en Ecuador según Senescyt (2023). En privadas llega al 27.9%.</p>
            </div>
            <div className="bg-white rounded-2xl p-6 border border-red-100 text-center">
              <div className="text-4xl font-extrabold text-red-500 mb-2">$1,500+</div>
              <div className="text-sm font-semibold text-gray-800 mb-1">Perdidos por desertor</div>
              <p className="text-xs text-gray-500">Cada estudiante que abandona representa matrícula perdida, inversión no recuperada y menor ingreso recurrente.</p>
            </div>
            <div className="bg-white rounded-2xl p-6 border border-red-100 text-center">
              <div className="text-4xl font-extrabold text-red-500 mb-2">CACES</div>
              <div className="text-sm font-semibold text-gray-800 mb-1">Exige evidencia</div>
              <p className="text-xs text-gray-500">El modelo MEEUEP 2023 evalúa retención, seguimiento y bienestar estudiantil. Sin datos, la acreditación está en riesgo.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Beneficios para el decisor ── */}
      <section id="benefits" className="py-20">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="Qué gana tu institución con Yachay Deep"
            subtitle="No es solo tecnología. Es la herramienta que necesitas para retener estudiantes, cumplir normativas y tomar mejores decisiones."
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-12">
            {BENEFITS.map((b, i) => (
              <div key={i} className="flex gap-4 bg-white border border-gray-200 rounded-2xl p-6 hover:shadow-lg transition-shadow">
                <div className="w-14 h-14 bg-gradient-to-br from-brand to-brand-light rounded-xl flex items-center justify-center text-white flex-shrink-0">
                  {b.icon}
                </div>
                <div>
                  <h3 className="font-bold text-gray-900 text-lg mb-1">{b.title}</h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{b.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Cómo funciona (3 pasos) ── */}
      <section id="how" className="py-20 bg-gradient-to-br from-brand-dark via-brand to-brand-light">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold text-white">Cómo funciona</h2>
            <p className="text-blue-200 mt-3 max-w-xl mx-auto">Implementación en 2-4 semanas. Sin instalar software en tu Moodle.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {STEPS.map((s, i) => (
              <div key={i} className="bg-white/10 backdrop-blur-sm border border-white/15 rounded-2xl p-6 text-center">
                <div className="w-12 h-12 bg-brand-gold text-brand-dark rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                  {s.step}
                </div>
                <h3 className="text-white font-bold text-base mb-2">{s.title}</h3>
                <p className="text-blue-200 text-sm leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
          <div className="text-center mt-10">
            <a href="#contact" className="bg-brand-gold text-brand-dark font-semibold px-8 py-3 rounded-xl text-base hover:bg-brand-gold-light transition-colors shadow-lg inline-block">
              Agendar demostración gratuita
            </a>
          </div>
        </div>
      </section>

      {/* ── Enfoque multinivel (resumido) ── */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="Análisis en cinco niveles simultáneos"
            subtitle="El abandono es multicausal. Yachay Deep cruza datos de estudiantes, asignaturas, docentes, administración e intervenciones."
          />
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-10">
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

      {/* ── Cumplimiento normativo ── */}
      <section id="compliance" className="py-16 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4">
          <SectionHeader
            title="Alineado con la normativa ecuatoriana"
            subtitle="Yachay Deep te ayuda a cumplir con los requerimientos de seguimiento, retención y protección de datos."
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-10">
            {COMPLIANCE.map((c, i) => (
              <div key={i} className="flex gap-4 items-start bg-white border border-gray-200 rounded-xl p-5">
                <div className="flex-shrink-0 w-10 h-10 bg-brand text-white rounded-lg flex items-center justify-center font-bold text-xs">
                  {c.norm.length > 4 ? c.norm.slice(0, 4) : c.norm}
                </div>
                <div>
                  <div className="font-semibold text-gray-900 text-sm">{c.norm}</div>
                  <p className="text-gray-500 text-xs mt-0.5 leading-relaxed">{c.desc}</p>
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
              Precios diferenciados para institutos tecnológicos y universidades. Sin costos ocultos.
            </p>

            {/* Segment toggle */}
            <div className="flex items-center justify-center gap-1 mt-6 bg-gray-100 rounded-xl p-1 max-w-md mx-auto">
              <button
                onClick={() => setSegment("inst")}
                className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                  segment === "inst"
                    ? "bg-white text-brand shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                Institutos Tecnológicos
              </button>
              <button
                onClick={() => setSegment("uni")}
                className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                  segment === "uni"
                    ? "bg-white text-brand shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                Universidades
              </button>
            </div>

            {/* Period toggle */}
            <div className="flex items-center justify-center gap-2 mt-4">
              {[
                { key: "firstYear", label: "Primer año", badge: "20% dto." },
                { key: "annual", label: "Anual" },
                { key: "semester", label: "Semestral" },
              ].map((p) => (
                <button
                  key={p.key}
                  onClick={() => setPeriod(p.key)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    period === p.key
                      ? "bg-brand text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {p.label}
                  {p.badge && period === p.key && (
                    <span className="ml-1.5 text-xs bg-white/20 px-1.5 py-0.5 rounded">{p.badge}</span>
                  )}
                </button>
              ))}
            </div>

            {period === "firstYear" && (
              <p className="text-xs text-green-600 mt-2 font-medium">
                Promoción Early Adopter: 20% de descuento en el primer año de contratación
              </p>
            )}
          </div>

          {/* ROI banner */}
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-4 mb-8 text-center">
            <p className="text-sm text-green-800 font-medium">
              {segment === "inst"
                ? "Retener 4 estudiantes al año cubre la inversión del plan Profesional"
                : "Una universidad con 5,000 estudiantes recupera la inversión reteniendo menos del 1% de su matrícula"}
            </p>
          </div>

          {/* Cards */}
          <div className={`grid grid-cols-1 gap-6 ${plans.length === 3 ? "md:grid-cols-3" : "md:grid-cols-2 max-w-4xl mx-auto"}`}>
            {plans.map((plan, i) => {
              const price = period === "firstYear" ? plan.priceFirstYear
                : period === "annual" ? plan.priceAnn
                : plan.priceSem;
              const periodSuffix = period === "semester" ? "/semestre" : "/año";

              return (
                <div
                  key={plan.name}
                  className={`relative rounded-2xl p-8 transition-all duration-200 hover:-translate-y-1 ${
                    plan.featured
                      ? "bg-white border-2 border-brand shadow-xl shadow-brand/10 hover:shadow-2xl"
                      : "bg-white border border-gray-200 hover:shadow-lg"
                  }`}
                >
                  {plan.featured && (
                    <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-brand-gold text-brand-dark text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap">
                      Más Popular
                    </div>
                  )}
                  <div className="mb-6">
                    <h3 className="text-xl font-bold text-gray-900">{plan.name}</h3>
                    <p className="text-sm text-gray-500 mt-1">{plan.desc}</p>
                  </div>
                  <div className="mb-1">
                    <span className="text-4xl font-extrabold text-gray-900">${price}</span>
                    <span className="text-gray-500 text-sm ml-1">{periodSuffix}</span>
                  </div>
                  {period === "firstYear" && (
                    <p className="text-xs text-green-600 mb-4 font-medium">
                      Precio regular: ${plan.priceAnn}/año
                    </p>
                  )}
                  {period !== "firstYear" && <div className="mb-4" />}
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
              );
            })}
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
              Piloto gratuito 30 días
            </span>
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

      {/* ── Para equipos técnicos (colapsable) ── */}
      <section className="py-16 bg-white">
        <div className="max-w-6xl mx-auto px-4">
          <button
            onClick={() => setShowTech(!showTech)}
            className="w-full flex items-center justify-between bg-gray-50 rounded-2xl p-6 hover:bg-gray-100 transition-colors"
          >
            <div>
              <h2 className="text-xl font-bold text-gray-900 text-left">Para equipos técnicos</h2>
              <p className="text-sm text-gray-500 mt-1 text-left">Arquitectura, fases de desarrollo, stack tecnológico y evolución del sistema.</p>
            </div>
            <svg
              className={`w-6 h-6 text-brand flex-shrink-0 transition-transform ${showTech ? "rotate-180" : ""}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>

          {showTech && (
            <div className="mt-8 space-y-16">
              {/* 3 Capas */}
              <div>
                <SectionHeader
                  title="Tres capas integradas"
                  subtitle="Learning Analytics + Early Warning + Decision Support en un único sistema."
                />
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
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
              </div>

              {/* Fases */}
              <div>
                <SectionHeader
                  title="Seis fases de madurez analítica"
                  subtitle="Cinco fases completadas y una sexta en desarrollo."
                />
                <div className="mt-8 space-y-4">
                  {PHASES.map((p, i) => {
                    const isCompleted = p.status === "completed";
                    return (
                      <div key={i} className={`flex gap-4 items-start bg-white border rounded-xl p-5 ${
                        isCompleted ? "border-green-200" : "border-gray-300 border-dashed"
                      }`}>
                        <div className={`flex-shrink-0 w-10 h-10 text-white rounded-full flex items-center justify-center font-bold text-sm ${
                          isCompleted ? "bg-green-600" : "bg-gray-400"
                        }`}>
                          {i + 1}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-1">
                            <span className="font-bold text-gray-900">{p.title}</span>
                            {isCompleted ? (
                              <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">Completada</span>
                            ) : (
                              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full font-medium">En desarrollo</span>
                            )}
                          </div>
                          <p className="text-gray-500 text-sm leading-relaxed">{p.desc}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Evolución */}
              <div>
                <SectionHeader
                  title="De Excel a plataforma web"
                  subtitle="Yachay Deep nació como un sistema en Excel con Power Query y macros VBA. Hoy es una plataforma web completa."
                />
                <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
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

              {/* Tech stack */}
              <div>
                <SectionHeader title="Stack tecnológico" />
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mt-8">
                  {TECH.map((t, i) => (
                    <div key={i} className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                      <div className="font-semibold text-gray-800 text-sm mb-1">{t.cat}</div>
                      <div className="text-xs text-gray-500">{t.items}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
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
            {" "}| Soluciones de inteligencia académica para educación superior
          </div>
          <button
            onClick={() => navigate(ctaTarget)}
            className="text-brand-gold text-sm font-medium hover:text-brand-gold-light transition-colors"
          >
            {ctaLabel} &rarr;
          </button>
        </div>
      </footer>
    </div>
  );
}

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
                