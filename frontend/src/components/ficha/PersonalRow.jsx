/**
 * PersonalRow — fila de dato personal en tabla compacta (Épica 1.5).
 */
export default function PersonalRow({ label, value, href, warning }) {
  if (value == null || value === "" || value === "nan") {
    return (
      <tr>
        <td className="text-right text-[11px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">{label}</td>
        <td className="text-[11px] text-gray-300 italic px-2 py-0.5 border border-gray-200">—</td>
      </tr>
    );
  }
  return (
    <tr className={warning ? "bg-red-50" : ""}>
      <td className="text-right text-[11px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">{label}</td>
      <td className="text-[11px] px-2 py-0.5 border border-gray-200">
        {href ? (
          <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">{value}</a>
        ) : (
          <span className="text-gray-700">{value}</span>
        )}
      </td>
    </tr>
  );
}
