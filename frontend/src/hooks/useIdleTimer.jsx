import { useEffect, useRef, useCallback } from "react";

const EVENTS = ["mousemove", "mousedown", "keydown", "touchstart", "scroll", "wheel"];

/**
 * Hook que detecta inactividad del usuario.
 * @param {number} timeoutMs - Milisegundos de inactividad antes de disparar onIdle (default 5 min)
 * @param {Function} onIdle - Callback cuando el usuario está inactivo
 * @param {Function} onActive - Callback cuando el usuario vuelve a estar activo (opcional)
 * @param {boolean} enabled - Si false, el timer no corre (default true)
 */
export function useIdleTimer({ timeoutMs = 5 * 60 * 1000, onIdle, onActive, enabled = true }) {
  const timerRef = useRef(null);
  const isIdleRef = useRef(false);

  const resetTimer = useCallback(() => {
    if (!enabled) return;

    if (isIdleRef.current && onActive) {
      onActive();
    }
    isIdleRef.current = false;

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      isIdleRef.current = true;
      onIdle?.();
    }, timeoutMs);
  }, [timeoutMs, onIdle, onActive, enabled]);

  useEffect(() => {
    if (!enabled) {
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    // Iniciar timer al montar
    resetTimer();

    // Escuchar eventos de actividad
    for (const ev of EVENTS) {
      window.addEventListener(ev, resetTimer, { passive: true });
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      for (const ev of EVENTS) {
        window.removeEventListener(ev, resetTimer);
      }
    };
  }, [resetTimer, enabled]);

  return { resetTimer };
}
