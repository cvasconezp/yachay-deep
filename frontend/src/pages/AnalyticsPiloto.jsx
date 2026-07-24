import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Dashboard, configureAnalytics } from "@yachaydeep-yd/dashboard";

/**
 * PILOTO — Track C de la integración con Yachay Deep Analytics.
 *
 * Reemplaza (a modo de prueba) la pestaña "Vista General" del Análisis Institucional
 * por el tablero embebido del motor. Ruta oculta: /admin/analytics-piloto.
 *
 * Deliberadamente aislado: convive con ResumenDatos para comparar lado a lado. Si el
 * backend de analytics no tiene la BD de Core conectada, no muestra datos — no rompe nada.
 *
 * Config por variables de entorno (Vite), NUNCA quemadas en el bundle:
 *   VITE_ANALYTICS_API → URL del backend de analytics (Railway)
 *   VITE_ANALYTICS_KEY → API key de rol acotado (viewer). NUNCA una key admin aquí.
 *
 * NOTA DE BUILD (verificado): como todo el render del <Dashboard> está detrás de
 * `if (apiBase)`, si se compila SIN VITE_ANALYTICS_API definida, Vite hace dead-code
 * elimination y NO empaqueta echarts ni el paquete (el chunk queda en ~30KB). Es
 * correcto: en un despliegue con la variable puesta, echarts entra en este chunk lazy
 * (~1.1MB, cargado solo al visitar esta ruta) y los gráficos renderizan. No es un fallo
 * de peers ni del paquete.
 */

const qc = new QueryClient();

// Las 8 métricas de Vista General, ya declaradas en el motor (apps/core.py).
// filtrosGlobales: los dos desplegables (Período, Carrera) los pinta el propio Dashboard
// y filtran los 8 paneles a la vez (cross-filtering).
const VISTA_GENERAL_SPEC = {
  id: "core-vista-general",
  titulo: "Análisis Institucional — Vista General",
  filtrosGlobales: ["periodo", "carrera"],
  paneles: [
    { id: "est", metric: "total_estudiantes", titulo: "Total estudiantes", chartHint: "kpi", size: "sm" },
    { id: "doc", metric: "total_docentes", titulo: "Docentes", chartHint: "kpi", size: "sm" },
    { id: "car", metric: "total_carreras", titulo: "Carreras", chartHint: "kpi", size: "sm" },
    { id: "mat", metric: "total_matriculas", titulo: "Matrículas", chartHint: "kpi", size: "sm" },
    { id: "prom", metric: "promedio_calificaciones", titulo: "Promedio de calificaciones", chartHint: "kpi", size: "sm" },
    { id: "asig", metric: "total_asignaturas", titulo: "Asignaturas", chartHint: "kpi", size: "sm" },
    { id: "sec", metric: "total_secciones", titulo: "Secciones", chartHint: "kpi", size: "sm" },
    { id: "aul", metric: "total_aulas_virtuales", titulo: "Aulas virtuales", chartHint: "kpi", size: "sm" },
    // Panel que hoy NO existe como tarjeta: distribución que cross-filtra al hacer clic
    { id: "porcarrera", metric: "total_estudiantes", titulo: "Estudiantes por carrera", dimensions: ["carrera"], chartHint: "bar_h", size: "lg" },
  ],
};

export default function AnalyticsPiloto() {
  const [configurado, setConfigurado] = useState(false);

  const apiBase = import.meta.env.VITE_ANALYTICS_API;
  const apiKey = import.meta.env.VITE_ANALYTICS_KEY;

  useEffect(() => {
    if (apiBase) {
      configureAnalytics({ apiBase, apiKey });
      setConfigurado(true);
    }
  }, [apiBase, apiKey]);

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Analytics (piloto)</h1>
        <p className="text-sm text-gray-500">
          Prueba del motor de tableros embebido. Convive con el Análisis Institucional
          actual para comparar los números lado a lado.
        </p>
      </div>

      {!apiBase ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
          <strong>Falta configurar el backend de analytics.</strong>
          <p className="mt-2">
            Define en el entorno de la app (Vercel){" "}
            <code className="bg-amber-100 px-1 rounded">VITE_ANALYTICS_API</code> (URL del
            backend en Railway) y{" "}
            <code className="bg-amber-100 px-1 rounded">VITE_ANALYTICS_KEY</code> (API key
            de rol <em>viewer</em>, nunca admin). En Railway, conecta{" "}
            <code className="bg-amber-100 px-1 rounded">ANALYTICS_DB_URL</code> a la BD de Core.
          </p>
          <p className="mt-2 text-amber-700">
            Caveat del período: <code>students.periodo</code> usa "2026-1" y{" "}
            <code>grades/enrollments</code> usan "P68". Compara primero sin filtro de período.
          </p>
        </div>
      ) : (
        <div style={{ ["--yd-accent"]: "#E8A838" }}>
          {configurado && (
            <QueryClientProvider client={qc}>
              <Dashboard spec={VISTA_GENERAL_SPEC} attributionTheme="light" />
            </QueryClientProvider>
          )}
        </div>
      )}
    </div>
  );
}
