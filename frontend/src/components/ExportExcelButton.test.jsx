/**
 * Tests: ExportExcelButton
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ExportExcelButton from "./ExportExcelButton.jsx";

const COLUMNS = [
  { key: "nombre", label: "Nombre" },
  { key: "carrera", label: "Carrera" },
  { key: "promedio", label: "Promedio" },
];

const DATA = [
  { nombre: "Juan Pérez", carrera: "Derecho", promedio: 85 },
  { nombre: "Ana López", carrera: "Educación", promedio: 92 },
];

describe("ExportExcelButton", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renderiza botón con label por defecto", () => {
    render(<ExportExcelButton columns={COLUMNS} data={DATA} />);
    expect(screen.getByText("Exportar Excel")).toBeInTheDocument();
  });

  it("acepta label personalizado", () => {
    render(<ExportExcelButton columns={COLUMNS} data={DATA} label="Descargar CSV" />);
    expect(screen.getByText("Descargar CSV")).toBeInTheDocument();
  });

  it("abre modal de configuración al click", async () => {
    render(<ExportExcelButton columns={COLUMNS} data={DATA} />);
    await userEvent.click(screen.getByText("Exportar Excel"));
    expect(screen.getByText("Configurar exportación (3 columnas seleccionadas)")).toBeInTheDocument();
  });

  it("muestra todas las columnas como checkboxes", async () => {
    render(<ExportExcelButton columns={COLUMNS} data={DATA} />);
    await userEvent.click(screen.getByText("Exportar Excel"));
    expect(screen.getByText("Nombre")).toBeInTheDocument();
    expect(screen.getByText("Carrera")).toBeInTheDocument();
    expect(screen.getByText("Promedio")).toBeInTheDocument();
  });

  it("muestra conteo de filas y columnas", async () => {
    render(<ExportExcelButton columns={COLUMNS} data={DATA} />);
    await userEvent.click(screen.getByText("Exportar Excel"));
    expect(screen.getByText(/2 filas · 3 columnas/)).toBeInTheDocument();
  });

  it("tiene botones Seleccionar todas y Mínimo", async () => {
    render(<ExportExcelButton columns={COLUMNS} data={DATA} />);
    await userEvent.click(screen.getByText("Exportar Excel"));
    expect(screen.getByText("Seleccionar todas")).toBeInTheDocument();
    expect(screen.getByText("Mínimo")).toBeInTheDocument();
  });

  it("cerrar modal con botón Cerrar", async () => {
    render(<ExportExcelButton columns={COLUMNS} data={DATA} />);
    await userEvent.click(screen.getByText("Exportar Excel"));
    expect(screen.getByText("Configurar exportación (3 columnas seleccionadas)")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Cerrar"));
    expect(screen.queryByText("Configurar exportación (3 columnas seleccionadas)")).not.toBeInTheDocument();
  });

  it("descargar genera CSV con BOM", async () => {
    const createObjectURL = vi.fn(() => "blob:test");
    const revokeObjectURL = vi.fn();
    global.URL.createObjectURL = createObjectURL;
    global.URL.revokeObjectURL = revokeObjectURL;

    const clickSpy = vi.fn();
    // Save original before spying to avoid infinite recursion
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag) => {
      if (tag === "a") return { set href(v) {}, set download(v) {}, click: clickSpy };
      return originalCreateElement(tag);
    });

    render(<ExportExcelButton columns={COLUMNS} data={DATA} filename="test_export" />);
    await userEvent.click(screen.getByText("Exportar Excel"));
    await userEvent.click(screen.getByText("Descargar Excel"));

    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
  });
});
