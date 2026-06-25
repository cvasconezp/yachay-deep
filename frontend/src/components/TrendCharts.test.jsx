/**
 * Tests: TrendCharts
 * Nota: Recharts usa SVG internamente. Testeamos render condicional y estructura.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendCharts } from "./TrendCharts.jsx";

// Mock recharts ya que usa ResizeObserver que no existe en jsdom
vi.mock("recharts", () => {
  const React = require("react");
  const MockChart = ({ children, data }) => <div data-testid="chart">{children}</div>;
  return {
    ResponsiveContainer: ({ children }) => <div>{children}</div>,
    LineChart: MockChart,
    BarChart: MockChart,
    Line: () => <div data-testid="line" />,
    Bar: () => <div data-testid="bar" />,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
  };
});

const TREND_DATA = [
  { label: "P66", promedio_calificaciones: 72, tasa_aprobacion: 80, total_estudiantes: 100, riesgo_alto: 20, total_docentes: 15, total_intervenciones: 30 },
  { label: "P67", promedio_calificaciones: 75, tasa_aprobacion: 85, total_estudiantes: 110, riesgo_alto: 18, total_docentes: 16, total_intervenciones: 40 },
  { label: "P68", promedio_calificaciones: 78, tasa_aprobacion: 88, total_estudiantes: 120, riesgo_alto: 15, total_docentes: 18, total_intervenciones: 50 },
];

describe("TrendCharts", () => {
  it("retorna null si data es null", () => {
    const { container } = render(<TrendCharts data={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("retorna null si data tiene menos de 2 items", () => {
    const { container } = render(<TrendCharts data={[TREND_DATA[0]]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renderiza título con datos suficientes", () => {
    render(<TrendCharts data={TREND_DATA} />);
    expect(screen.getByText("Tendencia entre períodos")).toBeInTheDocument();
  });

  it("renderiza 3 chart cards", () => {
    render(<TrendCharts data={TREND_DATA} />);
    expect(screen.getByText("Promedio calificaciones y tasa de aprobación")).toBeInTheDocument();
    expect(screen.getByText("Estudiantes totales y en riesgo alto")).toBeInTheDocument();
    expect(screen.getByText("Docentes e intervenciones por período")).toBeInTheDocument();
  });

  it("renderiza charts (mocked)", () => {
    render(<TrendCharts data={TREND_DATA} />);
    const charts = screen.getAllByTestId("chart");
    expect(charts.length).toBe(3);
  });
});
