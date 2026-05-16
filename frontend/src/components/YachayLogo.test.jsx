/**
 * Tests: YachayLogo, YachayIcon
 *
 * Note: the brand mark is rendered as an <img> referencing the SVG asset
 * in /yachay-logo.svg, so tests query for <img> instead of <svg>.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { YachayLogo, YachayIcon } from "./YachayLogo.jsx";

describe("YachayLogo", () => {
  it("renderiza el logo como <img>", () => {
    const { container } = render(<YachayLogo />);
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img.getAttribute("src")).toBe("/yachay-logo.svg");
    expect(img.getAttribute("alt")).toBe("Yachay Deep");
  });

  it("respeta prop size", () => {
    const { container } = render(<YachayLogo size={100} />);
    const img = container.querySelector("img");
    expect(img.getAttribute("width")).toBe("100");
    expect(img.getAttribute("height")).toBe("100");
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
  it("renderiza el icono como <img>", () => {
    const { container } = render(<YachayIcon />);
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img.getAttribute("src")).toBe("/yachay-logo.svg");
  });

  it("usa size por defecto de 32", () => {
    const { container } = render(<YachayIcon />);
    const img = container.querySelector("img");
    expect(img.getAttribute("width")).toBe("32");
    expect(img.getAttribute("height")).toBe("32");
  });

  it("respeta size personalizado", () => {
    const { container } = render(<YachayIcon size={64} />);
    const img = container.querySelector("img");
    expect(img.getAttribute("width")).toBe("64");
    expect(img.getAttribute("height")).toBe("64");
  });
});
