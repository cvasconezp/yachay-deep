/**
 * Botón de exportación Excel reutilizable con selector de columnas.
 *
 * Props:
 *   data: array de objetos a exportar
 *   columns: array de {key, label} con las columnas disponibles
 *   filename: nombre del archivo (sin extensión)
 *   defaultSelected: array de keys seleccionados por defecto
 */
import { useState } from "react";

export default function ExportExcelButton({ data = [], columns = [], filename = "export", defaultSelected = null }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(
    new Set(defaultSelected || columns.map(c => c.key))
  );
  const [exporting, setExporting] = useState(false);

  const toggle = (key) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(columns.map(c => c.key)));
  const selectNone = () => setSelected(new Set());

  const handleExport = () => {
    if (selected.size === 0 || !data.length) return;
    setExporting(true);

    // Generar CSV (compatible con Excel)
    const cols = columns.filter(c => selected.has(c.key));
    const header = cols.map(c => `"${c.label}"`).join(",");
    const rows = data.map(row =>
      cols.map(c => {
        const val = row[c.key];
        if (val == null) return '""';
        return `"${String(val).replace(/"/g, '""')}"`;
      }).join(",")
    );
    const bom = "\uFEFF"; // BOM para Excel UTF-8
    const csv = bom + header + "\n" + rows.join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    setExporting(false);
    setOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shadow-sm"
      >
        <span>📊</span> Exportar Excel
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-50 p-4"
          style={{ width: "320px", maxHeight: "400px" }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">Columnas a exportar</span>
            <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 text-sm">✕</button>
          </div>

          <div className="flex gap-2 mb-2">
            <button onClick={selectAll} className="text-[10px] text-blue-600 hover:underline">Todas</button>
            <button onClick={selectNone} className="text-[10px] text-blue-600 hover:underline">Ninguna</button>
          </div>

          <div className="max-h-52 overflow-y-auto space-y-0.5 mb-3">
            {columns.map(col => (
              <label key={col.key} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-gray-50 rounded px-2 py-1">
                <input
                  type="checkbox"
                  checked={selected.has(col.key)}
                  onChange={() => toggle(col.key)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-gray-700">{col.label}</span>
              </label>
            ))}
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-gray-100">
            <span className="text-[10px] text-gray-400">{data.length} filas · {selected.size} columnas</span>
            <button
              onClick={handleExport}
              disabled={selected.size === 0 || exporting}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-4 py-1.5 rounded-lg text-xs font-medium transition-colors"
            >
              {exporting ? "Exportando..." : "Descargar CSV"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
