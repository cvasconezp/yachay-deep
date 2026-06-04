import { useState, useRef, useEffect } from "react";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";

/**
 * Modal para configurar, cambiar o eliminar el PIN de 6 dígitos.
 * Se muestra desde el sidebar (Layout.jsx).
 */
export default function PinSetupModal({ open, onClose }) {
  const { user, refreshUser } = useAuth();
  const hasPin = user?.has_pin;

  const [mode, setMode] = useState(hasPin ? "manage" : "setup"); // "setup" | "manage"
  const [pin, setPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [password, setPassword] = useState("");
  const [step, setStep] = useState(1); // 1: password, 2: pin, 3: confirm
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  // Reset state on open
  useEffect(() => {
    if (open) {
      setMode(hasPin ? "manage" : "setup");
      setPin("");
      setConfirmPin("");
      setPassword("");
      setStep(1);
      setError("");
      setSuccess("");
      setLoading(false);
    }
  }, [open, hasPin]);

  // Focus input on step change
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open, step]);

  if (!open) return null;

  const handleSetPin = async () => {
    if (pin !== confirmPin) {
      setError("Los PINs no coinciden");
      setConfirmPin("");
      setStep(3);
      return;
    }
    setLoading(true);
    setError("");
    try {
      await api.setPin(pin, password);
      await refreshUser();
      setSuccess(hasPin ? "PIN actualizado correctamente" : "PIN configurado correctamente");
      setTimeout(() => onClose(), 1500);
    } catch (err) {
      setError(err.message || "Error al configurar PIN");
      setStep(1);
      setPassword("");
      setPin("");
      setConfirmPin("");
    } finally {
      setLoading(false);
    }
  };

  const handleRemovePin = async () => {
    setLoading(true);
    setError("");
    try {
      await api.removePin();
      await refreshUser();
      setSuccess("PIN eliminado. La pantalla de bloqueo se ha desactivado.");
      setTimeout(() => onClose(), 1500);
    } catch (err) {
      setError(err.message || "Error al eliminar PIN");
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    if (step === 1 && password.length < 1) {
      setError("Ingresa tu contraseña");
      return;
    }
    if (step === 2 && pin.length !== 6) {
      setError("El PIN debe ser de 6 dígitos");
      return;
    }
    if (step === 3) {
      handleSetPin();
      return;
    }
    setError("");
    setStep(step + 1);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleNext();
    if (e.key === "Escape") onClose();
  };

  // Manage mode: show options
  if (mode === "manage" && step === 1 && !success) {
    return (
      <Overlay onClose={onClose}>
        <h3 className="text-lg font-semibold text-gray-800 mb-1">PIN de bloqueo</h3>
        <p className="text-sm text-gray-500 mb-5">
          Tu PIN está configurado. La pantalla se bloqueará tras 5 min de inactividad.
        </p>
        <div className="space-y-2">
          <button
            onClick={() => { setMode("setup"); setStep(1); }}
            className="w-full py-2.5 px-4 rounded-lg bg-brand text-white font-medium hover:bg-brand-dark transition-colors text-sm"
          >
            Cambiar PIN
          </button>
          <button
            onClick={handleRemovePin}
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-lg border border-red-300 text-red-600 font-medium hover:bg-red-50 transition-colors text-sm disabled:opacity-50"
          >
            {loading ? "Eliminando..." : "Eliminar PIN"}
          </button>
        </div>
        {error && <p className="text-sm text-red-500 mt-3">{error}</p>}
      </Overlay>
    );
  }

  return (
    <Overlay onClose={onClose}>
      <h3 className="text-lg font-semibold text-gray-800 mb-1">
        {hasPin ? "Cambiar PIN" : "Configurar PIN de bloqueo"}
      </h3>
      <p className="text-sm text-gray-500 mb-5">
        {step === 1 && "Ingresa tu contraseña para verificar tu identidad."}
        {step === 2 && "Elige un PIN de 6 dígitos para desbloqueo rápido."}
        {step === 3 && "Confirma tu PIN."}
      </p>

      {success ? (
        <div className="flex items-center gap-2 py-3 px-4 bg-green-50 rounded-lg text-green-700 text-sm">
          <span>✓</span> {success}
        </div>
      ) : (
        <div onKeyDown={handleKeyDown}>
          {step === 1 && (
            <input
              ref={inputRef}
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(""); }}
              placeholder="Tu contraseña actual"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-gold focus:border-brand-gold outline-none text-sm"
              autoComplete="current-password"
            />
          )}
          {step === 2 && (
            <PinInput value={pin} onChange={(v) => { setPin(v); setError(""); }} ref={inputRef} />
          )}
          {step === 3 && (
            <PinInput value={confirmPin} onChange={(v) => { setConfirmPin(v); setError(""); }} ref={inputRef} />
          )}

          {error && <p className="text-sm text-red-500 mt-2">{error}</p>}

          <div className="flex gap-2 mt-5">
            {step > 1 && (
              <button
                onClick={() => setStep(step - 1)}
                className="flex-1 py-2.5 px-4 rounded-lg border border-gray-300 text-gray-600 font-medium hover:bg-gray-50 transition-colors text-sm"
              >
                Atrás
              </button>
            )}
            <button
              onClick={handleNext}
              disabled={loading}
              className="flex-1 py-2.5 px-4 rounded-lg bg-brand text-white font-medium hover:bg-brand-dark transition-colors text-sm disabled:opacity-50"
            >
              {loading ? "..." : step === 3 ? "Guardar PIN" : "Siguiente"}
            </button>
          </div>

          {/* Step indicators */}
          <div className="flex justify-center gap-1.5 mt-4">
            {[1, 2, 3].map((s) => (
              <div key={s} className={`w-2 h-2 rounded-full transition-colors ${s === step ? "bg-brand-gold" : s < step ? "bg-brand" : "bg-gray-200"}`} />
            ))}
          </div>
        </div>
      )}
    </Overlay>
  );
}

/** Overlay backdrop */
function Overlay({ children, onClose }) {
  return (
    <div className="fixed inset-0 z-[9990] flex items-center justify-center bg-black/60 backdrop-blur-md" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6 relative animate-in"
        onClick={(e) => e.stopPropagation()}
      >
        <button onClick={onClose} className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 text-lg">✕</button>
        {children}
        <style>{`
          @keyframes animate-in {
            from { opacity: 0; transform: scale(0.95) translateY(10px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
          }
          .animate-in { animation: animate-in 0.2s ease-out; }
        `}</style>
      </div>
    </div>
  );
}

/** Visual PIN input with 6 digit boxes */
import { forwardRef } from "react";

const PinInput = forwardRef(function PinInput({ value, onChange }, ref) {
  const handleChange = (e) => {
    const v = e.target.value.replace(/\D/g, "").slice(0, 6);
    onChange(v);
  };

  return (
    <div className="relative">
      <div className="flex gap-2 justify-center">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className={`w-10 h-12 rounded-lg border-2 flex items-center justify-center text-xl font-bold transition-all ${
              i < value.length
                ? "border-brand-gold bg-brand-gold/10 text-brand-dark"
                : i === value.length
                  ? "border-brand bg-blue-50"
                  : "border-gray-200 bg-gray-50"
            }`}
          >
            {i < value.length ? "•" : ""}
          </div>
        ))}
      </div>
      <input
        ref={ref}
        type="tel"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={6}
        value={value}
        onChange={handleChange}
        className="absolute inset-0 w-full h-full opacity-0 cursor-default"
        autoComplete="off"
      />
    </div>
  );
});
