import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DashboardCharts from "./DashboardCharts";

const mockStats = {
  total_estudiantes: 100,
  por_nivel_riesgo: [
    { nivel: "Alto", total: 30 },
    { nivel: "Medio", total: 45 },
    { nivel: "Bajo", total: 25 },
  ],
  por_carrera: [
    { carrera: "Educación Básica", total: 40 },
    { carrera: "Pedagogía", total: 35 },
    { carrera: "Comunicación", total: 25 },
  ],
  total_aulas_virtuales: 15,
  estudiantes_intervenidos: 22,
  tiene_datos_periodo: true,
};

const mockStudents = [
  { id: 1, porcentaje_tareas: 80, dias_sin_acceso: 3 },
  { id: 2, porcentaje_tareas: 20, dias_sin_acceso: 20 },
  { id: 3, porcentaje_tareas: 60, dias_sin_acceso: 5 },
];

describe("DashboardCharts", () => {
  it("renderiza los 3 paneles de gráficos", () => {
    render(<DashboardCharts stats={mockStats} students={mockStudents} />);
    expect(screen.getByText("Distribución de Riesgo")).toBeInTheDocument();
    expect(screen.getByText(/Estudiantes por Carrera/)).toBeInTheDocument();
    expect(screen.getByText("Indicadores Clave")).toBeInTheDocument();
  });

  it("muestra total en el donut", () => {
    render(<DashboardCharts stats={mockStats} students={mockStudents} />);
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("estudiantes")).toBeInTheDocument();
  });

  it("muestra niveles de riesgo en leyenda", () => {
    render(<DashboardCharts stats={mockStats} students={mockStudents} />);
    expect(screen.getByText("Alto")).toBeInTheDocument();
    expect(screen.getByText("Medio")).toBeInTheDocument();
    expect(screen.getByText("Bajo")).toBeInTheDocument();
  });

  it("muestra carreras", () => {
    render(<DashboardCharts stats={mockStats} students={mockStudents} />);
    expect(screen.getByText("Educación Básica")).toBeInTheDocument();
    expect(screen.getByText("Pedagogía")).toBeInTheDocument();
  });

  it("muestra KPIs de aulas e intervenidos", () => {
    render(<DashboardCharts stats={mockStats} students={mockStudents} />);
    expect(screen.getByText("15")).toBeInTheDocument(); // aulas
    expect(screen.getByText("22")).toBeInTheDocument(); // intervenidos
  });

  it("no renderiza si no hay datos de periodo", () => {
    const { container } = render(
      <DashboardCharts stats={{ tiene_datos_periodo: false }} students={[]} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("no renderiza si stats es null", () => {
    const { container } = render(<DashboardCharts stats={null} students={[]} />);
    expect(container.innerHTML).toBe("");
  });
});
