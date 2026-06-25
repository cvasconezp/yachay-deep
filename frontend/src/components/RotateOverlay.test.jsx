/**
 * Tests: RotateOverlay
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RotateOverlay } from "./RotateOverlay.jsx";

describe("RotateOverlay", () => {
  it("renderiza mensaje de rotación", () => {
    render(<RotateOverlay />);
    expect(screen.getByText("Gira tu dispositivo")).toBeInTheDocument();
  });

  it("muestra texto descriptivo", () => {
    render(<RotateOverlay />);
    expect(screen.getByText(/optimizado para usarse en modo horizontal/)).toBeInTheDocument();
  });

  it("tiene z-index alto para cubrir todo", () => {
    const { container } = render(<RotateOverlay />);
    const overlay = container.firstChild;
    expect(overlay.style.zIndex).toBe("9999");
  });

  it("contiene SVG de icono", () => {
    const { container } = render(<RotateOverlay />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
