/**
 * Hook de debouncing — [PERF-03] Remediación.
 *
 * Uso:
 *   const debouncedFilters = useDebounce(filters, 400);
 *   useEffect(() => { fetchData(debouncedFilters); }, [debouncedFilters]);
 */
import { useState, useEffect } from "react";

export function useDebounce(value, delay = 400) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
