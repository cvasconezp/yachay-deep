/**
 * T28: Tests de componentes — RiskBadge, PredictionBadge, PredictionBar, CompromisoBar
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskBadge, PredictionBadge, PredictionBar, CompromisoBar } from "./RiskBadge.jsx";

describe("RiskBadge", () => {
  it("renderiza nivel Alto con texto correcto", () => {
    render(<RiskBadge nivel="Alto" />);
    expect(screen.getByText("Alto")).toBeInTheDocument();
  });

  it("renderiza nivel Medio", () => {
    render(<RiskBadge nivel="Medio" />);
    expect(screen.getByText("Medio")).toBeInTheDocument();
  });

  it("renderiza nivel Bajo", () => {
    render(<RiskBadge nivel="Bajo" />);
    expect(screen.getByText("Bajo")).toBeInTheDocument();
  });

  it("usa fallback para nivel desconocido", () => {
    render(<RiskBadge nivel="Extremo" />);
    expect(screen.getByText("Extremo")).toBeInTheDocument();
  });

  it("muestra guion si nivel es null", () => {
    render(<RiskBadge nivel={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("oculta dot cuando showDot=false", () => {
    const { container } = render(<RiskBadge nivel="Alto" showDot={false} />);
    // Con showDot=true hay 2 spans (dot + label), sin dot solo el label
    const spans = container.querySelectorAll("span span");
    expect(spans.length).toBe(0);
  });
});

describe("PredictionBadge", () => {
  it("muestra porcentaje redondeado", () => {
    render(<PredictionBadge value={0.753} label="Deserción" />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("muestra placeholder si value es null", () => {
    render(<PredictionBadge value={null} label="Test" />);
    expect(screen.getByText("--")).toBeInTheDocument();
  });

  it("tiene tooltip con info del modelo para Deserción", () => {
    render(<PredictionBadge value={0.85} label="Deserción" />);
    const badge = screen.getByText("85%");
    expect(badge.getAttribute("title")).toContain("riesgo de deserción");
  });

  it("alto riesgo (>=70%) usa colores rojos", () => {
    render(<PredictionBadge value={0.80} label="Test" />);
    const el = screen.getByText("80%");
    expect(el.className).toContain("red");
  });

  it("riesgo moderado (40-69%) usa colores naranja", () => {
    render(<PredictionBadge value={0.50} label="Test" />);
    const el = screen.getByText("50%");
    expect(el.className).toContain("orange");
  });

  it("riesgo bajo (<40%) usa colores verdes", () => {
    render(<PredictionBadge value={0.20} label="Test" />);
    const el = screen.getByText("20%");
    expect(el.className).toContain("green");
  });
});

describe("PredictionBar", () => {
  it("renderiza label y porcentaje", () => {
    render(<PredictionBar value={0.65} label="Reprobación" />);
    expect(screen.getByText("Reprobación")).toBeInTheDocument();
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("retorna null si value es null", () => {
    const { container } = render(<PredictionBar value={null} label="Test" />);
    expect(container.innerHTML).toBe("");
  });

  it("barra tiene width style correcto", () => {
    const { container } = render(<PredictionBar value={0.45} label="Test" />);
    const bar = container.querySelector("[style]");
    expect(bar.style.width).toBe("45%");
  });
});

describe("CompromisoBar", () => {
  it("renderiza porcentaje", () => {
    render(<CompromisoBar valor={0.80} />);
    expect(screen.getByText("80%")).toBeInTheDocument();
  });

  it("retorna placeholder si valor es null", () => {
    render(<CompromisoBar valor={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("alto compromiso (>=70%) usa verde", () => {
    const { container } = render(<CompromisoBar valor={0.90} />);
    const bar = container.querySelector("[style]");
    expect(bar.className).toContain("green");
  });

  it("bajo compromiso (<40%) usa rojo", () => {
    const { container } = render(<CompromisoBar valor={0.20} />);
    const bar = container.querySelector("[style]");
    expect(bar.className).toContain("red");
  });
});
