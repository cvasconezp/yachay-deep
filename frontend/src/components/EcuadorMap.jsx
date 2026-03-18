/**
 * Mapa coropletico de Ecuador — nivel cantones (ADM2) usando datos GADM.
 * Muestra la provincia del estudiante con sus cantones y resalta la ciudad.
 *
 * Estilo inspirado en mapas Plotly/Choropleth:
 *   - Gradiente suave de azules para cantones
 *   - Canton resaltado en dorado con borde grueso
 *   - Provincias vecinas translucidas como contexto
 *   - Titulo de provincia y nombre del canton resaltado
 *   - Borde exterior de la provincia bien definido
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

function findProvince(provincia) {
  if (!provincia) return null;
  const n = norm(provincia);
  for (const name of Object.keys(ECUADOR_CANTONES)) {
    if (norm(name) === n) return name;
  }
  for (const name of Object.keys(ECUADOR_CANTONES)) {
    const nn = norm(name);
    if (nn.includes(n) || n.includes(nn)) return name;
  }
  return null;
}

function findCanton(provData, ciudad, parroquia) {
  if (!provData) return null;
  for (const loc of [ciudad, parroquia]) {
    if (!loc) continue;
    const n = norm(loc);
    for (const canton of provData.cantones) {
      if (norm(canton.name) === n) return canton;
    }
    for (const canton of provData.cantones) {
      const cn = norm(canton.name);
      if (cn.includes(n) || n.includes(cn)) return canton;
    }
  }
  return null;
}

/** Nombre legible: CamiloPonceEnriquez → Camilo Ponce Enriquez */
function humanizeName(name) {
  if (!name) return "";
  return name.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2");
}

// ── Paleta coropletica (azules suaves, inspirado en Plotly Blues) ───────────
const CANTON_PALETTE = [
  "#D6E8F7", "#C0D9EE", "#A8CAE5", "#90BBDC",
  "#78ACD3", "#609DCA", "#4A8EBF", "#3580B5",
];

function cantonColor(index, total) {
  const i = Math.floor((index / Math.max(total, 1)) * CANTON_PALETTE.length);
  return CANTON_PALETTE[Math.min(i, CANTON_PALETTE.length - 1)];
}

// ── Componente ───────────────────────────────────────────────────────────────
export default function EcuadorMap({ provincia, ciudad, parroquia, height = 160, showTitle = false }) {
  const matchedProvName = findProvince(provincia);
  const provData = matchedProvName ? ECUADOR_CANTONES[matchedProvName] : null;
  const matchedCanton = findCanton(provData, ciudad, parroquia);

  if (!provData) {
    return (
      <div className="flex items-center justify-center text-slate-400 text-xs" style={{ height }}>
        Sin datos geograficos
      </div>
    );
  }

  const { bounds, cantones } = provData;
  const bw = bounds.maxX - bounds.minX;
  const bh = bounds.maxY - bounds.minY;
  const padX = bw * 0.18;
  const padY = bh * 0.15;
  const padTop = showTitle ? bh * 0.32 : bh * 0.1;
  const vx = bounds.minX - padX;
  const vy = bounds.minY - padTop;
  const vw = bw + padX * 2;
  const vh = bh + padY + padTop;
  const viewBox = `${vx} ${vy} ${vw} ${vh}`;

  const scale = Math.max(bw, bh);
  const strokeInt = scale * 0.0015;
  const strokeExt = scale * 0.004;
  const strokeVec = scale * 0.002;
  const strokeResalt = scale * 0.015;
  const fontTitulo = scale * 0.05;
  const fontCanton = scale * 0.025;
  const fontResalt = scale * 0.042;

  const cantonDisplayName = matchedCanton ? humanizeName(matchedCanton.name) : null;
  const ciudadDisplay = ciudad || cantonDisplayName || "";

  // Ordenar cantones para que el resaltado se dibuje al final (encima)
  const sortedCantones = [...cantones].sort((a, b) => {
    const aH = matchedCanton && norm(a.name) === norm(matchedCanton.name) ? 1 : 0;
    const bH = matchedCanton && norm(b.name) === norm(matchedCanton.name) ? 1 : 0;
    return aH - bH;
  });

  return (
    <div className="relative w-full" style={{ height: height || "100%" }}>
      <svg viewBox={viewBox} className="w-full h-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          {/* Sombra para canton resaltado */}
          <filter id="shadow-canton" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy={scale * 0.005} stdDeviation={scale * 0.008} floodColor="#1B3A6B" floodOpacity="0.3"/>
          </filter>
          {/* Gradiente radial para fondo */}
          <radialGradient id="bg-grad" cx="50%" cy="50%" r="70%">
            <stop offset="0%" stopColor="#F8FAFC"/>
            <stop offset="100%" stopColor="#EEF2F7"/>
          </radialGradient>
        </defs>

        {/* Fondo suave */}
        <rect x={vx} y={vy} width={vw} height={vh} fill="url(#bg-grad)" rx={scale * 0.01}/>

        {/* Provincias vecinas como contexto */}
        {Object.entries(ECUADOR_CANTONES).map(([provName, pData]) => {
          if (provName === matchedProvName) return null;
          const nb = pData.bounds;
          const margin = scale * 0.5;
          if (nb.maxX < bounds.minX - margin || nb.minX > bounds.maxX + margin) return null;
          if (nb.maxY < bounds.minY - margin || nb.minY > bounds.maxY + margin) return null;
          return pData.cantones.map((c, i) => (
            <path key={`${provName}-${i}`} d={c.path} fill="#E8ECF0" stroke="#D1D5DB" strokeWidth={strokeVec} opacity={0.35}/>
          ));
        })}

        {/* Cantones de la provincia (palette coropletica) */}
        {sortedCantones.map((canton, i) => {
          const isHighlighted = matchedCanton && norm(canton.name) === norm(matchedCanton.name);
          return (
            <path
              key={`canton-${i}`}
              d={canton.path}
              fill={isHighlighted ? "#F5B800" : cantonColor(i, cantones.length)}
              stroke={isHighlighted ? "#1B3A6B" : "#FFFFFF"}
              strokeWidth={isHighlighted ? strokeResalt : strokeInt}
              strokeLinejoin="round"
              filter={isHighlighted ? "url(#shadow-canton)" : undefined}
              opacity={isHighlighted ? 1 : 0.85}
            />
          );
        })}

        {/* Borde exterior de la provincia */}
        {cantones.map((canton, i) => (
          <path key={`border-${i}`} d={canton.path} fill="none" stroke="#1B3A6B" strokeWidth={strokeExt} strokeLinejoin="round" opacity={0.25}/>
        ))}

        {/* Etiqueta del canton resaltado (prominente) */}
        {matchedCanton && (
          <g>
            {/* Fondo blanco detrás del nombre */}
            <text
              x={matchedCanton.cx} y={matchedCanton.cy}
              fontSize={fontResalt} fontFamily="system-ui, -apple-system, sans-serif"
              fill="white" fontWeight="800" textAnchor="middle" dominantBaseline="central"
              stroke="white" strokeWidth={fontResalt * 0.4} paintOrder="stroke"
            >
              {humanizeName(matchedCanton.name)}
            </text>
            {/* Nombre en azul oscuro */}
            <text
              x={matchedCanton.cx} y={matchedCanton.cy}
              fontSize={fontResalt} fontFamily="system-ui, -apple-system, sans-serif"
              fill="#1B3A6B" fontWeight="800" textAnchor="middle" dominantBaseline="central"
            >
              {humanizeName(matchedCanton.name)}
            </text>
          </g>
        )}

        {/* Etiquetas de otros cantones — ELIMINADAS para limpieza visual */}

        {/* Titulo: nombre de la provincia */}
        {showTitle && (
          <text
            x={bounds.minX + bw * 0.5} y={bounds.minY - bh * 0.14}
            fontSize={fontTitulo} fontFamily="system-ui, -apple-system, sans-serif"
            fill="#1B3A6B" fontWeight="700" textAnchor="middle" letterSpacing={scale * 0.003}
          >
            {matchedProvName}
          </text>
        )}
      </svg>
    </div>
  );
}
