/**
 * Botón de exportación Excel (.xlsx) con hoja LÉEME de autoría.
 *
 * Props:
 *   data: array de objetos a exportar
 *   columns: array de {key, label} con las columnas disponibles
 *   filename: nombre del archivo (sin extensión)
 *   defaultSelected: array de keys seleccionados por defecto
 *   reportTitle: título descriptivo del reporte (para la hoja LÉEME)
 */
import { useState } from "react";
import * as XLSX from "xlsx";

const MESES_ES = {
  0: "enero", 1: "febrero", 2: "marzo", 3: "abril",
  4: "mayo", 5: "junio", 6: "julio", 7: "agosto",
  8: "septiembre", 9: "octubre", 10: "noviembre", 11: "diciembre",
};

function buildLeemeSheet(reportTitle, numRows, numCols) {
  const now = new Date();
  const fecha = `${now.getDate()} de ${MESES_ES[now.getMonth()]} de ${now.getFullYear()}`;
  const anio = now.getFullYear();

  const lines = [
    ["════════════════════════════════════════════════════════════════"],
    ["           DOCUMENTACIÓN Y TÉRMINOS DE USO DE DATOS"],
    ["════════════════════════════════════════════════════════════════"],
    [""],
    ["1. INFORMACIÓN DE AUTORÍA Y PROPIEDAD INTELECTUAL"],
    ["────────────────────────────────────────────────────────────────"],
    [`• Desarrollado por:     Carlos Vásconez-Paredes`],
    ["• Cargo/Función:        Gestor de Analítica del Aprendizaje"],
    ["• Institución:          Universidad Politécnica Salesiana"],
    [`• Fecha de generación:  ${fecha}`],
    ["• Versión del dataset:  v1.0 (Estructurado y Procesado)"],
    [`• Reporte:              ${reportTitle}`],
    [""],
    ["2. CONDICIONES DE USO Y RECONOCIMIENTO (LICENCIA)"],
    ["────────────────────────────────────────────────────────────────"],
    ["Este conjunto de datos, métricas e interpretaciones analíticas son el resultado"],
    ["de un desarrollo metodológico y técnico específico. Se autoriza su uso para"],
    ["fines académicos, artículos científicos, ponencias y conferencias, bajo la"],
    ["condición estricta de otorgar el crédito correspondiente al autor."],
    [""],
    ["De acuerdo con las políticas de integridad científica, la omisión de la fuente"],
    ["se considerará una falta a la ética académica."],
    [""],
    ["3. FORMA SUGERIDA DE CITA / REFERENCIA"],
    ["────────────────────────────────────────────────────────────────"],
    ["• Estilo APA (7ma ed.):"],
    [`  Vásconez-Paredes, C. (${anio}). ${reportTitle}`],
    ["  (Versión 1.0) [Conjunto de datos/Métricas analíticas]. Gestión de Analítica"],
    ["  del Aprendizaje, Universidad Politécnica Salesiana."],
    [""],
    ["• Estilo Vancouver / Nota al pie:"],
    [`  Datos analíticos y procesamiento metodológico provistos por Carlos`],
    [`  Vásconez-Paredes, Gestión de Analítica del Aprendizaje, Universidad`],
    [`  Politécnica Salesiana, ${anio}.`],
    [""],
    ["4. CONTACTO Y COLABORACIÓN"],
    ["────────────────────────────────────────────────────────────────"],
    ["Si su investigación requiere modificaciones metodológicas en los datos, cruces"],
    ["de variables avanzados o una interpretación analítica conjunta que impacte la"],
    ["sección de \"Metodología\" o \"Resultados\" del artículo, por favor tome contacto"],
    ["para estructurar una participación formal bajo la figura de coautoría."],
    [""],
    ["Contacto: cvasconez@ups.edu.ec"],
    [""],
    ["5. INFORMACIÓN DE ESTA EXPORTACIÓN"],
    ["────────────────────────────────────────────────────────────────"],
    [`• Filas de datos:   ${numRows}`],
    [`• Columnas:         ${numCols}`],
    [`• Fecha/hora:       ${now.toLocaleString("es-EC")}`],
    ["• Plataforma:       YachayDeep — Sistema de Analítica del Aprendizaje"],
    ["════════════════════════════════════════════════════════════════"],
  ];

  const ws = XLSX.utils.aoa_to_sheet(lines.map(l => [l[0] || ""]));
  ws["!cols"] = [{ wch: 80 }];
  return ws;
}

export default function ExportExcelButton({
  data = [], columns = [], filename = "export",
  defaultSelected = null, label = "Exportar Excel", small = false,
  reportTitle = null,
}) {
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

    try {
      const cols = columns.filter(c => selected.has(c.key));
      const title = reportTitle || filename.replace(/_/g, " ");

      // Build workbook
      const wb = XLSX.utils.book_new();

      // 1) LÉEME sheet
      const leemeWs = buildLeemeSheet(title, data.length, cols.length);
      XLSX.utils.book_append_sheet(wb, leemeWs, "LÉEME");

      // 2) Data sheet
      const headers = cols.map(c => c.label);
      const rows = data.map(row =>
        cols.map(c => {
          const val = row[c.key];
          return val == null ? "" : val;
        })
      );
      const dataWs = XLSX.utils.aoa_to_sheet([headers, ...rows]);

      // Auto-fit column widths
      const colWidths = cols.map((c, i) => {
        let maxLen = c.label.length;
        for (let r = 0; r < Math.min(rows.length, 50); r++) {
          const val = rows[r][i];
          if (val != null) maxLen = Math.max(maxLen, String(val).length);
        }
        return { wch: Math.min(maxLen + 3, 45) };
      });
      dataWs["!cols"] = colWidths;

      // Sheet name based on filename
      const sheetName = filename.length > 31
        ? filename.slice(0, 31)
        : filename;
      XLSX.utils.book_append_sheet(wb, dataWs, sheetName.replace(/[\\\/\*\?\[\]:]/g, "_"));

      // Write and download
      const wbout = XLSX.write(wb, { bookType: "xlsx", type: "array" });
      const blob = new Blob([wbout], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${filename}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Error exportando Excel:", err);
      alert("Error al generar el archivo Excel. Intenta de nuevo.");
    } finally {
      setExporting(false);
      setOpen(false);
    }
  };

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors shadow-sm ${
          small ? "px-2.5 py-1 text-xs" : "px-4 py-2 text-sm gap-2"
        }`}
      >
        <span className={small ? "text-xs" : ""}>📥</span> {label}
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

            {/* Info + nota LÉEME */}
            <div className="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 mb-3">
              <p className="text-[11px] text-blue-700">
                📋 El archivo incluirá una hoja <strong>LÉEME</strong> con información de autoría, licencia y forma de cita recomendada.
              </p>
            </div>

            {/* Información y botones */}
            <div className="flex items-center justify-between pt-3 border-t border-gray-100">
              <span className="text-[11px] text-gray-400">{data.length} filas · {selected.size} columnas · formato .xlsx</span>
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
