import { useState, useEffect } from "react";
import { api } from "../services/api";

const FALLBACK = [{ key: "actual", label: "Semestre actual" }];

export function PeriodSelector({ value, onChange, className = "" }) {
  const [periodos, setPeriodos] = useState(FALLBACK);

  useEffect(() => {
    api.getPeriodosDisponibles()
      .then(p => { if (p && p.length > 0) setPeriodos(p); })
      .catch(() => {});
  }, []);

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
