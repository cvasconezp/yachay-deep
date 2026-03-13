/**
 * Mapa coroplético de Ecuador – vista centrada en la provincia del estudiante.
 * Muestra la provincia con sus límites y marca la ciudad de procedencia.
 *
 * Props:
 *   provincia  – nombre de la provincia (ej. "Imbabura")
 *   ciudad     – nombre de la ciudad/cantón (ej. "Otavalo")
 *   parroquia  – (opcional) nombre de la parroquia
 *   height     – altura del contenedor (default 160)
 */

// ── Paths SVG simplificados de las 23 provincias continentales ───────────────
const PROVINCE_PATHS = {
  "Azuay": "M78.8,269.2L89.4,259.3L85.1,255L87.3,251L93.4,249L94.7,243.4L98.1,245.3L97.5,241.8L101.6,244L101.9,239.4L111.2,249.2L119.6,249.8L121.9,246.6L129.8,256L134.7,255.1L137.5,246.2L143.7,246.5L149.6,239.3L151.4,243.6L154.7,240.5L157.9,243.8L148.9,248.2L142.4,271.8L122.2,287.5L119,302.5L113.3,291.6L106.9,293.1L104.3,285.6L84.7,284.6L88.4,275.6L78.9,269.4L78.8,269.2Z",
  "Bolívar": "M107,159.8L117.6,156.4L124.4,160.5L132,158.9L127.6,168.8L133,187.1L130.8,191.9L123.2,193.2L122.4,212.5L117.5,218.4L117,213.4L111.8,214.4L108.5,204.3L111.6,191.6L103,185.2L109.4,179.9L102.6,174.4L108.2,167L100.8,166.5L106.8,159.8L107,159.8Z",
  "Carchi": "M152.9,18.4L158.3,21.4L164.2,18L171.3,32.8L185.3,40L199.9,38.3L202.7,46.9L210.7,50L204.6,50.9L201.5,50.7L203.3,52.9L194,67.5L177.3,60L170.9,46.2L150.7,32.9L153,18.7L152.9,18.4Z",
  "Cañar": "M102.7,228L108.5,233.7L116,219.3L123.6,228.9L129.2,231.3L135,228.8L136.8,232.3L143.8,233.2L149.4,239.4L143.7,246.5L136.5,247.7L134.7,255.1L129.8,256L121.9,246.6L119.6,249.8L111.2,249.2L100.9,235.9L93.2,237.4L99.4,226.4L102.7,228L102.7,228Z",
  "Chimborazo": "M116.3,218.5L122.3,212.8L123.2,193.2L130.8,191.9L133,187.1L130.8,174.9L137.4,172.9L146.2,177.5L153.5,173.2L161.5,176.9L161.5,185.6L155.4,192L158,200.6L154.1,204.1L157.1,212.2L152.7,214.3L154.1,219.7L148.2,225.3L155.7,231.3L151.3,240L136,229.2L123.3,228.7L115.8,219.1L108.9,219.5L116,218.5L116.3,218.5Z",
  "Cotopaxi": "M119.1,121.9L124.6,120.6L122.8,114.5L127.4,108.1L133.8,119.5L139.6,121.6L140.7,127.7L154.1,124L160.3,139.3L156,152.3L149.6,152.1L149.4,155L126.4,160.3L117.6,156.4L107,159.8L103.9,154.9L105.3,145.1L118.8,122.3L119.1,121.9Z",
  "El Oro": "M64.9,280.6L71.2,268.7L78.8,269.2L88.4,275.6L84.7,284.6L96,284.4L98.7,291.8L94.6,301.6L98.7,299.8L102.1,303.4L99.7,312.3L90.9,313L87.4,309.8L75,315L57.1,318.1L53.5,311.3L50.6,293.1L65.2,289.9L64.9,281L64.9,280.6Z",
  "Esmeraldas": "M61.8,40L100.6,24.6L113.8,24L123.6,13.5L128.2,16.2L124.9,13.2L129.4,7.3L129.6,11.6L136.6,12.2L133,9.5L135.6,4.4L153.7,18.6L150.7,32.9L156.9,40.4L151.4,43L157.6,52.8L156.2,56.7L150.6,57.9L143.2,66.6L135.6,64.3L121.6,70.5L106.7,68.6L106.3,73.1L102.5,74.1L106,77.9L102.6,84.9L82,77.7L84.3,73.5L81,72.5L80.8,66.5L66.6,72.3L61.7,60.9L64.6,55L58.8,47.6L61.6,40.2L61.8,40Z",
  "Guayas": "M47.2,188.9L70.8,194.8L88.5,203.6L94.4,212.5L100.3,224.3L94.4,236.1L88.5,247.9L76.7,259.7L64.9,265.6L53.1,247.9L41.3,230.2L41.3,212.5L47.2,188.9Z",
  "Imbabura": "M107.6,69L121.6,70.5L135.6,64.3L144.2,66.2L157.6,54.7L151.4,43.1L156.4,41.9L156.2,36.8L170.9,46.2L177.3,60L189.7,65.6L194.2,67.6L190.4,76.4L169.2,81.3L163.4,76.6L160.8,79L160.3,73.7L127,76.5L120.5,70.4L107.9,69L107.6,69Z",
  "Loja": "M36.6,329.3L38.8,324.3L48.1,325.4L67.6,314.5L81.1,314.7L87.4,309.8L90.9,313L99.7,312.3L102.1,303.4L98.7,299.8L94.6,301.6L98.7,292.4L96.7,285L105.9,286.6L107.5,293.7L114.6,293.7L117.9,302.6L112.4,308.3L115.8,326.5L117.3,348.7L111.5,354.7L104.8,354.5L98.7,368.8L94.5,355.3L85.9,350.1L75.9,353.6L58.8,341.8L54.8,341.7L45.5,352L39,351.6L38.6,346.3L46.8,336.4L38.4,337L36.5,329.5L36.6,329.3Z",
  "Los Ríos": "M88.1,138.9L95.2,120.6L103.5,120.6L102.1,127L106.4,129.8L116.2,120.7L119.1,121.9L105.9,143.4L103.9,154.9L107,159.8L100.8,166.2L108.2,167L102.6,174.4L109.2,180.9L103,185.2L109.1,187.6L109.8,192.9L108.5,204.3L111.8,214.4L95.1,199.7L85.2,202.1L72.9,185.5L72.7,173.2L79.7,158.9L92.4,150.6L94.3,138.9L88.2,139.1L88.1,138.9Z",
  "Manabí": "M12.9,156.2L11.1,151L15.9,145L28.2,144.4L32.8,140.3L40.7,123.4L36.1,110.1L60.9,85.5L62.9,66.7L65.9,78.3L70.5,69.9L80.8,66.5L81,72.5L84.3,73.5L82,77.7L90.4,81.7L88,91.7L93.2,98.2L99.6,99.6L100.2,112.1L95.1,123.1L87.3,140L80.9,140.6L74.1,152.4L65.7,155.2L63.4,163.8L56.3,167L53.9,179.9L47.8,181.1L52.3,188.5L45.8,187.8L39.8,194.3L38.8,203.7L26.7,187.1L17.3,189.2L14.5,183L21.3,168.6L12.9,156.3L12.9,156.2Z",
  "Morona Santiago": "M150.1,239.6L155.7,231.3L148.2,225.3L154.1,219.7L152.6,214.7L157.2,212L154.1,204.1L159.5,197.9L155.4,192L161.5,185.6L160.7,179.2L172.3,174L178.2,177.2L181.7,187.4L189.5,188.3L193.3,201.8L199.8,208.1L224.1,217.5L236.5,226.2L242.3,237.1L249.7,239.6L260.1,242.5L186.3,269.5L171.3,287L174,294L169.4,295.4L168.5,289.2L162.3,287.3L161.2,297.1L145.7,297.1L142.6,300.3L133.7,297.8L126.6,283.3L141.4,273.1L149,256.7L146.5,252.9L148.9,248.2L157.9,243.8L154.6,240.4L150.5,243.1L150.1,239.7L150.1,239.6Z",
  "Napo": "M158.8,131.1L166.6,121.8L172.4,99.5L186.6,94.8L193.2,86.5L196.6,93.5L207.4,95L214.9,89.6L215.3,96.7L219.7,97.5L224.4,92.1L226.8,106.8L216.8,119.3L209.3,115.4L204.9,120.4L212.6,130.1L207,143L214.6,142.3L234.9,129.6L230.3,138.9L240.4,142.9L238.9,148L179.9,162.2L169.9,155.9L162.3,157.8L163.9,150L159,146.9L159,131.4L158.8,131.1Z",
  "Orellana": "M224.2,91.9L238.1,95.3L245.7,92L263.6,113.7L268.5,112.7L278.3,119.3L295.7,114.4L305.3,122.2L305,112.6L315.8,113.3L344.6,126.7L348.6,145.8L337.3,143.6L327,180.8L308.2,167.1L304.6,168.8L294.4,163.7L283.1,165.6L272.5,162.2L270.1,150.7L251.9,154L250.6,157.2L240,153.3L235.9,148.8L240.4,142.9L230.3,138.9L234.9,129.6L219.2,141.2L207,143L212.6,130.1L204.9,120.4L209.3,115.4L216.8,119.3L222.7,113.5L226.8,106.8L224.4,92.1L224.2,91.9Z",
  "Pastaza": "M172.3,174L175.9,160.2L189.5,162L198.6,156.3L208.7,156.9L215.4,152.1L221.8,153.7L235.6,148L250.3,157.2L251.9,154L270.1,150.7L269.9,159.2L279.1,163.5L308.2,167.1L325.5,180L298.4,213.9L260.1,242.5L257.4,239.3L245.3,239.4L236.5,226.2L224.1,217.5L199.8,208.1L193.3,201.8L189.5,188.3L181.7,187.4L178.2,177.2L172.6,174.1L172.3,174Z",
  "Pichincha": "M102.6,84.9L106,77.9L102.5,74.1L106.3,73.1L106.7,68.6L120.5,70.4L127,76.5L160.3,73.7L160.8,79L163.4,76.6L168.5,81.3L181.2,77.4L192.3,87.5L186.6,94.8L175.6,99.2L171.7,100.2L163.5,127.5L158.8,131.1L152.8,123.5L140.7,127.7L139.6,121.6L133.8,119.5L126.6,107.2L134.4,108.9L138.9,104.9L133.6,96.6L115.1,94L117.4,89.9L102.5,85L102.6,84.9Z",
  "Santa Elena": "M20.3,205.5L17.6,189.5L26.5,187L34.8,201.8L50.5,212.9L51.2,220.7L48.1,227.4L39.1,229.4L37.6,235.4L31.7,236.5L11.9,226.2L5.4,217.7L11.2,219.6L18.3,215.5L20.4,205.4L20.3,205.5Z",
  "Santo Domingo": "M90.4,81.7L116.6,89.5L115.1,94L133.5,96.5L138.9,104.9L134.4,108.9L126.8,107.1L122.9,114.2L123.2,122.4L116.9,120.5L103.3,129.2L103.6,120.7L95.4,120.6L100.2,112.1L99.6,99.6L93.2,98.2L88,91.7L90.1,82L90.4,81.7Z",
  "Sucumbíos": "M185,79.2L193,72.6L194.3,63.4L203.3,52.9L201.5,50.7L213,49.5L210.9,64.9L216.5,62.6L225,67.1L232.2,65.5L237.4,71.7L247.4,74L257.7,71.5L266.2,75.6L275.8,74.7L276.7,66.1L284.5,62.7L291.7,65.6L312.4,85.5L322.7,85.7L326.1,90.1L344.8,95.4L336,98.6L324.2,95L324,99.9L328.7,99.3L337.3,114.3L345.7,119.4L346.2,126.8L327.1,120.9L315.8,113.3L305,112.6L305.3,122.2L295.7,114.4L278.3,119.3L268.5,112.7L263.6,113.7L245.7,92L238.1,95.3L225,90.8L219.7,97.5L215.2,96.6L214.9,89.6L207.1,95L195.9,93.4L195.9,87.6L184.1,82.2L185,79.6L185,79.2Z",
  "Tungurahua": "M131.8,158.6L149.4,155L150,151L155.4,152.7L158.7,146.8L163.9,150L162.3,157.8L169.9,155.9L175.9,159L176.5,164L169.3,176.6L162.2,178.4L153.4,173.2L145.9,177.5L129.4,173.1L127.6,168.5L132,158.9L131.8,158.6Z",
  "Zamora Chinchipe": "M98.7,368.8L104.8,354.5L111.5,354.7L117.4,348.5L118,336.9L114.3,331.2L116.3,318L112.4,308.3L121.3,299.9L122.2,287.5L127.8,286.2L133.8,298L142.6,300.3L145.7,297.1L161.2,297.1L159.6,302.2L158.6,312.1L149.5,324.2L144.2,359.1L132.4,364L129,370.6L130.2,377.6L125.6,377.4L123,384.4L108.2,381.7L98.5,369.2L98.7,368.8Z",
};

// ── Coordenadas de ciudades/cantones para marcador ──────────────────────────
// Proyección: x = (lng + 81.1) * 59.0, y = (1.5 - lat) * 60.6
const CITY_COORDS = {
  quito:       { x: 155.4, y: 101.8 },
  cuenca:      { x: 124.2, y: 266.5 },
  guayaquil:   { x: 71.0,  y: 221.4 },
  cayambe:     { x: 174.0, y: 88.5 },
  latacunga:   { x: 146.5, y: 147.6 },
  otavalo:     { x: 166.9, y: 76.7 },
  riobamba:    { x: 143.1, y: 191.7 },
  ambato:      { x: 146.5, y: 166.5 },
  ibarra:      { x: 175.5, y: 69.6 },
  tulcan:      { x: 195.8, y: 41.7 },
  guaranda:    { x: 124.0, y: 187.6 },
  tena:        { x: 189.5, y: 151.2 },
  puyo:        { x: 181.0, y: 181.0 },
  macas:       { x: 171.0, y: 230.9 },
  "san gabriel": { x: 191.5, y: 54.4 },
  cotacachi:   { x: 168.7, y: 72.7 },
  tabacundo:   { x: 170.0, y: 87.8 },
  sangolqui:   { x: 159.5, y: 110.9 },
  machachi:    { x: 148.4, y: 122.3 },
  salcedo:     { x: 144.8, y: 154.6 },
  saquisili:   { x: 131.8, y: 140.8 },
  pujili:      { x: 124.4, y: 148.4 },
  sigchos:     { x: 120.0, y: 136.5 },
  loja:        { x: 107.5, y: 333.0 },
  zamora:      { x: 126.5, y: 327.0 },
  esmeraldas:  { x: 81.5,  y: 46.8 },
  portoviejo:  { x: 48.5,  y: 148.0 },
  "santo domingo": { x: 107.0, y: 106.5 },
  babahoyo:    { x: 97.0,  y: 180.0 },
  machala:     { x: 77.0,  y: 293.0 },
  "santa elena": { x: 27.5, y: 220.0 },
};

// ── Normalizar nombre para matching ──────────────────────────────────────────
function norm(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+de\s+los\s+/g, " ")
    .trim();
}

function findProvince(provincia) {
  if (!provincia) return null;
  const n = norm(provincia);
  for (const name of Object.keys(PROVINCE_PATHS)) {
    if (norm(name) === n) return name;
    if (norm(name).startsWith(n) || n.startsWith(norm(name))) return name;
  }
  return null;
}

function findCity(ciudad, parroquia) {
  for (const loc of [ciudad, parroquia]) {
    if (!loc) continue;
    const n = norm(loc);
    if (CITY_COORDS[n]) return { name: loc, ...CITY_COORDS[n] };
  }
  return null;
}

/** Extrae la bounding box de un SVG path (solo M/L absolutas) */
function getPathBBox(d) {
  const nums = [];
  const re = /[ML]\s*([\d.]+)\s*,\s*([\d.]+)/g;
  let match;
  while ((match = re.exec(d)) !== null) {
    nums.push({ x: parseFloat(match[1]), y: parseFloat(match[2]) });
  }
  if (nums.length === 0) return null;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of nums) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  return { minX, minY, maxX, maxY, w: maxX - minX, h: maxY - minY };
}

// ── Componente ───────────────────────────────────────────────────────────────
export default function EcuadorMap({ provincia, ciudad, parroquia, height = 160 }) {
  const matchedProv = findProvince(provincia);
  const matchedCity = findCity(ciudad, parroquia);
  const provPath = matchedProv ? PROVINCE_PATHS[matchedProv] : null;

  // Si hay provincia: zoom a esa provincia; si no, mostrar todo Ecuador
  const bbox = provPath ? getPathBBox(provPath) : null;

  let viewBox, showAllProvinces;
  if (bbox) {
    // Centrar en la provincia con padding
    const pad = Math.max(bbox.w, bbox.h) * 0.25;
    const vx = bbox.minX - pad;
    const vy = bbox.minY - pad;
    const vw = bbox.w + pad * 2;
    const vh = bbox.h + pad * 2;
    viewBox = `${vx} ${vy} ${vw} ${vh}`;
    showAllProvinces = false;
  } else {
    viewBox = "-5 -5 360 400";
    showAllProvinces = true;
  }

  // Escalar tamaños relativos al viewbox
  const scale = bbox ? Math.max(bbox.w, bbox.h) : 350;
  const markerR = scale * 0.035;
  const ringR = markerR * 2;
  const fontSize = scale * 0.065;
  const labelFontSize = scale * 0.05;
  const strokeW = scale * 0.005;

  return (
    <div className="relative" style={{ height }}>
      <svg
        viewBox={viewBox}
        className="w-full h-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Fondo */}
        {showAllProvinces ? (
          // Vista completa de Ecuador
          <>
            <rect x="-5" y="-5" width="360" height="400" fill="#F8FAFC" rx="4" />
            {Object.entries(PROVINCE_PATHS).map(([name, d]) => {
              const isHighlighted = name === matchedProv;
              return (
                <path
                  key={name}
                  d={d}
                  fill={isHighlighted ? "#1B3A6B" : "#E2E8F0"}
                  stroke={isHighlighted ? "#0F2749" : "#94A3B8"}
                  strokeWidth={isHighlighted ? 1.2 : 0.5}
                  opacity={isHighlighted ? 1 : 0.85}
                />
              );
            })}
          </>
        ) : (
          // Vista zoom a la provincia
          <>
            {/* Provincia resaltada */}
            <path
              d={provPath}
              fill="#1B3A6B"
              stroke="#0F2749"
              strokeWidth={strokeW * 1.5}
            />

            {/* Provincias vecinas como contexto, muy tenues */}
            {Object.entries(PROVINCE_PATHS).map(([name, d]) => {
              if (name === matchedProv) return null;
              return (
                <path
                  key={name}
                  d={d}
                  fill="#E8ECF0"
                  stroke="#CBD5E1"
                  strokeWidth={strokeW * 0.5}
                  opacity={0.5}
                />
              );
            })}

            {/* Re-dibujar la provincia encima para que no se tape */}
            <path
              d={provPath}
              fill="#1B3A6B"
              stroke="#0F2749"
              strokeWidth={strokeW * 1.5}
            />
          </>
        )}

        {/* Marcador de ciudad */}
        {matchedCity && (
          <g>
            {/* Anillo exterior */}
            <circle
              cx={matchedCity.x}
              cy={matchedCity.y}
              r={ringR}
              fill="none"
              stroke="#F0B000"
              strokeWidth={strokeW * 1.5}
              opacity="0.7"
            />
            {/* Punto central */}
            <circle
              cx={matchedCity.x}
              cy={matchedCity.y}
              r={markerR}
              fill="#F0B000"
              stroke="white"
              strokeWidth={strokeW}
            />
            {/* Nombre de la ciudad */}
            <text
              x={matchedCity.x + ringR + scale * 0.02}
              y={matchedCity.y + labelFontSize * 0.35}
              fontSize={labelFontSize}
              fontFamily="Calibri, Arial, sans-serif"
              fill="white"
              fontWeight="700"
              stroke="#1B3A6B"
              strokeWidth={labelFontSize * 0.25}
              paintOrder="stroke"
            >
              {matchedCity.name}
            </text>
          </g>
        )}

        {/* Label de provincia */}
        {matchedProv && !showAllProvinces && bbox && (
          <text
            x={bbox.minX + bbox.w * 0.5}
            y={bbox.minY - Math.max(bbox.w, bbox.h) * 0.12}
            fontSize={fontSize}
            fontFamily="Calibri, Arial, sans-serif"
            fill="#1B3A6B"
            fontWeight="700"
            textAnchor="middle"
          >
            {matchedProv}
          </text>
        )}

        {/* Labels para vista completa */}
        {showAllProvinces && matchedProv && (
          <text x="5" y="392" fontSize="9" fontFamily="Calibri, Arial, sans-serif" fill="#1B3A6B" fontWeight="600">
            {matchedProv}
          </text>
        )}
        {showAllProvinces && matchedCity && (
          <text x="350" y="392" fontSize="8" fontFamily="Calibri, Arial, sans-serif" fill="#F0B000" fontWeight="600" textAnchor="end">
            ● {matchedCity.name}
          </text>
        )}
      </svg>
    </div>
  );
}
