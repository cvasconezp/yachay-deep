/**
 * Tests: YachayLogo, YachayIcon
 *
 * Both marks are rendered as <img> referencing SVG assets in /public:
 *   - YachayLogo variant="light"  → /yachay-logo-light.svg
 *   - YachayLogo variant="dark"   → /yachay-logo-dark.svg
 *   - YachayIcon                  → /yachay-favicon.svg
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { YachayLogo, YachayIcon } from "./YachayLogo.jsx";

const HEADER_ASPECT = 840 / 445;

describe("YachayLogo", () => {
  it("renderiza el logo como <img>", () => {
    const { container } = render(<YachayLogo />);
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img.getAttribute("alt")).toBe("Yachay Deep");
  });

  it("usa la variante light por defecto", () => {
    const { container } = render(<YachayLogo />);
    const img = container.querySelector("img");
    expect(img.getAttribute("src")).toBe("/yachay-logo-light.svg");
  });

  it("usa la variante dark cuando se especifica", () => {
    const { container } = render(<YachayLogo variant="dark" />);
    const img = container.querySelector("img");
    expect(img.getAttribute("src")).toBe("/yachay-logo-dark.svg");
  });

  it("size establece height y width vía aspect ratio", () => {
    const { container } = render(<YachayLogo size={100} />);
    const img = container.querySelector("img");
    expect(img.getAttribute("height")).toBe("100");
    expect(img.getAttribute("width")).toBe(String(Math.round(100 * HEADER_ASPECT)));
  });

  it("sin size, no emite atributos width/height (responsive via CSS)", () => {
    const { container } = render(<YachayLogo className="w-full h-auto" />);
    const img = container.querySelector("img");
    expect(img.getAttribute("width")).toBeNull();
    expect(img.getAttribute("height")).toBeNull();
    expect(img.className).toContain("w-full");
    expect(img.className).toContain("h-auto");
  });

  it("aplica className personalizado", () => {
    const { container } = render(<YachayLogo className="my-custom" />);
    const img = container.querySelector("img");
    expect(img.className).toContain("my-custom");
  });
});

describe("YachayIcon", () => {
  it("renderiza el favicon como <img>", () => {
    const { container } = render(<YachayIcon />);
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img.getAttribute("src")).toBe("/yachay-favicon.svg");
  });

  it("respeta size cuando se especifica", () => {
    const { container } = render(<YachayIcon size={64} />);
    const img = container.querySelector("img");
    expect(img.getAttribute("width")).toBe("64");
    expect(img.getAttribute("height")).toBe("64");
  });

  it("sin size, no emite atributos width/height", () => {
    const { container } = render(<YachayIcon className="w-6 h-6" />);
    const img = container.querySelector("img");
    expect(img.getAttribute("width")).toBeNull();
    expect(img.getAttribute("height")).toBeNull();
  });
});
