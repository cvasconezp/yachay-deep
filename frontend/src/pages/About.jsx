import { useState } from "react";
import { YachayLogo } from "../components/YachayLogo";

const PODCASTS = [
  {
    title: "El Excel que frena el abandono universitario",
    description:
      "El origen de Yachay Deep: como un sistema construido en Excel con macros VBA evolucionó hacia una plataforma web de inteligencia académica preventiva.",
    file: "/El_Excel_que_frena_el_abandono_universitario.m4a",
  },
  {
    title: "IA para evitar el abandono universitario",
    description:
      "Cómo la inteligencia artificial y la analítica del aprendizaje pueden anticipar el riesgo de deserción y activar intervenciones oportunas en educación superior.",
    file: "/IA_para_evitar_el_abandono_universitario.m4a",
  },
  {
    title: "Yachay Deep: Un framework multinivel de inteligencia académica para la retención estudiantil",
    description:
      "Una visión general de Yachay Deep como sistema de soporte a la decisión con alerta temprana impulsado por analítica del aprendizaje: su arquitectura multinivel, modelado predictivo, IA explicable y trazabilidad de intervenciones de ciclo cerrado para la retención estudiantil en educación superior.",
    file: "/Yachay Deep A Multilevel Intelligence Framework for Student Retention.m4a",
  },
];

const FRAMEWORK_PHASES = [
  {
    phase: "Fase 1",
    title: "Analítica descriptiva y diagnóstica",
    status: "completed",
    items: [
      "Monitoreo e indicadores de compromiso",
      "Dashboards de riesgo por estudiante, asignatura y docente",
      "Clasificación de riesgo multinivel (Alto / Medio / Bajo)",
      "Fichas individuales con historial académico",
      "Registro y seguimiento de intervenciones",
      "Listas de tutoría por asignatura",
      "Resumen de datos y exportación Excel",
    ],
  },
  {
    phase: "Fase 2",
    title: "Analítica predictiva",
    status: "completed",
    items: [
      "Modelos de predicción de abandono y reprobación",
      "Logistic Regression y Random Forest por carrera",
      "Entrenamiento con datos históricos consolidados (P60-P67)",
      "Predicción batch y auto-reentrenamiento",
    ],
  },
  {
    phase: "Fase 3",
    title: "Explicación del riesgo (XAI)",
    status: "completed",
    items: [
      "Contribuciones por feature (coeficientes / importancias)",
      "Comparación con media de carrera",
      "Factores que incrementan o reducen el riesgo del estudiante",
    ],
  },
  {
    phase: "Fase 4",
    title: "Recomendaciones automáticas",
    status: "completed",
    items: [
      "Motor de recomendaciones basado en reglas y XAI",
      "Sugerencias de intervención priorizadas (urgente / importante / sugerida)",
      "Derivación a Bienestar Estudiantil con notificación por correo",
    ],
  },
  {
    phase: "Fase 5",
    title: "Integración LMS completa",
    status: "upcoming",
    items: [
      "APIs de Moodle/Canvas",
      "Actualización en tiempo real",
      "Trazabilidad institucional completa",
    ],
  },
];

const CAPAS = [
  { name: "Learning Analytics", desc: "Análisis de comportamiento educativo y compromiso académico" },
  { name: "Early Warning System", desc: "Identificación de señales de riesgo antes del fracaso" },
  { name: "Decision Support System", desc: "Soporte para la toma de decisiones pedagógicas e institucionales" },
];

export default function About() {
  const [playingIdx, setPlayingIdx] = useState(null);

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-10 flex items-center gap-5">
        <YachayLogo size={80} />
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Sobre Yachay Deep</h1>
          <p className="text-gray-500 text-sm">
            Learning Analytics-Driven Early Warning Decision Support System for Student Retention
          </p>
        </div>
      </div>

      {/* Resumen ejecutivo */}
      <Section title="Resumen ejecutivo">
        <p className="text-gray-700 leading-relaxed mb-4">
          <strong>Yachay Deep</strong> es un sistema de inteligencia académica preventiva orientado a la permanencia
          estudiantil en educación superior, especialmente en entornos virtuales o híbridos. Su propósito es
          identificar tempranamente estudiantes en riesgo, comprender los factores que explican dicho riesgo y
          apoyar decisiones pedagógicas e institucionales oportunas.
        </p>
        <p className="text-gray-700 leading-relaxed mb-4">
          Desde una formulación científica rigurosa, Yachay Deep se define como un{" "}
          <em>Learning Analytics-Driven Early Warning Decision Support System</em>: un sistema en el que los
          datos educativos son recopilados y procesados, se analizan mediante Learning Analytics, se transforman en
          alertas tempranas propias de un Early Warning System, y finalmente se convierten en acciones concretas
          mediante un Decision Support System.
        </p>
        <p className="text-gray-600 leading-relaxed text-sm">
          Su valor está precisamente en la integración de las tres capas, lo que lo distingue de soluciones que
          solo abordan una dimensión del problema.
        </p>
      </Section>

      {/* Tres capas */}
      <Section title="Arquitectura conceptual">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          {CAPAS.map((c, i) => (
            <div key={i} className="bg-gradient-to-br from-brand to-brand-light rounded-xl p-5 text-white">
              <div className="text-xs font-semibold uppercase tracking-wider text-brand-ice mb-2">Capa {i + 1}</div>
              <div className="font-bold text-lg mb-2">{c.name}</div>
              <div className="text-blue-100 text-sm leading-relaxed">{c.desc}</div>
            </div>
          ))}
        </div>
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600 text-center">
          <span className="font-mono text-xs">
            Datos educativos &rarr; Learning Analytics &rarr; Modelo de riesgo &rarr; Early Warning System &rarr; Decision Support System
          </span>
        </div>
      </Section>

      {/* Enfoque multinivel */}
      <Section title="Enfoque multinivel del riesgo">
        <p className="text-gray-600 text-sm mb-4">
          El riesgo estudiantil no se explica solo por variables individuales. Yachay Deep analiza simultáneamente
          múltiples niveles:
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { level: "Estudiante", icon: "person", desc: "Comportamiento individual, accesos, tareas, calificaciones" },
            { level: "Asignatura", icon: "book", desc: "Promedios, aprobación, repitencia, materias críticas" },
            { level: "Docente", icon: "school", desc: "Carga académica, gestión de cursos, concentración de riesgo" },
            { level: "Administrativo", icon: "receipt", desc: "Matrícula, deuda, bloqueos financieros" },
            { level: "Intervención", icon: "support", desc: "Acciones institucionales, seguimiento, impacto" },
          ].map((n, i) => (
            <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 text-center hover:shadow-md transition-shadow">
              <div className="text-2xl mb-2">
                {["🧑‍🎓", "📚", "👨‍🏫", "🏛️", "🤝"][i]}
              </div>
              <div className="font-semibold text-gray-800 text-sm">{n.level}</div>
              <div className="text-xs text-gray-500 mt-1 leading-relaxed">{n.desc}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* Hoja de ruta */}
      <Section title="Hoja de ruta de madurez analítica">
        <div className="space-y-3">
          {FRAMEWORK_PHASES.map((p, i) => (
            <div
              key={i}
              className={`rounded-xl border p-4 ${
                p.status === "completed"
                  ? "border-green-300 bg-green-50/50"
                  : p.status === "active"
                  ? "border-blue-300 bg-blue-50/50"
                  : "border-gray-200 bg-gray-50/50"
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <span
                  className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                    p.status === "completed"
                      ? "bg-green-600 text-white"
                      : p.status === "active"
                      ? "bg-brand-gold text-brand-dark"
                      : "bg-gray-200 text-gray-500"
                  }`}
                >
                  {p.phase}
                </span>
                <span className="font-semibold text-gray-800">{p.title}</span>
                {p.status === "completed" && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium ml-auto">
                    Completada
                  </span>
                )}
                {p.status === "active" && (
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium ml-auto">
                    En desarrollo
                  </span>
                )}
              </div>
              <ul className="ml-10 text-sm text-gray-600 space-y-1">
                {p.items.map((item, j) => (
                  <li key={j} className="flex items-start gap-2">
                    <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      p.status === "completed" ? "bg-green-500"
                      : p.status === "active" ? "bg-blue-400"
                      : "bg-gray-300"
                    }`} />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      {/* Principios */}
      <Section title="Principios rectores">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            ["Prevención temprana", "No esperar al fracaso. Detectar señales previas de riesgo."],
            ["Integración humano-máquina", "La analítica apoya, orienta y prioriza la intervención humana."],
            ["Decisiones basadas en evidencia", "Datos dispersos transformados en evidencia accionable."],
            ["Ciclo cerrado", "Detección, alerta, intervención, seguimiento y evaluación."],
            ["Explicabilidad", "El riesgo debe poder explicarse con claridad a docentes y gestores."],
            ["Escalabilidad", "Sirve para investigación, tesis, software real y protección intelectual."],
          ].map(([title, desc], i) => (
            <div key={i} className="flex gap-3 bg-white border border-gray-200 rounded-lg p-4">
              <div className="w-8 h-8 bg-brand text-white rounded-lg flex items-center justify-center font-bold text-sm flex-shrink-0">
                {i + 1}
              </div>
              <div>
                <div className="font-semibold text-gray-800 text-sm">{title}</div>
                <div className="text-xs text-gray-500 mt-0.5">{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Podcasts */}
      <Section title="Podcasts">
        <p className="text-gray-500 text-sm mb-4">
          Episodios que explican el contexto, motivación y evolución de Yachay Deep.
        </p>
        <div className="space-y-4">
          {PODCASTS.map((pod, i) => (
            <div key={i} className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 bg-gradient-to-br from-brand to-brand-light rounded-xl flex items-center justify-center flex-shrink-0">
                  <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM8 11a4 4 0 0 0 8 0h2a6 6 0 0 1-5 5.91V20h3v2H8v-2h3v-3.09A6 6 0 0 1 6 11h2z"/>
                  </svg>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900">{pod.title}</h3>
                  <p className="text-sm text-gray-500 mt-1 leading-relaxed">{pod.description}</p>
                  <audio
                    controls
                    className="mt-3 w-full"
                    onPlay={() => setPlayingIdx(i)}
                    preload="none"
                  >
                    <source src={pod.file} type="audio/mp4" />
                    Su navegador no soporta el elemento de audio.
                  </audio>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Stack tecnológico */}
      <Section title="Stack tecnológico">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { cat: "Backend", items: "FastAPI, Python, SQLAlchemy, Pandas" },
            { cat: "Frontend", items: "React 18, Vite, Tailwind CSS" },
            { cat: "Base de datos", items: "PostgreSQL (prod), SQLite (dev)" },
            { cat: "Despliegue", items: "Railway, Vercel, GitHub Actions" },
          ].map((s, i) => (
            <div key={i} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <div className="font-semibold text-gray-800 text-sm mb-1">{s.cat}</div>
              <div className="text-xs text-gray-500">{s.items}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* Desarrollador */}
      <Section title="Desarrollador">
        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <div className="bg-gradient-to-r from-brand to-brand-light px-6 py-8">
            <div className="flex items-center gap-5">
              <div className="w-20 h-20 bg-white/20 rounded-full flex items-center justify-center text-3xl font-bold text-white border-2 border-white/30">
                CV
              </div>
              <div className="text-white">
                <h3 className="text-xl font-bold">Carlos Vasconez-Paredes</h3>
                <p className="text-blue-200 text-sm mt-1">
                  Docente | Gestor de Analítica del Aprendizaje | Investigador
                </p>
              </div>
            </div>
          </div>

          <div className="p-6">
            <p className="text-gray-700 text-sm leading-relaxed mb-5">
              Docente, gestor de Analítica del Aprendizaje e investigador en el campo de la innovación educativa,
              la analítica del aprendizaje y la transformación digital en educación superior. Su trabajo se centra
              en la integración de pedagogía, ciencia de datos y tecnologías emergentes para mejorar la permanencia
              y el éxito académico de los estudiantes.
            </p>
            <p className="text-gray-700 text-sm leading-relaxed mb-5">
              Creador de Yachay Deep, su experiencia combina docencia, coordinación académica, monitoreo de
              estudiantes en línea y desarrollo de soluciones basadas en datos para la gestión educativa. Sus
              intereses de investigación se enfocan en Learning Analytics, inteligencia artificial aplicada a la
              educación, sistemas de alerta temprana y modelos predictivos para la retención estudiantil.
            </p>

            {/* Links */}
            <div className="flex flex-wrap gap-3">
              <SocialLink
                href="https://www.linkedin.com/in/cvasconezp/"
                label="LinkedIn"
                color="bg-[#0A66C2]"
                icon={
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                  </svg>
                }
              />
              <SocialLink
                href="https://orcid.org/0000-0002-1574-346X"
                label="ORCID"
                color="bg-[#A6CE39]"
                icon={
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zM7.369 4.378c.525 0 .947.431.947.947s-.422.947-.947.947a.95.95 0 01-.947-.947c0-.525.422-.947.947-.947zm-.722 3.038h1.444v10.041H6.647V7.416zm3.562 0h3.9c3.712 0 5.344 2.653 5.344 5.025 0 2.578-2.016 5.025-5.325 5.025h-3.919V7.416zm1.444 1.303v7.444h2.297c3.272 0 4.022-2.484 4.022-3.722 0-1.847-1.188-3.722-3.931-3.722h-2.388z"/>
                  </svg>
                }
              />
              <SocialLink
                href="https://scholar.google.com/citations?user=w46QDacAAAAJ&hl=es"
                label="Google Académico"
                color="bg-[#4285F4]"
                icon={
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M5.242 13.769L0 9.5 12 0l12 9.5-5.242 4.269C17.548 11.249 14.978 9.5 12 9.5c-2.977 0-5.548 1.748-6.758 4.269zM12 10a7 7 0 100 14 7 7 0 000-14z"/>
                  </svg>
                }
              />
              <SocialLink
                href="mailto:cvasconezp@gmail.com"
                label="cvasconezp@gmail.com"
                color="bg-gray-700"
                icon={
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                  </svg>
                }
              />
            </div>
          </div>
        </div>
      </Section>

      {/* Footer */}
      <div className="text-center py-8 text-xs text-gray-400 border-t border-gray-200 mt-10">
        &copy; {new Date().getFullYear()} Carlos Vasconez-Paredes | PachaTech | Yachay Deep v1.0
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="mb-10">
      <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
        <span className="w-1 h-6 bg-brand rounded-full" />
        {title}
      </h2>
      {children}
    </section>
  );
}

function SocialLink({ href, label, color, icon }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-2 ${color} text-white text-sm font-medium px-4 py-2 rounded-lg hover:opacity-90 transition-opacity`}
    >
      {icon}
      {label}
    </a>
  );
}
