/**
 * Tests: FilterableStatCards
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FilterableStatCards from "./FilterableStatCards.jsx";

const CARDS = [
  { key: "total", label: "Total", value: 100, color: "text-blue-700" },
  { key: "riesgo", label: "Riesgo Alto", value: 25, color: "text-red-700" },
  { key: "ok", label: "Sin Riesgo", value: 75, color: "text-green-700" },
];

describe("FilterableStatCards", () => {
  it("renderiza todas las tarjetas", () => {
    render(<FilterableStatCards cards={CARDS} onFilterChange={() => {}} />);
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getByText("75")).toBeInTheDocument();
  });

  it("muestra labels en uppercase", () => {
    render(<FilterableStatCards cards={CARDS} onFilterChange={() => {}} />);
    expect(screen.getByText("Total")).toBeInTheDocument();
    expect(screen.getByText("Riesgo Alto")).toBeInTheDocument();
  });

  it("click en tarjeta activa filtro", async () => {
    const onFilter = vi.fn();
    render(<FilterableStatCards cards={CARDS} onFilterChange={onFilter} />);
    await userEvent.click(screen.getByText("25"));
    expect(onFilter).toHaveBeenCalledWith("riesgo");
  });

  it("click en tarjeta activa la desactiva", async () => {
    const onFilter = vi.fn();
    render(<FilterableStatCards cards={CARDS} activeFilter="riesgo" onFilterChange={onFilter} />);
    await userEvent.click(screen.getByText("25"));
    expect(onFilter).toHaveBeenCalledWith(null);
  });

  it("muestra indicador de filtro activo", () => {
    render(<FilterableStatCards cards={CARDS} activeFilter="riesgo" onFilterChange={() => {}} />);
    expect(screen.getByText("✓ Filtro activo")).toBeInTheDocument();
  });

  it("muestra botón limpiar filtro cuando hay filtro activo", () => {
    render(<FilterableStatCards cards={CARDS} activeFilter="total" onFilterChange={() => {}} />);
    expect(screen.getByText("✕ Limpiar filtro")).toBeInTheDocument();
  });

  it("botón limpiar llama onFilterChange(null)", async () => {
    const onFilter = vi.fn();
    render(<FilterableStatCards cards={CARDS} activeFilter="total" onFilterChange={onFilter} />);
    await userEvent.click(screen.getByText("✕ Limpiar filtro"));
    expect(onFilter).toHaveBeenCalledWith(null);
  });

  it("no muestra botón limpiar sin filtro activo", () => {
    render(<FilterableStatCards cards={CARDS} onFilterChange={() => {}} />);
    expect(screen.queryByText("✕ Limpiar filtro")).not.toBeInTheDocument();
  });

  it("maneja cards vacío", () => {
    const { container } = render(<FilterableStatCards cards={[]} onFilterChange={() => {}} />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
