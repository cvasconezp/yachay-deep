/**
 * T28: Tests de StatCard
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard, SummaryCard } from "./StatCard.jsx";

describe("StatCard — preset mode", () => {
  it("renderiza valor y label con color blue", () => {
    render(<StatCard label="Total" value={42} color="blue" />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
  });

  it("aplica clases de preset red", () => {
    const { container } = render(<StatCard label="Riesgo" value={7} color="red" />);
    expect(container.firstChild.className).toContain("red");
  });

  it("preset green funciona", () => {
    const { container } = render(<StatCard label="OK" value={100} color="green" />);
    expect(container.firstChild.className).toContain("green");
  });
});

describe("StatCard — custom mode", () => {
  it("renderiza en modo custom con className", () => {
    render(<StatCard label="Custom" value="$1,000" className="text-blue-600" />);
    expect(screen.getByText("$1,000")).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });

  it("muestra sub text cuando se provee", () => {
    render(<StatCard label="Tasa" value="78%" sub="vs 72% anterior" />);
    expect(screen.getByText("vs 72% anterior")).toBeInTheDocument();
  });

  it("no renderiza sub si no se provee", () => {
    const { container } = render(<StatCard label="X" value="Y" />);
    // No debe existir el div de sub (text-gray-400 mt-0.5)
    expect(container.querySelector(".text-\\[11px\\]")).toBeNull();
  });
});

describe("SummaryCard alias", () => {
  it("SummaryCard es exactamente StatCard", () => {
    expect(SummaryCard).toBe(StatCard);
  });
});
