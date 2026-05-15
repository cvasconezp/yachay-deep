/**
 * Hook para persistir filtros en URL search params — [BUG-02] Remediación.
 *
 * Uso:
 *   const { filters, updateFilter, clearFilters } = useUrlFilters({
 *     carrera: "", nivel_riesgo: "", periodo: "",
 *   });
 */
import { useSearchParams } from "react-router-dom";
import { useCallback } from "react";

export function useUrlFilters(defaults = {}) {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = {};
  for (const [key, defaultVal] of Object.entries(defaults)) {
    filters[key] = searchParams.get(key) || defaultVal;
  }

  const setFilters = useCallback((newFilters) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [key, val] of Object.entries(newFilters)) {
        if (val === "" || val == null) next.delete(key);
        else next.set(key, val);
      }
      return next;
    });
  }, [setSearchParams]);

  const updateFilter = useCallback((key, value) => setFilters({ [key]: value }), [setFilters]);
  const clearFilters = useCallback(() => setSearchParams({}), [setSearchParams]);

  return { filters, setFilters, updateFilter, clearFilters };
}
