/**
 * T27: Tests del hook useUrlFilters
 *
 * Cobertura:
 *  - Lee defaults cuando URL no tiene params
 *  - Lee valores de URL existentes
 *  - updateFilter cambia un param
 *  - clearFilters limpia todo
 *  - setFilters con valor vacio elimina el param
 */
import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useUrlFilters } from "./useUrlFilters.js";

function wrapper({ initialEntries = ["/"] } = {}) {
  return function Wrapper({ children }) {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>;
  };
}

describe("useUrlFilters", () => {
  it("retorna defaults cuando URL no tiene params", () => {
    const { result } = renderHook(
      () => useUrlFilters({ carrera: "", nivel_riesgo: "todos" }),
      { wrapper: wrapper() }
    );
    expect(result.current.filters).toEqual({ carrera: "", nivel_riesgo: "todos" });
  });

  it("lee valores de URL existentes", () => {
    const { result } = renderHook(
      () => useUrlFilters({ carrera: "", nivel_riesgo: "" }),
      { wrapper: wrapper({ initialEntries: ["/?carrera=DERECHO&nivel_riesgo=alto"] }) }
    );
    expect(result.current.filters.carrera).toBe("DERECHO");
    expect(result.current.filters.nivel_riesgo).toBe("alto");
  });

  it("updateFilter cambia un solo param", () => {
    const { result } = renderHook(
      () => useUrlFilters({ carrera: "", periodo: "" }),
      { wrapper: wrapper() }
    );

    act(() => {
      result.current.updateFilter("carrera", "EDUCACION");
    });

    expect(result.current.filters.carrera).toBe("EDUCACION");
    expect(result.current.filters.periodo).toBe("");
  });

  it("setFilters puede establecer multiples params", () => {
    const { result } = renderHook(
      () => useUrlFilters({ carrera: "", periodo: "", riesgo: "" }),
      { wrapper: wrapper() }
    );

    act(() => {
      result.current.setFilters({ carrera: "DERECHO", periodo: "P67" });
    });

    expect(result.current.filters.carrera).toBe("DERECHO");
    expect(result.current.filters.periodo).toBe("P67");
  });

  it("setFilters con valor vacio elimina el param", () => {
    const { result } = renderHook(
      () => useUrlFilters({ carrera: "", periodo: "" }),
      { wrapper: wrapper({ initialEntries: ["/?carrera=DERECHO"] }) }
    );

    expect(result.current.filters.carrera).toBe("DERECHO");

    act(() => {
      result.current.setFilters({ carrera: "" });
    });

    expect(result.current.filters.carrera).toBe("");
  });

  it("clearFilters limpia todos los params", () => {
    const { result } = renderHook(
      () => useUrlFilters({ carrera: "", periodo: "" }),
      { wrapper: wrapper({ initialEntries: ["/?carrera=X&periodo=P67"] }) }
    );

    act(() => {
      result.current.clearFilters();
    });

    expect(result.current.filters.carrera).toBe("");
    expect(result.current.filters.periodo).toBe("");
  });
});
