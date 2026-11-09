import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authenticate, clearToken, generateTestCases, getToken, revokeSession, runAnalysis } from "./api";

describe("API client", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stores bearer token after authentication", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            access_token: "test-access-token",
            user: { id: 1, name: "Reviewer", email: "reviewer@example.com" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const user = await authenticate("login", { email: "reviewer@example.com", password: "passphrase" });
    expect(user.email).toBe("reviewer@example.com");
    expect(getToken()).toBe("test-access-token");
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("sends analysis options with authenticated request", async () => {
    sessionStorage.setItem("codelens_access_token", "test-token");
    const result = {
      id: 7,
      language: "python",
      quality_score: 100,
      status: "completed",
      findings: [],
      ai_findings: [],
      analyzers: [],
      source_code: "print(1)",
      created_at: "2026-01-01T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(result), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await runAnalysis("python", "print(1)", false, true);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/analyses");
    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer test-token");
    expect(JSON.parse(String(options.body))).toMatchObject({ retain_source: true });
  });

  it("surfaces API errors instead of fabricating success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "service unavailable" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(authenticate("login", { email: "bad@example.com", password: "x" })).rejects.toThrow(
      "service unavailable",
    );
  });

  it("sends a specific access token when revoking a session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await revokeSession("session-to-revoke");

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(fetchMock.mock.calls[0][0]).toContain("/api/auth/logout");
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer session-to-revoke");
  });

  it("requests AI test scenarios without saving source or generated output", async () => {
    sessionStorage.setItem("codelens_access_token", "test-token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            name: "Boundary case",
            purpose: "Check the upper boundary.",
            input_data: "100",
            expected_result: "The value is accepted.",
            category: "boundary",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const cases = await generateTestCases("python", "def check(value): return value <= 100");

    expect(cases[0].category).toBe("boundary");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/test-cases");
    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(options.body))).toEqual({
      language: "python",
      source_code: "def check(value): return value <= 100",
    });
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer test-token");
  });
});
