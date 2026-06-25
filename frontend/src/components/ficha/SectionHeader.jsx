/**
 * SectionHeader — encabezado de sección azul oscuro (Épica 1.5).
 */
export default function SectionHeader({ children, className = "" }) {
  return (
    <div className={`bg-[#1B3A6B] text-white px-3 py-1 text-[10px] font-bold uppercase tracking-wider ${className}`}>
      {children}
    </div>
  );
}
