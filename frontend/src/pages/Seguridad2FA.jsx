import { useState, useEffect } from "react";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";

/**
 * [WF3] Pantalla de gestión de 2FA (TOTP): enrolamiento con QR,
 * códigos de recuperación y desactivación.
 */
export default function Seguridad2FA() {
  const [status, setStatus] = useState(null);     // { enabled, recovery_codes_remaining }
  const [setupData, setSetupData] = useState(null); // { qr, secret }
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(null);  // códigos mostrados una sola vez
  const [pwd, setPwd] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const { user, isSuperAdmin, mustEnroll2FA, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [usuarios, setUsuarios] = useState([]);
  const [resetUserId, setResetUserId] = useState("");
  const [resetMsg, setResetMsg] = useState("");
  const [nuevoCorreo, setNuevoCorreo] = useState("");
  const [emailPwd, setEmailPwd] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [emailMsg, setEmailMsg] = useState("");

  const loadStatus = () => api.get2FAStatus().then(setStatus).catch(() => {});
  useEffect(() => { loadStatus(); }, []);
  useEffect(() => {
    if (isSuperAdmin) api.listUsers().then(setUsuarios).catch(() => setUsuarios([]));
  }, [isSuperAdmin]);

  const resetUsuario2FA = async () => {
    if (!resetUserId) return;
    setResetMsg(""); setBusy(true);
    try {
      const r = await api.resetUser2FA(resetUserId);
      setResetMsg(r.detail || "2FA reseteado");
      api.listUsers().then(setUsuarios).catch(() => {});
    } catch (e) { setResetMsg("Error: " + e.message); }
    finally { setBusy(false); }
  };

  const cambiarCorreo = async (e) => {
    e.preventDefault();
    setEmailMsg(""); setBusy(true);
    try {
      const r = await api.changeEmail(nuevoCorreo, emailPwd, emailCode || null);
      setEmailMsg("Correo actualizado a " + r.email);
      setNuevoCorreo(""); setEmailPwd(""); setEmailCode("");
      await refreshUser();
    } catch (err) { setEmailMsg("Error: " + err.message); }
    finally { setBusy(false); }
  };

  const startSetup = async () => {
    setErr(""); setMsg(""); setBusy(true);
    try { setSetupData(await api.setup2FA()); }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  };

  const confirmSetup = async (e) => {
    e.preventDefault();
    setErr(""); setMsg(""); setBusy(true);
    try {
      const r = await api.verifySetup2FA(code);
      setRecovery(r.recovery_codes);
      setSetupData(null); setCode("");
      await loadStatus();
      await refreshUser();
      setMsg("2FA activado correctamente. Guarda tus códigos de recuperación.");
      if (mustEnroll2FA) setTimeout(() => navigate("/dashboard"), 1500);
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  };

  const disable = async (e) => {
    e.preventDefault();
    setErr(""); setMsg(""); setBusy(true);
    try {
      await api.disable2FA(pwd);
      setPwd(""); setRecovery(null);
      await loadStatus();
      setMsg("2FA desactivado.");
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="max-w-xl mx-auto p-6">
      <h1 className="text-xl font-bold text-gray-800 mb-1">Autenticación en dos pasos (2FA)</h1>
      <p className="text-sm text-gray-500 mb-5">
        Añade un segundo factor con una app autenticadora (Google Authenticator, Microsoft Authenticator, etc.).
      </p>

      {mustEnroll2FA && (
        <div className="bg-amber-50 border border-amber-300 text-amber-800 rounded-lg px-4 py-3 text-sm mb-4">
          🔒 Tu organización exige 2FA. Debes activarlo aquí para poder usar el resto del sistema.
        </div>
      )}

      {status && (
        <div className={`rounded-lg px-4 py-3 text-sm mb-4 ${status.enabled ? "bg-green-50 text-green-700 border border-green-200" : "bg-gray-50 text-gray-600 border border-gray-200"}`}>
          Estado: <strong>{status.enabled ? "Activado" : "Desactivado"}</strong>
          {status.enabled && <> · Códigos de recuperación restantes: {status.recovery_codes_remaining}</>}
        </div>
      )}

      {msg && <div className="bg-blue-50 border border-blue-200 text-blue-700 rounded-lg px-4 py-3 text-sm mb-4">{msg}</div>}
      {err && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-4">{err}</div>}

      {recovery && (
        <div className="border border-amber-300 bg-amber-50 rounded-lg p-4 mb-4">
          <p className="text-sm font-semibold text-amber-800 mb-2">Códigos de recuperación (se muestran una sola vez)</p>
          <div className="grid grid-cols-2 gap-2 font-mono text-sm">
            {recovery.map(c => <span key={c} className="bg-white border rounded px-2 py-1 text-center">{c}</span>)}
          </div>
          <p className="text-xs text-amber-700 mt-2">Guárdalos en un lugar seguro. Cada uno sirve una sola vez.</p>
        </div>
      )}

      {/* Activar */}
      {status && !status.enabled && !setupData && (
        <button onClick={startSetup} disabled={busy}
          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-medium">
          {busy ? "Generando…" : "Activar 2FA"}
        </button>
      )}

      {setupData && (
        <div className="border border-gray-200 rounded-lg p-4">
          <p className="text-sm text-gray-700 mb-3">1) Escanea este código QR con tu app autenticadora:</p>
          <img src={setupData.qr} alt="QR 2FA" className="w-44 h-44 mx-auto mb-3" />
          <p className="text-xs text-gray-500 mb-3 text-center">
            ¿No puedes escanear? Clave manual: <code className="bg-gray-100 px-1 rounded">{setupData.secret}</code>
          </p>
          <form onSubmit={confirmSetup} className="space-y-3">
            <label className="block text-sm font-medium text-gray-700">2) Ingresa el código de 6 dígitos:</label>
            <input value={code} onChange={e => setCode(e.target.value)} inputMode="numeric"
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm tracking-widest text-center"
              placeholder="123456" required />
            <button type="submit" disabled={busy}
              className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white py-2.5 rounded-lg text-sm font-medium">
              {busy ? "Verificando…" : "Confirmar y activar"}
            </button>
          </form>
        </div>
      )}

      {/* Desactivar */}
      {status && status.enabled && (
        <form onSubmit={disable} className="border border-gray-200 rounded-lg p-4 mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">Desactivar 2FA (confirma con tu contraseña)</label>
          <input type="password" value={pwd} onChange={e => setPwd(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm mb-3" placeholder="Contraseña actual" required />
          <button type="submit" disabled={busy}
            className="bg-red-600 hover:bg-red-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-medium">
            Desactivar 2FA
          </button>
        </form>
      )}

      {isSuperAdmin && (
        <div className="border border-gray-200 rounded-lg p-4 mt-6">
          <h2 className="text-sm font-bold text-gray-800 mb-1">Resetear 2FA de un usuario (admin)</h2>
          <p className="text-xs text-gray-500 mb-3">
            Si un usuario perdió su dispositivo, desactiva su 2FA para que pueda volver a enrolarse.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <select value={resetUserId} onChange={e => setResetUserId(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm min-w-[240px]">
              <option value="">Selecciona un usuario…</option>
              {usuarios.map(u => (
                <option key={u.id} value={u.id}>{u.email} {u.role ? `(${u.role})` : ""}</option>
              ))}
            </select>
            <button onClick={resetUsuario2FA} disabled={busy || !resetUserId}
              className="bg-amber-600 hover:bg-amber-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium">
              Resetear 2FA
            </button>
          </div>
          {resetMsg && <p className="text-xs mt-2 text-gray-700">{resetMsg}</p>}
        </div>
      )}

      <form onSubmit={cambiarCorreo} className="border border-gray-200 rounded-lg p-4 mt-6">
        <h2 className="text-sm font-bold text-gray-800 mb-1">Cambiar mi correo</h2>
        <p className="text-xs text-gray-500 mb-3">
          Correo actual: <strong>{user?.email}</strong>. Requiere tu contraseña{user?.totp_enabled ? " y código 2FA" : ""}.
        </p>
        <div className="space-y-2">
          <input type="email" value={nuevoCorreo} onChange={e => setNuevoCorreo(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="nuevo@correo.com" required />
          <input type="password" value={emailPwd} onChange={e => setEmailPwd(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="Contraseña actual" required />
          {user?.totp_enabled && (
            <input type="text" inputMode="numeric" value={emailCode} onChange={e => setEmailCode(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm tracking-widest text-center"
              placeholder="Código 2FA" required />
          )}
          <button type="submit" disabled={busy}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-medium">
            Cambiar correo
          </button>
        </div>
        {emailMsg && (
          <div className={`text-sm mt-3 px-4 py-2 rounded-lg ${emailMsg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
            {emailMsg}
          </div>
        )}
      </form>
    </div>
  );
}
