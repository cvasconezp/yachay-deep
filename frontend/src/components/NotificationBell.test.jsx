import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import NotificationBell from "./NotificationBell";

// Mock api
vi.mock("../services/api", () => ({
  api: {
    getAlertsPending: vi.fn().mockResolvedValue([]),
    markAlertRead: vi.fn().mockResolvedValue({}),
  },
}));

// Mock navigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderBell(props = {}) {
  return render(
    <MemoryRouter>
      <NotificationBell alertCount={5} criticoCount={2} {...props} />
    </MemoryRouter>
  );
}

describe("NotificationBell", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("muestra badge con conteo", () => {
    renderBell();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("no muestra badge con conteo 0", () => {
    renderBell({ alertCount: 0, criticoCount: 0 });
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("muestra 99+ para conteos altos", () => {
    renderBell({ alertCount: 150, criticoCount: 0 });
    expect(screen.getByText("99+")).toBeInTheDocument();
  });

  it("abre panel al hacer clic", async () => {
    renderBell();
    const bell = screen.getByTitle("5 alertas pendientes");
    fireEvent.click(bell);
    await waitFor(() => {
      expect(screen.getByText("Notificaciones")).toBeInTheDocument();
    });
  });

  it("muestra estado vacío cuando no hay alertas", async () => {
    renderBell();
    fireEvent.click(screen.getByTitle("5 alertas pendientes"));
    await waitFor(() => {
      expect(screen.getByText("Sin alertas pendientes")).toBeInTheDocument();
    });
  });

  it("muestra alertas cuando hay datos", async () => {
    const { api } = await import("../services/api");
    api.getAlertsPending.mockResolvedValueOnce([
      { id: 1, student_id: 10, student_nombre: "Juan Pérez", tipo: "inactividad", severidad: "critico", mensaje: "Sin acceso 15 días", created_at: new Date().toISOString() },
      { id: 2, student_id: 11, student_nombre: "Ana López", tipo: "tareas_bajas", severidad: "alto", mensaje: "Solo 20% tareas", created_at: new Date().toISOString() },
    ]);

    renderBell();
    fireEvent.click(screen.getByTitle("5 alertas pendientes"));

    await waitFor(() => {
      expect(screen.getByText("Juan Pérez")).toBeInTheDocument();
      expect(screen.getByText("Ana López")).toBeInTheDocument();
    });
  });

  it("navega a ver todas las alertas", async () => {
    renderBell();
    fireEvent.click(screen.getByTitle("5 alertas pendientes"));
    await waitFor(() => {
      expect(screen.getByText(/Ver todas las alertas/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Ver todas las alertas/));
    expect(mockNavigate).toHaveBeenCalledWith("/alertas");
  });
});
