/**
 * Tests: EcuadorMap
 * El componente usa SVG paths de datos GADM — no react-leaflet.
 * Requiere una provincia válida para renderizar el mapa.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import EcuadorMap from "./EcuadorMap.jsx";

// Mock the cantones data with a minimal valid province
vi.mock("../data/ecuadorCantones", () => ({
  default: {
    Pichincha: {
      bounds: { minX: -79, maxX: -78, minY: -0.5, maxY: 0.5 },
      cantones: [
        { name: "Quito", path: "M0,0 L1,0 L1,1 L0,1 Z", labelX: 0.5, labelY: 0.5 },
        { name: "Rumiñahui", path: "M2,0 L3,0 L3,1 L2,1 Z", labelX: 2.5, labelY: 0.5 },
      ],
    },
  },
}));

describe("EcuadorMap", () => {
  it("muestra fallback sin provincia", () => {
    render(<EcuadorMap />);
    expect(screen.getByText("Sin datos geograficos")).toBeInTheDocument();
  });

  it("renderiza SVG con provincia válida", () => {
    const { container } = render(<EcuadorMap provincia="Pichincha" ciudad="Quito" />);
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
  });

  it("renderiza paths de cantones", () => {
    const { container } = render(<EcuadorMap provincia="Pichincha" ciudad="Quito" />);
    const paths = container.querySelectorAll("path");
    expect(paths.length).toBeGreaterThanOrEqual(2);
  });

  it("resalta cantón coincidente con color dorado", () => {
    const { container } = render(<EcuadorMap provincia="Pichincha" ciudad="Quito" />);
    const paths = container.querySelectorAll("path");
    const fills = Array.from(paths).map(p => p.getAttribute("fill"));
    expect(fills).toContain("#F5B800"); // Gold for highlighted canton
  });

  it("muestra título si showTitle es true", () => {
    render(<EcuadorMap provincia="Pichincha" ciudad="Quito" showTitle />);
    expect(screen.getByText("Pichincha")).toBeInTheDocument();
  });
});
