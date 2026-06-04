/**
 * TaskCell — celda visual de tarea.
 * Estados: verde (entregada+calificada), amarillo (entregada sin calificar),
 *          rojo (retrasada), gris (pendiente).
 */
export default function TaskCell({ entregada, calificada, retrasada, title }) {
  let color;
  if (entregada && calificada) {
    color = "bg-green-400 border-green-500";
  } else if (entregada && !calificada) {
    color = "bg-amber-400 border-amber-500";
  } else if (retrasada) {
    color = "bg-red-400 border-red-500";
  } else {
    color = "bg-gray-200 border-gray-300";
  }

  return (
    <span
      title={title}
      className={`inline-block w-2.5 h-2.5 rounded-sm border ${color}`}
    />
  );
}
