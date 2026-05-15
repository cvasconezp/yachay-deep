/**
 * TaskCell — celda visual de tarea (entregada/retrasada/pendiente).
 */
export default function TaskCell({ entregada, retrasada, title }) {
  return (
    <span
      title={title}
      className={`inline-block w-2.5 h-2.5 rounded-sm border ${
        entregada ? "bg-green-400 border-green-500"
        : retrasada ? "bg-red-400 border-red-500"
        : "bg-gray-200 border-gray-300"
      }`}
    />
  );
}
