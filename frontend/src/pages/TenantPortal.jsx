/**
 * TenantPortal — Super-admin portal for managing tenant instances.
 * Shown on yachaydeep.com (root domain) after admin login.
 * Allows jumping between subdomain instances.
 */
import { useState, useEffect } from "react";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";
import { YachayLogo } from "../components/YachayLogo";

// Tenant configs — extend as new tenants are added
const TENANT_CONFIGS = {
  ups: {
    name: "Universidad Politécnica Salesiana",
    short: "UPS",
    color: "from-blue-600 to-blue-800",
    accent: "bg-blue-500",
    icon: "🎓",
    description: "Producción — datos reales de AVAC",
    status: "active",
  },
  demo: {
    name: "Instancia Demo",
    short: "DEMO",
    color: "from-amber-500 to-orange-600",
    accent: "bg-amber-500",
    icon: "🧪",
    description: "Datos anonimizados para presentaciones",
    status: "active",
  },
};

function TenantCard({ tenant, code, onNavigate, isSuperAdmin = false }) {
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoMsg, setDemoMsg] = useState("");
  const isDemo = code === "demo";

  const regenDemo = async (e) => {
    e.stopPropagation();
    if (!window.confirm("Esto BORRARÁ los datos del demo y generará ~1000 estudiantes sintéticos (1-2 min). ¿Continuar?")) return;
    setDemoBusy(true); setDemoMsg("");
    try {
      const r = await api.regenerateDemoSynthetic(1000);
      const c = r.creados || {};
      setDemoMsg(`Listo: ${c.estudiantes} estudiantes, ${c.calificaciones} notas, ${c.alertas} alertas.`);
    } catch (err) { setDemoMsg("Error: " + err.message); }
    finally { setDemoBusy(false); }
  };
  const config = TENANT_CONFIGS[code] || {
    name: tenant?.nombre || code,
    short: code.toUpperCase(),
    color: "from-gray-500 to-gray-700",
    accent: "bg-gray-500",
    icon: "🏛️",
    description: "",
    status: "active",
  };

  const subdomain = `https://${code}.yachaydeep.com`;
  const ROLE_BTNS = [
    { role: "coordinador", label: "Coordinador" },
    { role: "docente", label: "Docente" },
    { role: "monitor", label: "Monitor" },
  ];

  return (
    <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
      <div className={`h-2 bg-gradient-to-r ${config.color}`} />
      <div className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{config.icon}</span>
            <div>
              <h3 className="font-bold text-gray-900 text-lg leading-tight">{config.name}</h3>
              <span className={`inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium text-white ${config.accent}`}>{config.short}</span>
            </div>
          </div>
          <div className={`w-3 h-3 rounded-full ${config.status === "active" ? "bg-green-400" : "bg-gray-300"} ring-2 ring-offset-2 ${config.status === "active" ? "ring-green-200" : "ring-gray-100"}`} />
        </div>

        {config.description && <p className="text-sm text-gray-500 mb-3">{config.description}</p>}
        <p className="text-xs text-gray-400 font-mono mb-4">{code}.yachaydeep.com</p>

        {/* Acciones (estilo Kullki): ingresar como admin o entrar en vista de un rol */}
        <div className="flex flex-wrap gap-2">
          <button onClick={() => onNavigate(subdomain, null)}
            className="bg-brand text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-brand-dark transition-colors">
            Ingresar →
          </button>
          {isSuperAdmin && ROLE_BTNS.map(b => (
            <button key={b.role} onClick={() => onNavigate(subdomain, b.role)}
              title={`Entrar a ${config.short} viendo como ${b.label}`}
              className="border border-gray-300 text-gray-600 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-gray-50 transition-colors">
              👁️ {b.label}
            </button>
          ))}
        </div>

        {isSuperAdmin && isDemo && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <button onClick={regenDemo} disabled={demoBusy}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded-lg text-xs font-medium">
              {demoBusy ? "Regenerando… (1-2 min)" : "↻ Regenerar demo (1000)"}
            </button>
            {demoMsg && <p className={`text-[11px] mt-1 ${demoMsg.startsWith("Error") ? "text-red-600" : "text-green-700"}`}>{demoMsg}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

export default function TenantPortal() {
  const { realIsSuperAdmin } = useAuth();
  const [institutions, setInstitutions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getInstitutions()
      .then((data) => setInstitutions(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleNavigate = (url, viewAs) => {
    window.location.href = viewAs ? `${url}/dashboard?view_as=${viewAs}` : url;
  };

  // Merge API institutions with hardcoded tenant configs
  const tenantCodes = Object.keys(TENANT_CONFIGS);
  // Add any institutions from API that aren't in TENANT_CONFIGS
  institutions.forEach((inst) => {
    if (inst.codigo && !tenantCodes.includes(inst.codigo)) {
      tenantCodes.push(inst.codigo);
    }
  });

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Portal de Administración</h1>
        <p className="text-gray-500 mt-1">
          Selecciona una instancia para gestionar. Cada subdominio opera con datos independientes.
        </p>
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">Cargando instancias...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {tenantCodes.map((code) => {
            const inst = institutions.find((i) => i.codigo === code);
            return (
              <TenantCard
                key={code}
                code={code}
                tenant={inst}
                onNavigate={handleNavigate}
                isSuperAdmin={realIsSuperAdmin}
              />
            );
          })}

          <button
            onClick={() => { window.location.href = "/core/kapak"; }}
            className="border-2 border-dashed border-gray-300 rounded-2xl p-6 flex flex-col items-center justify-center gap-2 text-gray-400 hover:border-brand-gold hover:text-brand-gold transition-colors min-h-[200px]"
          >
            <span className="text-4xl">+</span>
            <span className="text-sm font-medium">Nueva instancia</span>
          </button>
        </div>
      )}
    </div>
  );
}
