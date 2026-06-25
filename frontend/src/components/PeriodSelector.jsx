import { useState, useEffect, useRef } from "react";
import { api } from "../services/api";

const FALLBACK = [{ key: "actual", label: "Semestre actual" }];

export function PeriodSelector({ value, onChange, className = "" }) {
  const [periodos, setPeriodos] = useState(FALLBACK);
  const initialized = useRef(false);

  useEffect(() => {
    api.getPeriodosDisponibles()
      .then(data => {
        // Nuevo formato: { periodos: [...], default: "P68" }
        // Retrocompatible con formato viejo: [...]
        const list = Array.isArray(data) ? data : data?.periodos;
        const defaultKey = Array.isArray(data) ? null : data?.default;

        if (list && list.length > 0) {
          setPeriodos(list);
          // Preseleccionar el default si el padre aún no tiene valor o tiene "actual"
          if (!initialized.current && defaultKey && (!value || value === "actual")) {
            onChange(defaultKey);
            initialized.current = true;
          }
        }
      })
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <label className="text-xs font-medium text-gray-600 block mb-1">Período</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className={`border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[180px] ${className}`}
      >
        {periodos.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
      </select>
    </div>
  );
}
