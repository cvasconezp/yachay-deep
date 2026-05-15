/**
 * Tests: BulkInterventionModal
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BulkInterventionModal from "./BulkInterventionModal.jsx";

vi.mock("../services/api", () => ({
  api: { bulkCreateInterventions: vi.fn() },
}));

// Mock constants
vi.mock("../constants/interventions", () => ({
  MEDIOS: ["Llamada telefónica", "WhatsApp", "Email"],
  MOTIVOS: ["Seguimiento académico", "Ausentismo"],
  ESTADOS: ["Contactado", "No contactado"],
  RESULTADOS: ["Compromiso de mejora", "Sin respuesta"],
}));

import { api } from "../services/api";

const STUDENTS = [
  { id: 1, nombre: "Juan Pérez", carrera: "Derecho" },
  { id: 2, nombre: "Ana López", carrera: "Educación" },
];

describe("BulkInterventionModal", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("muestra título y conteo de estudiantes", () => {
    render(<BulkInterventionModal selectedStudents={STUDENTS} onClose={() => {}} onSaved={() => {}} />);
    expect(screen.getByText("Intervención Masiva")).toBeInTheDocument();
    expect(screen.getByText(/2\s*estudiantes?\s*seleccionados?/)).toBeInTheDocument();
  });

  it("muestra nombres de estudiantes en preview", () => {
    render(<BulkInterventionModal selectedStudents={STUDENTS} onClose={() => {}} onSaved={() => {}} />);
    expect(screen.getByText("Juan Pérez")).toBeInTheDocument();
    expect(screen.getByText("Ana López")).toBeInTheDocument();
  });

  it("muestra error si campos obligatorios vacíos", async () => {
    render(<BulkInterventionModal selectedStudents={STUDENTS} onClose={() => {}} onSaved={() => {}} />);
    // Use regex to find button with "Guardar" text
    const submitBtn = screen.getByRole("button", { name: /Guardar/i });
    await userEvent.click(submitBtn);
    expect(screen.getByText(/obligatori/i)).toBeInTheDocument();
  });

  it("llama api.bulkCreateInterventions al submit válido", async () => {
    api.bulkCreateInterventions.mockResolvedValue({ created: 2, errors: [] });
    const onSaved = vi.fn();
    render(<BulkInterventionModal selectedStudents={STUDENTS} onClose={() => {}} onSaved={onSaved} />);

    // Seleccionar campos obligatorios
    const selects = screen.getAllByRole("combobox");
    await userEvent.selectOptions(selects[0], "Llamada telefónica"); // medio
    await userEvent.selectOptions(selects[1], "Seguimiento académico"); // motivo
    await userEvent.selectOptions(selects[2], "Contactado"); // estado

    await userEvent.click(screen.getByRole("button", { name: /Guardar/i }));
    expect(api.bulkCreateInterventions).toHaveBeenCalled();
    expect(onSaved).toHaveBeenCalled();
  });

  it("muestra contexto prefill si existe", () => {
    render(
      <BulkInterventionModal
        selectedStudents={STUDENTS}
        prefill={{ observacion: "No entregó Unidad 1", medio: "WhatsApp" }}
        onClose={() => {}}
        onSaved={() => {}}
      />
    );
    expect(screen.getByText("No entregó Unidad 1")).toBeInTheDocument();
  });

  it("singular para 1 estudiante", () => {
    render(<BulkInterventionModal selectedStudents={[STUDENTS[0]]} onClose={() => {}} onSaved={() => {}} />);
    expect(screen.getByText(/1\s*estudiante\s*seleccionado/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Guardar 1 Intervención$/i })).toBeInTheDocument();
  });
});
