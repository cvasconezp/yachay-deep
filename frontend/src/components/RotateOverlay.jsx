// frontend/src/components/RotateOverlay.jsx
// Overlay que cubre la pantalla cuando el dispositivo está en vertical
// Solo se muestra en móviles cuando useLandscapeEnforcer lo activa

export function RotateOverlay() {
  return (
    <div
      style={{ zIndex: 9999 }}
      className="fixed inset-0 bg-brand flex flex-col items-center justify-center text-white text-center px-8"
    >
      {/* Ícono de rotación animado */}
      <div className="mb-6 animate-spin-slow">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="w-20 h-20 opacity-90"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18h3"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M16.5 12a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z"
          />
        </svg>
      </div>

      <h2 className="text-xl font-bold mb-2">Gira tu dispositivo</h2>
      <p className="text-sm opacity-75">
        Yachay Deep está optimizado para usarse en modo horizontal.
        Por favor, rota tu pantalla para continuar.
      </p>
    </div>
  );
}
