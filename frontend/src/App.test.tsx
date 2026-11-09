import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const apiMocks = vi.hoisted(() => ({
  generateTestCases: vi.fn(),
  listAnalyses: vi.fn(),
  revokeSession: vi.fn(),
  whoAmI: vi.fn(),
}));

vi.mock("@monaco-editor/react", () => ({
  default: ({ value }: { value: string }) => <textarea aria-label="Code editor" value={value} readOnly />,
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, ...apiMocks };
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CodeLens application", () => {
  it("shows a sign-in form when no user session is available", () => {
    sessionStorage.clear();
    render(<App />);
    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
  });

  it("offers a registration form with password length validation", () => {
    sessionStorage.clear();
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Create an account" }));
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    expect(screen.getByLabelText("Your name")).toBeRequired();
    expect(screen.getByLabelText("Password")).toHaveAttribute("minLength", "12");
  });

  it("discloses that Gemini receives the full source and keeps the opt-in disabled by default", async () => {
    sessionStorage.setItem("codelens_access_token", "test-token");
    apiMocks.whoAmI.mockResolvedValue({ id: 1, name: "Test User", email: "test@example.com" });
    apiMocks.listAnalyses.mockResolvedValue([]);

    render(<App />);

    const geminiConsent = await screen.findByRole("checkbox", { name: /Send source to Google Gemini/ });
    expect(geminiConsent).not.toBeChecked();
    expect(screen.getByText(/the full source is sent to Google for AI review/i)).toBeInTheDocument();
    const retentionConsent = screen.getByRole("checkbox", { name: /Save source and evidence in history/ });
    expect(retentionConsent).not.toBeChecked();
    expect(screen.getByText(/saved reviews omit the source and finding evidence/i)).toBeInTheDocument();

    fireEvent.click(geminiConsent);
    expect(geminiConsent).toBeChecked();
  });

  it("revokes the server session after clearing the local session", async () => {
    sessionStorage.setItem("codelens_access_token", "test-token");
    apiMocks.whoAmI.mockResolvedValue({ id: 1, name: "Test User", email: "test@example.com" });
    apiMocks.listAnalyses.mockResolvedValue([]);
    apiMocks.revokeSession.mockResolvedValue(undefined);

    render(<App />);
    await screen.findByRole("button", { name: "Sign out" });
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(sessionStorage.getItem("codelens_access_token")).toBeNull();
    expect(apiMocks.revokeSession).toHaveBeenCalledWith("test-token");
  });

  it("reports when local sign-out succeeds but server revocation fails", async () => {
    sessionStorage.setItem("codelens_access_token", "test-token");
    apiMocks.whoAmI.mockResolvedValue({ id: 1, name: "Test User", email: "test@example.com" });
    apiMocks.listAnalyses.mockResolvedValue([]);
    apiMocks.revokeSession.mockRejectedValue(new Error("network unavailable"));

    render(<App />);
    await screen.findByRole("button", { name: "Sign out" });
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Signed out on this device, but server session revocation failed: network unavailable",
    );
    expect(sessionStorage.getItem("codelens_access_token")).toBeNull();
  });

  it("shows retained source and explains when source was omitted from a saved review", async () => {
    sessionStorage.setItem("codelens_access_token", "test-token");
    apiMocks.whoAmI.mockResolvedValue({ id: 1, name: "Test User", email: "test@example.com" });
    apiMocks.listAnalyses.mockResolvedValue([
      { id: 9, language: "python", quality_score: 100, status: "completed", created_at: "2026-11-07T00:00:00Z" },
      { id: 10, language: "python", quality_score: 100, status: "completed", created_at: "2026-11-07T00:00:00Z" },
    ]);
    const savedReview = (id: number, source_code: string | null) => ({
      id,
      language: "python",
      quality_score: 100,
      status: "completed",
      findings: [],
      ai_findings: [],
      analyzers: [],
      source_code,
      created_at: "2026-11-07T00:00:00Z",
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(savedReview(9, null)), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(savedReview(10, "print('retained')")), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    const openButtons = await screen.findAllByRole("button", { name: /Open/ });
    fireEvent.click(openButtons[0]);

    expect(await screen.findByText(/This review did not retain the source code/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate AI test cases" })).toBeDisabled();

    fireEvent.click(openButtons[1]);
    fireEvent.click(await screen.findByText("Reviewed source · python"));
    expect(await screen.findByText("print('retained')")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate AI test cases" })).toBeEnabled();
    expect(screen.getByText(/Selecting Generate sends the full source to Google Gemini/i)).toBeInTheDocument();

    apiMocks.generateTestCases.mockResolvedValue([
      {
        name: "Empty input",
        purpose: "Check empty input handling.",
        input_data: "[]",
        expected_result: "An empty result is returned.",
        category: "edge",
      },
    ]);
    fireEvent.click(screen.getByRole("button", { name: "Generate AI test cases" }));

    expect(await screen.findByText("Empty input")).toBeInTheDocument();
    expect(screen.getByText("An empty result is returned.")).toBeInTheDocument();
    expect(apiMocks.generateTestCases).toHaveBeenCalledWith("python", "print('retained')");
  });
});
