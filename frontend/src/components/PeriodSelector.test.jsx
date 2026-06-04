/**
 * Tests: PeriodSelector
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PeriodSelector } from "./PeriodSelector.jsx";

vi.mock("../services/api", () => ({
  api: {
    getPeriodosDisponibles: vi.fn(),
  },
}));

import { api } from "../services/api";

describe("PeriodSelector", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renderiza con fallback 'Semestre actual' antes de cargar", () => {
    api.getPeriodosDisponibles.mockResolvedValue([]);
    render(<PeriodSelector value="actual" onChange={() => {}} />);
    expect(screen.getByText("Período")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Semestre actual")).toBeInTheDocument();
  });

  it("carga periodos del API y los muestra", async () => {
    api.getPeriodosDisponibles.mockResolvedValue([
      { key: "P67", label: "P67 — 2024-I" },
      { key: "P68", label: "P68 — 2024-II" },
    ]);
    render(<PeriodSelector value="P67" onChange={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("P67 — 2024-I")).toBeInTheDocument();
      expect(screen.getByText("P68 — 2024-II")).toBeInTheDocument();
    });
  });

  it("maneja nuevo formato con default", async () => {
    const onChange = vi.fn();
    api.getPeriodosDisponibles.mockResolvedValue({
      periodos: [{ key: "P67", label: "P67" }, { key: "P68", label: "P68" }],
      default: "P68",
    });
    render(<PeriodSelector value="actual" onChange={onChange} />);
    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith("P68");
    });
  });

  it("no crashea si API falla", async () => {
    api.getPeriodosDisponibles.mockRejectedValue(new Error("Network"));
    render(<PeriodSelector value="actual" onChange={() => {}} />);
    // Debe seguir mostrando fallback
    expect(screen.getByDisplayValue("Semestre actual")).toBeInTheDocument();
  });

  it("llama onChange al seleccionar otro periodo", async () => {
    const onChange = vi.fn();
    api.getPeriodosDisponibles.mockResolvedValue([
      { key: "P67", label: "P67" },
      { key: "P68", label: "P68" },
    ]);
    render(<PeriodSelector value="P67" onChange={onChange} />);
    await waitFor(() => screen.getByText("P68"));

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "P68");
    expect(onChange).toHaveBeenCalledWith("P68");
  });
});
