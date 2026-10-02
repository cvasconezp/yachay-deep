// Enlaces al Aula Virtual (AVAC) por período.
//
// La URL de AVAC cambia de "grado" según el período (grado68, grado69, ...).
// Donde hay un período disponible (páginas con selector, Ficha), se deriva de él.
// Donde la vista opera sobre el período vigente y no tiene uno a mano, se usa
// GRADO_VIGENTE como respaldo: al iniciar un nuevo período basta con cambiar ESTE
// valor (antes el "grado68" estaba repetido y fijo en 5 lugares).
export const GRADO_VIGENTE = "69";

export function avacGrado(periodo) {
  const m = String(periodo ?? "").match(/\d+/);
  return m ? m[0] : GRADO_VIGENTE;
}

export function avacCourseUrl(codigo, periodo) {
  return `https://avac.ups.edu.ec/grado${avacGrado(periodo)}/course/search.php` +
    `?areaids=core_course-course&q=${encodeURIComponent(codigo)}`;
}
