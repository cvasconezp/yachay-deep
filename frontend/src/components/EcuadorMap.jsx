/**
 * Mapa detallado de Ecuador a nivel de cantones (ADM2) usando datos GADM.
 * Muestra la provincia del estudiante con sus cantones y resalta la ciudad de procedencia.
 *
 * Props:
 *   provincia  - nombre de la provincia (ej. "Imbabura", "GUAYAS")
 *   ciudad     - nombre de la ciudad/canton (ej. "Otavalo", "GUAYAQUIL")
 *   parroquia  - (opcional) nombre de la parroquia
 *   height     - altura del contenedor (default 160)
 */

import ECUADOR_CANTONES from "../data/ecuadorCantones";

// ── Normalizar nombre para matching flexible ──────────────────────────────────
function norm(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, "")
    .trim();
}

/** Busca la provincia en los datos GADM (match flexible) */
function findProvince(provincia) {
  if (!provincia) return null;
  const n = norm(provincia);
  for (const name of Object.keys(ECUADOR_CANTONES)) {
    if (norm(name) === n) return name;
  }
  // Match parcial
  for (const name of Object.keys(ECUADOR_CANTONES)) {
    const nn = norm(name);
    if (nn.includes(n) || n.includes(nn)) return name;
  }
  return null;
}

/** Busca un canton dentro de una provincia (match flexible) */
function findCanton(provData, ciudad, parroquia) {
  if (!provData) return null;
  for (const loc of [ciudad, parroquia]) {
    if (!loc) continue;
    const n = norm(loc);
    // Exact match
    for (const canton of provData.cantones) {
      if (norm(canton.name) === n) return canton;
    }
    // Partial match
    for (const canton of provData.cantones) {
      const cn = norm(canton.name);
      if (cn.includes(n) || n.includes(cn)) return canton;
    }
  }
  return null;
}

// ── Colores ──────────────────────────────────────────────────────────────────
const COLORS = {
  cantonBase:     "#D6E4F0",   // Azul claro para cantones normales
  cantonResalt:   "#F0B000",   // Dorado/amarillo para canton seleccionado
  bordeInterno:   "#FFFFFF",   // Blanco entre cantones
  bordeExterior:  "#1B3A6B",   // Azul oscuro para borde provincia
  vecinos:        "#E8ECF0",   // Gris muy claro para provincias vecinas
  bordeVecinos:   "#CBD5E1",   // Gris medio para bordes vecinos
  texto:          "#1B3A6B",   // Azul institucional
};

// ── Componente ───────────────────────────────────────────────────────────────
export default function EcuadorMap({ provincia, ciudad, parroquia, height = 160 }) {
  const matchedProvName = findProvince(provincia);
  const provData = matchedProvName ? ECUADOR_CANTONES[matchedProvName] : null;
  const matchedCanton = findCanton(provData, ciudad, parroquia);

  if (!provData) {
    // Sin datos: mensaje
    return (
      <div className="flex items-center justify-center text-slate-400 text-xs"
           style={{ height }}>
        Sin datos geograficos
      </div>
    );
  }

  const { bounds, cantones } = provData;

  // ViewBox con padding proporcional
  const bw = bounds.maxX - bounds.minX;
  const bh = bounds.maxY - bounds.minY;
  const padX = bw * 0.15;
  const padY = bh * 0.15;
  // Extra padding arriba para titulo
  const padTop = bh * 0.3;
  const vx = bounds.minX - padX;
  const vy = bounds.minY - padTop;
  const vw = bw + padX * 2;
  const vh = bh + padY + padTop;
  const viewBox = `${vx} ${vy} ${vw} ${vh}`;

  // Escalar elementos relativos al tamano del viewbox
  const scale = Math.max(bw, bh);
  const strokeInt = scale * 0.004;    // borde interno
  const strokeExt = scale * 0.008;    // borde externo
  const strokeVec = scale * 0.002;    // borde vecinos
  const fontTitulo = scale * 0.055;
  const fontCanton = scale * 0.028;
  const fontResalt = scale * 0.035;

  // Nombre legible del canton encontrado (Title Case)
  const cantonDisplayName = matchedCanton
    ? matchedCanton.name.replace(/([A-Z])/g, " $1").trim()
    : null;

  // Nombre legible del canton para la ciudad mostrada
  const ciudadDisplay = ciudad || cantonDisplayName || "";

  return (
    <div className="relative" style={{ height }}>
      <svg
        viewBox={viewBox}
        className="w-full h-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Provincias vecinas como contexto */}
        {Object.entries(ECUADOR_CANTONES).map(([provName, pData]) => {
          if (provName === matchedProvName) return null;
          // Solo dibujar vecinos que esten cerca (dentro de ~2x del bbox)
          const nb = pData.bounds;
          const margin = scale * 0.5;
          if (nb.maxX < bounds.minX - margin || nb.minX > bounds.maxX + margin) return null;
          if (nb.maxY < bounds.minY - margin || nb.minY > bounds.maxY + margin) return null;

          return pData.cantones.map((c, i) => (
            <path
              key={`${provName}-${i}`}
              d={c.path}
              fill={COLORS.vecinos}
              stroke={COLORS.bordeVecinos}
              strokeWidth={strokeVec}
              opacity={0.4}
            />
          ));
        })}

        {/* Cantones de la provincia */}
        {cantones.map((canton, i) => {
          const isHighlighted = matchedCanton && norm(canton.name) === norm(matchedCanton.name);
          return (
            <path
              key={`canton-${i}`}
              d={canton.path}
              fill={isHighlighted ? COLORS.cantonResalt : COLORS.cantonBase}
              stroke={COLORS.bordeInterno}
              strokeWidth={strokeInt}
              strokeLinejoin="round"
            />
          );
        })}

        {/* Borde exterior de la provincia (todos los paths como contorno) */}
        {cantones.map((canton, i) => (
          <path
            key={`border-${i}`}
            d={canton.path}
            fill="none"
            stroke={COLORS.bordeExterior}
            strokeWidth={strokeExt}
            strokeLinejoin="round"
            opacity={0.3}
          />
        ))}

        {/* Etiquetas de cantones */}
        {cantones.map((canton, i) => {
          const isHighlighted = matchedCanton && norm(canton.name) === norm(matchedCanton.name);
          // Nombre legible: insertar espacios antes de mayusculas
          const displayName = canton.name.replace(/([A-Z])/g, " $1").trim();

          if (isHighlighted) {
            // Canton resaltado: nombre grande en bold
            return (
              <text
                key={`label-${i}`}
                x={canton.cx}
                y={canton.cy}
                fontSize={fontResalt}
                fontFamily="Calibri, Arial, sans-serif"
                fill="#1B3A6B"
                fontWeight="700"
                textAnchor="middle"
                dominantBaseline="central"
                stroke="white"
                strokeWidth={fontResalt * 0.2}
                paintOrder="stroke"
              >
                {displayName}
              </text>
            );
          }

          // Otros cantones: nombre pequeno
          return (
            <text
              key={`label-${i}`}
              x={canton.cx}
              y={canton.cy}
              fontSize={fontCanton}
              fontFamily="Calibri, Arial, sans-serif"
              fill="#334155"
              fontWeight="400"
              textAnchor="middle"
              dominantBaseline="central"
              stroke="white"
              strokeWidth={fontCanton * 0.25}
              paintOrder="stroke"
            >
              {displayName}
            </text>
          );
        })}

        {/* Titulo: nombre de la provincia */}
        <text
          x={bounds.minX + bw * 0.5}
          y={bounds.minY - bh * 0.12}
          fontSize={fontTitulo}
          fontFamily="Calibri, Arial, sans-serif"
          fill={COLORS.texto}
          fontWeight="700"
          textAnchor="middle"
        >
          {matchedProvName}
        </text>
      </svg>
    </div>
  );
}
