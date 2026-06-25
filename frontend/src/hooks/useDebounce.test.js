/**
 * T26: Tests del hook useDebounce
 *
 * Cobertura:
 *  - Valor inicial se retorna inmediatamente
 *  - Valor cambiado se retorna tras delay
 *  - Cambios rapidos solo producen el ultimo valor
 *  - Custom delay funciona
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "./useDebounce.js";

describe("useDebounce", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("retorna valor inicial inmediatamente", () => {
    const { result } = renderHook(() => useDebounce("hello", 400));
    expect(result.current).toBe("hello");
  });

  it("retorna valor actualizado tras el delay", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 400),
      { initialProps: { value: "a" } }
    );
    expect(result.current).toBe("a");

    rerender({ value: "b" });
    expect(result.current).toBe("a"); // aun no cambio

    act(() => vi.advanceTimersByTime(400));
    expect(result.current).toBe("b");
  });

  it("multiples cambios rapidos solo producen el ultimo", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "x" } }
    );

    rerender({ value: "y" });
    act(() => vi.advanceTimersByTime(100));
    rerender({ value: "z" });
    act(() => vi.advanceTimersByTime(300));

    expect(result.current).toBe("z");
  });

  it("respeta custom delay", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 1000),
      { initialProps: { value: "start" } }
    );

    rerender({ value: "end" });
    act(() => vi.advanceTimersByTime(500));
    expect(result.current).toBe("start"); // aun no

    act(() => vi.advanceTimersByTime(500));
    expect(result.current).toBe("end");
  });

  it("funciona con objetos", () => {
    const obj1 = { q: "test" };
    const obj2 = { q: "updated" };
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 400),
      { initialProps: { value: obj1 } }
    );

    rerender({ value: obj2 });
    act(() => vi.advanceTimersByTime(400));
    expect(result.current).toEqual({ q: "updated" });
  });
});
