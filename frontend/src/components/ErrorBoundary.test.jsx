/**
 * T28: Tests de ErrorBoundary
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary.jsx";

// Componente que lanza error
function ThrowError({ message }) {
  throw new Error(message);
}

function SafeChild() {
  return <div>Todo bien</div>;
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // Suprimir console.error del boundary
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("renderiza children cuando no hay error", () => {
    render(
      <ErrorBoundary><SafeChild /></ErrorBoundary>
    );
    expect(screen.getByText("Todo bien")).toBeInTheDocument();
  });

  it("muestra UI de error cuando un hijo lanza", () => {
    render(
      <ErrorBoundary><ThrowError message="crash!" /></ErrorBoundary>
    );
    expect(screen.getByText("Algo salió mal")).toBeInTheDocument();
    expect(screen.getByText("crash!")).toBeInTheDocument();
  });

  it("muestra boton de recargar", () => {
    render(
      <ErrorBoundary><ThrowError message="test" /></ErrorBoundary>
    );
    expect(screen.getByText("Recargar página")).toBeInTheDocument();
  });

  it("muestra 'Error desconocido' si error no tiene message", () => {
    // Componente que lanza algo sin message
    function ThrowWeird() { throw {}; } // eslint-disable-line
    render(
      <ErrorBoundary><ThrowWeird /></ErrorBoundary>
    );
    expect(screen.getByText("Error desconocido")).toBeInTheDocument();
  });

  it("logea error en console.error", () => {
    render(
      <ErrorBoundary><ThrowError message="log test" /></ErrorBoundary>
    );
    expect(console.error).toHaveBeenCalled();
  });
});
