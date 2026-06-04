/**
 * Tests: Layout
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Layout } from "./Layout.jsx";

vi.mock("../hooks/useAuth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../services/api", () => ({
  api: { getAlertCount: vi.fn() },
}));

import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";

function renderLayout(authOverrides = {}, alertData = { critico: 0, alto: 0 }) {
  useAuth.mockReturnValue({
    user: { nombre: "Carlos Test", role: "admin", email: "c@test.com" },
    logout: vi.fn(),
    isAdmin: true,
    ...authOverrides,
  });
  api.getAlertCount.mockResolvedValue(alertData);

  return render(
    <MemoryRouter>
      <Layout><div data-testid="content">Child Content</div></Layout>
    </MemoryRouter>
  );
}

describe("Layout", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renderiza children", async () => {
    renderLayout();
    await waitFor(() => {});
    expect(screen.getByTestId("content")).toBeInTheDocument();
    expect(screen.getByText("Child Content")).toBeInTheDocument();
  });

  it("muestra nombre de usuario", async () => {
    renderLayout();
    await waitFor(() => {});
    expect(screen.getByText("Carlos Test")).toBeInTheDocument();
  });

  it("muestra items de navegación", async () => {
    renderLayout();
    await waitFor(() => {});
    expect(screen.getByText("Estudiantes")).toBeInTheDocument();
    expect(screen.getByText("Ficha Estudiante")).toBeInTheDocument();
    expect(screen.getByText("Alertas")).toBeInTheDocument();
  });

  it("muestra Administración para admin", async () => {
    renderLayout({ isAdmin: true });
    await waitFor(() => {});
    expect(screen.getByText("Administración")).toBeInTheDocument();
  });

  it("oculta Administración para monitor", async () => {
    renderLayout({ isAdmin: false });
    await waitFor(() => {});
    expect(screen.queryByText("Administración")).not.toBeInTheDocument();
  });

  it("muestra el logo de marca (link al inicio)", async () => {
    renderLayout();
    await waitFor(() => {});
    expect(
      screen.getByLabelText("Ir al inicio de Yachay Deep")
    ).toBeInTheDocument();
  });

  it("muestra resumen de alertas cuando hay alertas", async () => {
    // alertCount = alto + medio; con alto=0 se muestra "N alertas"
    renderLayout({}, { alto: 0, medio: 5 });
    await waitFor(() => {
      expect(screen.getByText("5 alertas")).toBeInTheDocument();
    });
  });

  it("prioriza el conteo de alto riesgo en el resumen", async () => {
    renderLayout({}, { alto: 2, medio: 3 });
    await waitFor(() => {
      expect(screen.getByText("2 alto riesgo")).toBeInTheDocument();
    });
  });
});
