/**
 * Botón de exportación Excel con modal de configuración de columnas.
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
  const selectMinimo = () => setSelected(new Set(columns.slice(0, Math.min(3, columns.length)).map(c => c.key)));

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
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm"
      >
        <span>📥</span> Exportar Excel
      </button>

      {open && (
        <div
          className="fixed inset-x-0 top-0 z-50 flex items-start justify-center pt-20"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-white rounded-xl border border-green-200 shadow-xl p-5 mx-4"
            style={{ maxWidth: "800px", width: "100%" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-gray-800">Configurar exportación ({selected.size} columnas seleccionadas)</h3>
              <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
            </div>

            {/* Acciones rápidas */}
            <div className="flex gap-2 mb-4">
              <button onClick={selectAll} className="text-[12px] text-blue-600 hover:underline font-medium">Seleccionar todas</button>
              <button onClick={selectMinimo} className="text-[12px] text-gray-500 hover:underline">Mínimo</button>
            </div>

            {/* Grid de columnas */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-1.5 mb-4">
              {columns.map(col => (
                <label key={col.key} className="flex items-center gap-1.5 text-xs cursor-pointer hover:bg-gray-50 rounded px-1.5 py-1">
                  <input
                    type="checkbox"
                    checked={selected.has(col.key)}
                    onChange={() => toggle(col.key)}
                    className="accent-green-600"
                  />
                  <span className="text-gray-700 truncate" title={col.label}>{col.label}</span>
                </label>
              ))}
            </div>

            {/* Información y botones */}
            <div className="flex items-center justify-between pt-3 border-t border-gray-100">
              <span className="text-[11px] text-gray-400">{data.length} filas · {selected.size} columnas</span>
              <div className="flex gap-2">
                <button
                  onClick={handleExport}
                  disabled={selected.size === 0 || exporting}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  {exporting ? "Generando..." : "Descargar Excel"}
                </button>
                <button onClick={() => setOpen(false)} className="text-sm text-gray-500 hover:text-gray-700">Cerrar</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
