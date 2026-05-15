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
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
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

  it("muestra brand Yachay Deep", async () => {
    renderLayout();
    await waitFor(() => {});
    expect(screen.getByText("Yachay Deep")).toBeInTheDocument();
    expect(screen.getByText("Monitoreo Académico")).toBeInTheDocument();
  });

  it("muestra badge de alertas cuando hay alertas", async () => {
    renderLayout({}, { critico: 3, alto: 2 });
    await waitFor(() => {
      expect(screen.getByText("5")).toBeInTheDocument();
    });
  });
});
