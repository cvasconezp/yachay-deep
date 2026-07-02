/**
 * T26: Tests del hook useAuth + AuthProvider
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./useAuth.jsx";

vi.mock("../services/api", () => ({
  api: {
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

import { api } from "../services/api";

function AuthConsumer() {
  const { user, loading, login, logout, isAdmin } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.email : "null"}</span>
      <span data-testid="isAdmin">{String(isAdmin)}</span>
      <button onClick={() => login("a@b.com", "pass")}>Login</button>
      <button onClick={() => logout()}>Logout</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <AuthProvider><AuthConsumer /></AuthProvider>
  );
}

describe("useAuth / AuthProvider", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Prevent polling from interfering
    vi.spyOn(global, "setInterval").mockReturnValue(999);
    vi.spyOn(global, "clearInterval");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("muestra loading=true y luego false tras me()", async () => {
    api.me.mockResolvedValue({ email: "u@test.com", role: "monitor" });
    renderWithProvider();
    expect(screen.getByTestId("loading").textContent).toBe("true");
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false")
    );
  });

  it("carga usuario de api.me() al montar", async () => {
    api.me.mockResolvedValue({ email: "admin@test.com", role: "admin" });
    renderWithProvider();
    await waitFor(() =>
      expect(screen.getByTestId("user").textContent).toBe("admin@test.com")
    );
    expect(screen.getByTestId("isAdmin").textContent).toBe("true");
  });

  it("user=null si me() falla", async () => {
    api.me.mockRejectedValue(new Error("No autenticado"));
    renderWithProvider();
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false")
    );
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("login() setea user", async () => {
    api.me.mockRejectedValue(new Error("No auth"));
    renderWithProvider();
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false")
    );

    api.login.mockResolvedValueOnce({ user: { email: "new@test.com", role: "monitor" } });
    await act(async () => {
      screen.getByText("Login").click();
    });

    // login() pasa el 3er arg de 2FA (code=null cuando no se ingresa código)
    expect(api.login).toHaveBeenCalledWith("a@b.com", "pass", null);
    expect(screen.getByTestId("user").textContent).toBe("new@test.com");
    expect(screen.getByTestId("isAdmin").textContent).toBe("false");
  });

  it("logout() limpia user incluso si api falla", async () => {
    api.me.mockResolvedValue({ email: "u@test.com", role: "admin" });
    renderWithProvider();
    await waitFor(() =>
      expect(screen.getByTestId("user").textContent).toBe("u@test.com")
    );

    api.logout.mockRejectedValueOnce(new Error("network"));
    await act(async () => {
      screen.getByText("Logout").click();
    });

    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("yd:unauthorized event limpia user", async () => {
    api.me.mockResolvedValue({ email: "u@test.com", role: "monitor" });
    renderWithProvider();
    await waitFor(() =>
      expect(screen.getByTestId("user").textContent).toBe("u@test.com")
    );

    act(() => {
      window.dispatchEvent(new CustomEvent("yd:unauthorized"));
    });

    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("registra intervalo de polling al montar", async () => {
    api.me.mockResolvedValue({ email: "u@test.com", role: "monitor" });
    renderWithProvider();
    await waitFor(() =>
      expect(screen.getByTestId("user").textContent).toBe("u@test.com")
    );
    // setInterval fue llamado con 120_000ms
    expect(setInterval).toHaveBeenCalledWith(expect.any(Function), 120_000);
  });
});
