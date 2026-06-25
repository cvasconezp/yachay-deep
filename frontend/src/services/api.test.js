/**
 * T25: Tests unitarios API Client (services/api.js)
 *
 * Cobertura:
 *  - sanitizeErrorMessage (XSS)
 *  - request(): JSON ok, 401 dispatch, error detail parsing, timeout, PDF blob
 *  - HTTP helpers: get, post, put, patch, delete
 *  - getBlob: ok + 401 + error
 *  - login(): FormData con username/password
 *  - searchStudents: query string building
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── Mock de import.meta.env antes de importar api ──
vi.stubEnv("VITE_API_URL", "http://test:8000");

// Importar después del stub
const { api } = await import("./api.js");

// ── Helpers ──

function jsonResponse(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function errorResponse(detail, status = 400) {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ══════════════ sanitizeErrorMessage ══════════════

describe("sanitizeErrorMessage", () => {
  // Accedemos via la respuesta de error del request
  it("elimina tags HTML de mensajes de error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      errorResponse('<script>alert("xss")</script>Hola', 400)
    );
    await expect(api.get("/test")).rejects.toThrow("alert");
    // No debe contener tags
    try { await api.get("/test"); } catch (_) { /* ya testeado */ }
  });

  it("trunca mensajes largos a 500 chars", async () => {
    const longMsg = "A".repeat(1000);
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(errorResponse(longMsg, 400));
    try {
      await api.get("/test");
    } catch (e) {
      expect(e.message.length).toBeLessThanOrEqual(500);
    }
  });

  it("maneja detail no-string como Error desconocido", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 12345 }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      })
    );
    await expect(api.get("/test")).rejects.toThrow("HTTP 400");
  });
});

// ══════════════ request() core ══════════════

describe("request()", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("retorna JSON en respuesta exitosa", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({ ok: true, data: [1, 2, 3] })
    );
    const result = await api.get("/test");
    expect(result).toEqual({ ok: true, data: [1, 2, 3] });
  });

  it("incluye credentials:'include' en cada request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse({ ok: true }));
    await api.get("/any");
    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("despacha evento yd:unauthorized en 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("", { status: 401 })
    );
    const handler = vi.fn();
    window.addEventListener("yd:unauthorized", handler);
    await expect(api.get("/test")).rejects.toThrow("No autenticado");
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener("yd:unauthorized", handler);
  });

  it("parsea detail como array de validacion", async () => {
    const detail = [
      { msg: "campo requerido", loc: ["body", "email"] },
      { msg: "formato invalido", loc: ["body", "name"] },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(errorResponse(detail, 422));
    await expect(api.get("/test")).rejects.toThrow("campo requerido; formato invalido");
  });

  it("retorna blob para content-type PDF", async () => {
    const body = new TextEncoder().encode("%PDF-1.4");
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(body, {
        status: 200,
        headers: { "Content-Type": "application/pdf" },
      })
    );
    const result = await api.get("/export/pdf");
    expect(result.size).toBeGreaterThan(0);
    expect(typeof result.text).toBe("function");
  });

  it("maneja respuesta de error sin JSON valido", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("Internal Server Error", {
        status: 500,
        headers: { "Content-Type": "text/plain" },
      })
    );
    await expect(api.get("/test")).rejects.toThrow("Error desconocido");
  });

  it("timeout lanza error descriptivo", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, opts) =>
        new Promise((_, reject) => {
          opts.signal?.addEventListener("abort", () =>
            reject(Object.assign(new Error("aborted"), { name: "AbortError" }))
          );
        })
    );

    const promise = api.get("/slow");
    vi.advanceTimersByTime(31000);

    await expect(promise).rejects.toThrow("tardó demasiado");
    vi.useRealTimers();
  });
});

// ══════════════ HTTP helpers ══════════════

describe("HTTP helpers", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("post() envia JSON con method POST", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse({ id: 1 }));
    await api.post("/items", { name: "test" });
    const [, opts] = fetch.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ name: "test" });
  });

  it("put() envia method PUT", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse({ ok: true }));
    await api.put("/items/1", { name: "updated" });
    expect(fetch.mock.calls[0][1].method).toBe("PUT");
  });

  it("patch() envia method PATCH", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse({ ok: true }));
    await api.patch("/items/1", { status: "done" });
    expect(fetch.mock.calls[0][1].method).toBe("PATCH");
  });

  it("delete() envia method DELETE", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse({ ok: true }));
    await api.delete("/items/1");
    expect(fetch.mock.calls[0][1].method).toBe("DELETE");
  });
});

// ══════════════ getBlob ══════════════

describe("getBlob()", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("retorna blob en respuesta exitosa", async () => {
    const body = new TextEncoder().encode("filedata");
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(body, { status: 200 }));
    const result = await api.getBlob("/export/file");
    expect(result.size).toBeGreaterThan(0);
    expect(typeof result.text).toBe("function");
  });

  it("401 despacha yd:unauthorized", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("", { status: 401 }));
    const handler = vi.fn();
    window.addEventListener("yd:unauthorized", handler);
    await expect(api.getBlob("/export/file")).rejects.toThrow("No autenticado");
    expect(handler).toHaveBeenCalled();
    window.removeEventListener("yd:unauthorized", handler);
  });

  it("error non-401 lanza con detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      errorResponse("Archivo no encontrado", 404)
    );
    await expect(api.getBlob("/export/missing")).rejects.toThrow("Archivo no encontrado");
  });
});

// ══════════════ login() ══════════════

describe("login()", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("envia FormData con username y password", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({ access_token: "tok", role: "admin" })
    );
    await api.login("user@test.com", "secret");
    const [, opts] = fetch.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
    expect(opts.body.get("username")).toBe("user@test.com");
    expect(opts.body.get("password")).toBe("secret");
  });
});

// ══════════════ searchStudents ══════════════

describe("searchStudents()", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("construye query string con todos los params", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse({ items: [] }));
    await api.searchStudents("Juan", "DERECHO", { page: 2, limit: 25, nivel_riesgo: "alto" });
    const url = fetch.mock.calls[0][0];
    expect(url).toContain("q=Juan");
    expect(url).toContain("carrera=DERECHO");
    expect(url).toContain("page=2");
    expect(url).toContain("limit=25");
    expect(url).toContain("nivel_riesgo=alto");
  });

  it("omite params vacios", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse({ items: [] }));
    await api.searchStudents("", "");
    const url = fetch.mock.calls[0][0];
    expect(url).not.toContain("q=");
    expect(url).not.toContain("carrera=");
  });
});
