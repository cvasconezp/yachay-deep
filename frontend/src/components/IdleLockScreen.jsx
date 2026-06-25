import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "../services/api";

/**
 * Pantalla de bloqueo por inactividad.
 * Muestra el iceberg animado (goteo de agua) y pide PIN de 6 dígitos.
 * Tras 3 intentos fallidos → logout.
 */
export default function IdleLockScreen({ onUnlock, onLogout, userName }) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [attempts, setAttempts] = useState(0);
  const [verifying, setVerifying] = useState(false);
  const [showPin, setShowPin] = useState(false);
  const inputRef = useRef(null);

  // Al aparecer, mostrar PIN input después de un momento
  useEffect(() => {
    const t = setTimeout(() => setShowPin(true), 800);
    return () => clearTimeout(t);
  }, []);

  // Focus al input cuando aparece
  useEffect(() => {
    if (showPin && inputRef.current) inputRef.current.focus();
  }, [showPin]);

  const handleSubmit = useCallback(async (e) => {
    e?.preventDefault();
    if (pin.length !== 6 || verifying) return;

    setVerifying(true);
    setError("");

    try {
      await api.verifyPin(pin);
      onUnlock();
    } catch (err) {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);
      setPin("");

      if (newAttempts >= 3) {
        setError("Demasiados intentos. Cerrando sesión...");
        setTimeout(() => onLogout(), 1500);
      } else {
        setError(`PIN incorrecto (intento ${newAttempts}/3)`);
        inputRef.current?.focus();
      }
    } finally {
      setVerifying(false);
    }
  }, [pin, attempts, verifying, onUnlock, onLogout]);

  // Handle digit input
  const handleChange = (e) => {
    const val = e.target.value.replace(/\D/g, "").slice(0, 6);
    setPin(val);
    setError("");
  };

  // Auto-submit cuando se completan 6 dígitos
  useEffect(() => {
    if (pin.length === 6) {
      handleSubmit();
    }
  }, [pin]); // eslint-disable-line react-hooks/exhaustive-deps

  const firstName = userName?.split(" ").slice(-1)[0] || "Usuario";
  const capitalName = firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase();

  return (
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center"
      style={{ background: "linear-gradient(180deg, #0a1628 0%, #1b3a6b 40%, #2d6ca3 70%, #5ea9d5 100%)" }}
      onMouseMove={() => {}} // absorber eventos
      onKeyDown={(e) => { if (e.key === "Escape") e.preventDefault(); }}
    >
      {/* Estrellas de fondo */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {Array.from({ length: 30 }).map((_, i) => (
          <div
            key={i}
            className="absolute rounded-full bg-white"
            style={{
              width: Math.random() * 2 + 1,
              height: Math.random() * 2 + 1,
              top: `${Math.random() * 40}%`,
              left: `${Math.random() * 100}%`,
              opacity: Math.random() * 0.6 + 0.2,
              animation: `twinkle ${2 + Math.random() * 3}s ease-in-out infinite`,
              animationDelay: `${Math.random() * 3}s`,
            }}
          />
        ))}
      </div>

      {/* Iceberg animado */}
      <div className="relative mb-8" style={{ animation: "float 4s ease-in-out infinite" }}>
        <img
          src="/yachay-favicon.svg"
          alt="Yachay Deep"
          className="w-32 h-32 drop-shadow-2xl"
          style={{ filter: "drop-shadow(0 0 20px rgba(94, 169, 213, 0.4))" }}
        />
        {/* Gotas de agua */}
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="absolute rounded-full"
            style={{
              width: 4,
              height: 6,
              background: "rgba(168, 220, 232, 0.8)",
              bottom: -8,
              left: `${35 + i * 15}%`,
              animation: `drip ${1.8 + i * 0.4}s ease-in infinite`,
              animationDelay: `${i * 0.6}s`,
            }}
          />
        ))}
      </div>

      {/* Nombre + estado */}
      <p className="text-white/60 text-sm mb-1">Sesión suspendida</p>
      <p className="text-white text-xl font-semibold mb-8">{capitalName}</p>

      {/* PIN Input */}
      <div
        className={`transition-all duration-500 ${showPin ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}
      >
        <form onSubmit={handleSubmit} className="flex flex-col items-center gap-4">
          <p className="text-white/70 text-sm">Ingresa tu PIN para continuar</p>

          {/* 6 digit boxes */}
          <div className="relative">
            <div className="flex gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className={`w-11 h-14 rounded-lg border-2 flex items-center justify-center text-2xl font-bold transition-all duration-200 ${
                    i < pin.length
                      ? "border-[#e8a838] bg-white/15 text-white"
                      : i === pin.length
                        ? "border-white/60 bg-white/10"
                        : "border-white/20 bg-white/5"
                  }`}
                >
                  {i < pin.length ? "•" : ""}
                </div>
              ))}
            </div>
            {/* Hidden real input */}
            <input
              ref={inputRef}
              type="tel"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={pin}
              onChange={handleChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-default"
              autoComplete="off"
              autoFocus
            />
          </div>

          {/* Error */}
          {error && (
            <p className={`text-sm font-medium ${attempts >= 3 ? "text-red-400" : "text-amber-400"}`}>
              {error}
            </p>
          )}

          {/* Loading */}
          {verifying && (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          )}
        </form>
      </div>

      {/* Hora */}
      <Clock />

      {/* CSS Animations */}
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
        @keyframes drip {
          0% { opacity: 0.8; transform: translateY(0) scale(1); }
          60% { opacity: 0.6; transform: translateY(40px) scale(0.8); }
          100% { opacity: 0; transform: translateY(80px) scale(0.4); }
        }
        @keyframes twinkle {
          0%, 100% { opacity: 0.2; }
          50% { opacity: 0.8; }
        }
      `}</style>
    </div>
  );
}

/** Reloj sutil en la parte inferior */
function Clock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const iv = setInterval(() => setTime(new Date()), 60_000);
    return () => clearInterval(iv);
  }, []);

  return (
    <p className="absolute bottom-8 text-white/40 text-sm tracking-wider">
      {time.toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" })}
    </p>
  );
}
