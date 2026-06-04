/**
 * Tests: StudentListModal (ModalContent)
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModalContent from "./StudentListModal.jsx";

const STUDENTS = [
  { id: 1, nombre: "Juan Pérez", cedula: "1234567890", carrera: "Derecho", nivel_academico: 3, nivel_riesgo: "Alto", promedio_calificaciones: 65, dias_sin_acceso: 15, porcentaje_tareas: 40 },
  { id: 2, nombre: "Ana López", cedula: "0987654321", carrera: "Educación", nivel_academico: 5, nivel_riesgo: "Bajo", promedio_calificaciones: 92, dias_sin_acceso: 2, porcentaje_tareas: 95 },
];

describe("StudentListModal (ModalContent)", () => {
  it("muestra título según tipo", () => {
    render(<ModalContent tipo="riesgo_alto" estudiantes={STUDENTS} total={2} loading={false} onClose={() => {}} onNavigate={() => {}} />);
    expect(screen.getByText("Estudiantes — Riesgo Alto")).toBeInTheDocument();
  });

  it("muestra conteo de estudiantes", () => {
    render(<ModalContent tipo="riesgo_alto" estudiantes={STUDENTS} total={2} loading={false} onClose={() => {}} onNavigate={() => {}} />);
    expect(screen.getByText("2 estudiantes")).toBeInTheDocument();
  });

  it("muestra datos de estudiantes en tabla", () => {
    render(<ModalContent tipo="riesgo_alto" estudiantes={STUDENTS} total={2} loading={false} onClose={() => {}} onNavigate={() => {}} />);
    expect(screen.getByText("Juan Pérez")).toBeInTheDocument();
    expect(screen.getByText("Ana López")).toBeInTheDocument();
    expect(screen.getByText("1234567890")).toBeInTheDocument();
  });

  it("muestra loading state", () => {
    render(<ModalContent tipo="riesgo_alto" estudiantes={[]} total={0} loading={true} onClose={() => {}} onNavigate={() => {}} />);
    expect(screen.getByText("Cargando listado...")).toBeInTheDocument();
  });

  it("muestra estado vacío", () => {
    render(<ModalContent tipo="riesgo_alto" estudiantes={[]} total={0} loading={false} onClose={() => {}} onNavigate={() => {}} />);
    expect(screen.getByText("No se encontraron estudiantes")).toBeInTheDocument();
  });

  it("click en nombre navega a ficha", async () => {
    const onNavigate = vi.fn();
    render(<ModalContent tipo="riesgo_alto" estudiantes={STUDENTS} total={2} loading={false} onClose={() => {}} onNavigate={onNavigate} />);
    await userEvent.click(screen.getByText("Juan Pérez"));
    expect(onNavigate).toHaveBeenCalledWith(1);
  });

  it("muestra columna asignaturas para repitentes", () => {
    const repitentes = [{ ...STUDENTS[0], asignaturas_repitencia: ["Matemáticas", "Física"] }];
    render(<ModalContent tipo="repitentes" estudiantes={repitentes} total={1} loading={false} onClose={() => {}} onNavigate={() => {}} />);
    expect(screen.getByText("Matemáticas")).toBeInTheDocument();
    expect(screen.getByText("Física")).toBeInTheDocument();
  });

  it("botón exportar CSV existe", () => {
    render(<ModalContent tipo="riesgo_alto" estudiantes={STUDENTS} total={2} loading={false} onClose={() => {}} onNavigate={() => {}} />);
    expect(screen.getByText(/Exportar CSV/)).toBeInTheDocument();
  });
});
