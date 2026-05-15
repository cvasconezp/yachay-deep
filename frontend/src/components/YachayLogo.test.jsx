/**
 * Tests: YachayLogo, YachayIcon
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { YachayLogo, YachayIcon } from "./YachayLogo.jsx";

describe("YachayLogo", () => {
  it("renderiza SVG iceberg", () => {
    const { container } = render(<YachayLogo />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("respeta prop size", () => {
    const { container } = render(<YachayLogo size={100} />);
    const svg = container.querySelector("svg");
    expect(svg.getAttribute("width")).toBe("100");
  });

  it("no muestra texto por defecto", () => {
    render(<YachayLogo />);
    expect(screen.queryByText("Yachay Deep")).not.toBeInTheDocument();
  });

  it("muestra texto cuando showText=true", () => {
    render(<YachayLogo showText />);
    expect(screen.getByText("Yachay Deep")).toBeInTheDocument();
    expect(screen.getByText("Monitoreo Académico")).toBeInTheDocument();
  });

  it("aplica className personalizado", () => {
    const { container } = render(<YachayLogo className="my-custom" />);
    expect(container.firstChild.className).toContain("my-custom");
  });
});

describe("YachayIcon", () => {
  it("renderiza SVG", () => {
    const { container } = render(<YachayIcon />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("usa size por defecto de 32", () => {
    const { container } = render(<YachayIcon />);
    const svg = container.querySelector("svg");
    expect(svg.getAttribute("width")).toBe("32");
  });

  it("respeta size personalizado", () => {
    const { container } = render(<YachayIcon size={64} />);
    const svg = container.querySelector("svg");
    expect(svg.getAttribute("width")).toBe("64");
  });
});
