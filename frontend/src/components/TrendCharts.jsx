import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";

/* ── Power BI palette ── */
const PBI = {
  navy: "#1B2A4A", blue: "#2B5EA7", teal: "#0F9B8D",
  gold: "#F2C94C", coral: "#EB5757", purple: "#7B61FF",
  slate: "#64748B", card: "#FFFFFF", border: "#E2E8F0",
};

const tooltipStyle = { fontSize: 12, borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,.1)", background: "#fff" };
const axisProps = { axisLine: false, tickLine: false };

function ChartCard({ title, children }) {
  return (
    <div className="rounded-lg p-5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
      <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: PBI.slate }}>{title}</h3>
      {children}
    </div>
  );
}

export function TrendCharts({ data }) {
  if (!data || data.length < 2) return null;

  return (
    <div className="space-y-6 mb-8">
      <h2 className="text-lg font-bold" style={{ color: PBI.navy }}>Tendencia entre períodos</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Promedio y tasa aprobación */}
        <ChartCard title="Promedio calificaciones y tasa de aprobación">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: PBI.slate }} {...axisProps} />
              <YAxis tick={{ fontSize: 12, fill: PBI.slate }} domain={[0, 100]} {...axisProps} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" iconSize={8} />
              <Line
                type="monotone"
                dataKey="promedio_calificaciones"
                name="Promedio"
                stroke={PBI.blue}
                strokeWidth={2.5}
                dot={{ r: 4, fill: PBI.blue }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="tasa_aprobacion"
                name="Aprobación %"
                stroke={PBI.teal}
                strokeWidth={2.5}
                dot={{ r: 4, fill: PBI.teal }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Estudiantes y riesgo alto */}
        <ChartCard title="Estudiantes totales y en riesgo alto">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: PBI.slate }} {...axisProps} />
              <YAxis tick={{ fontSize: 12, fill: PBI.slate }} {...axisProps} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" iconSize={8} />
              <Bar dataKey="total_estudiantes" name="Estudiantes" fill={PBI.blue} radius={[6, 6, 0, 0]} />
              <Bar dataKey="riesgo_alto" name="Riesgo alto" fill={PBI.coral} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Docentes e intervenciones */}
        <ChartCard title="Docentes e intervenciones por período">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: PBI.slate }} {...axisProps} />
              <YAxis tick={{ fontSize: 12, fill: PBI.slate }} {...axisProps} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" iconSize={8} />
              <Bar dataKey="total_docentes" name="Docentes" fill={PBI.purple} radius={[6, 6, 0, 0]} />
              <Bar dataKey="total_intervenciones" name="Intervenciones" fill={PBI.gold} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
