// frontend/src/hooks/useLandscapeEnforcer.js
// Fuerza orientación horizontal en móviles después del login.
// - Android Chrome: bloquea la orientación con la Screen Orientation API
// - iOS Safari: muestra un overlay pidiendo rotar (la API no está disponible)

import { useEffect, useState } from "react";

export function useLandscapeEnforcer(active = true) {
  const [showOverlay, setShowOverlay] = useState(false);

  useEffect(() => {
    if (!active) {
      setShowOverlay(false);
      return;
    }

    // Intenta bloquear orientación con la API nativa (Android/PWA)
    const tryLock = async () => {
      try {
        if (screen.orientation && screen.orientation.lock) {
          await screen.orientation.lock("landscape");
          setShowOverlay(false); // Bloqueó exitosamente, no se necesita overlay
        } else {
          checkOrientation(); // API no disponible, usar overlay
        }
      } catch {
        // La API existe pero falló (ej. iOS, desktop) → usar overlay
        checkOrientation();
      }
    };

    // Evalúa si se debe mostrar el overlay según la orientación actual
    const checkOrientation = () => {
      const isMobile = window.innerWidth < 1024 || "ontouchstart" in window;
      if (!isMobile) {
        setShowOverlay(false);
        return;
      }
      const isPortrait = window.innerHeight > window.innerWidth;
      setShowOverlay(isPortrait);
    };

    tryLock();

    window.addEventListener("resize", checkOrientation);
    window.addEventListener("orientationchange", checkOrientation);

    return () => {
      window.removeEventListener("resize", checkOrientation);
      window.removeEventListener("orientationchange", checkOrientation);
      // Libera el bloqueo al desmontar
      try {
        if (screen.orientation && screen.orientation.unlock) {
          screen.orientation.unlock();
        }
      } catch {}
    };
  }, [active]);

  return showOverlay;
}
