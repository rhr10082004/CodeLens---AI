import Editor from "@monaco-editor/react";
import {
  Activity,
  ArrowUpRight,
  BookText,
  Check,
  Code2,
  ExternalLink,
  FileCode2,
  GitBranch,
  History,
  Home,
  Info,
  LogOut,
  Moon,
  Play,
  Settings,
  ShieldCheck,
  Sun,
  Trash2,
  TriangleAlert,
  Upload,
  UserCircle2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { API_CONFIGURED, authenticate, browseGitHubRepository, clearToken, fetchGitHubFile, generateTestCases, getAnalysis, getToken, listAnalyses, removeAnalysis, revokeSession, runAnalysis, whoAmI } from "./api";
import type { Analysis, AnalysisSummary, GeneratedTestCase, GitHubFile, GitHubRepository, Language, User } from "./types";

const EXAMPLES: Record<Language, string> = {
  python: `import subprocess\n\ndef run_command(command):\n    return subprocess.run(command, shell=True, capture_output=True)\n`,
  javascript: `function findUser(users, id) {\n  return users.find((user) => user.id == id);\n}\n`,
  typescript: `type User = { id: number; email: string };\n\nfunction findUser(users: User[], id: number) {\n  return users.find((user) => user.id === id);\n}\n`,
  java: `public class Greeting {\n    public String greet(String name) {\n        return "Hello, " + name;\n    }\n}\n`,
};

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(Boolean(getToken()));
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authError, setAuthError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [language, setLanguage] = useState<Language>("python");
  const [code, setCode] = useState(EXAMPLES.python);
  const [includeAI, setIncludeAI] = useState(false);
  const [retainSource, setRetainSource] = useState(false);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [currentView, setCurrentView] = useState<"landing" | "workspace" | "docs" | "about" | "settings" | "profile">("workspace");
  const [githubUrl, setGithubUrl] = useState("");
  const [githubRepository, setGithubRepository] = useState<GitHubRepository | null>(null);
  const [githubFiles, setGithubFiles] = useState<GitHubFile[]>([]);
  const [githubLoading, setGithubLoading] = useState(false);
  const [githubError, setGithubError] = useState("");
  const [error, setError] = useState("");
  const [dark, setDark] = useState(true);

  const refreshHistory = useCallback(async () => {
    setHistory(await listAnalyses());
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    whoAmI()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setBooting(false));
  }, []);

  useEffect(() => {
    if (user) refreshHistory().catch((err: Error) => setError(err.message));
  }, [user, refreshHistory]);

  const lineCount = useMemo(() => code.split("\n").length, [code]);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setAuthError("");
    const data = new FormData(event.currentTarget);
    try {
      const signedIn = await authenticate(authMode, {
        name: String(data.get("name") ?? ""),
        email: String(data.get("email") ?? ""),
        password: String(data.get("password") ?? ""),
      });
      setUser(signedIn);
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "Could not authenticate.");
    } finally {
      setLoading(false);
    }
  }

  async function submitAnalysis() {
    setSubmitting(true);
    setError("");
    setAnalysis(null);
    try {
      const result = await runAnalysis(language, code, includeAI, retainSource);
      setAnalysis(result);
      await refreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis could not be completed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function submitGitHubBrowse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setGithubLoading(true);
    setGithubError("");
    setGithubRepository(null);
    setGithubFiles([]);
    try {
      const result = await browseGitHubRepository(githubUrl);
      setGithubRepository(result.repository);
      setGithubFiles(result.files);
    } catch (err) {
      setGithubError(err instanceof Error ? err.message : "Repository could not be loaded.");
    } finally {
      setGithubLoading(false);
    }
  }

  async function loadGitHubFile(file: GitHubFile) {
    setGithubLoading(true);
    setGithubError("");
    try {
      const loaded = await fetchGitHubFile(githubUrl, file.path);
      const ext = loaded.path.split(".").pop()?.toLowerCase();
      const nextLanguage: Language = ext === "py" ? "python" : ext === "java" ? "java" : ext === "ts" || ext === "tsx" ? "typescript" : "javascript";
      setLanguage(nextLanguage);
      setCode(loaded.source_code);
      setAnalysis(null);
      document.getElementById("code-editor")?.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      setGithubError(err instanceof Error ? err.message : "Repository file could not be loaded.");
    } finally {
      setGithubLoading(false);
    }
  }

  async function uploadSourceFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;
    const extension = file.name.split(".").pop()?.toLowerCase();
    const fileLanguages: Record<string, Language> = {
      py: "python",
      js: "javascript",
      jsx: "javascript",
      ts: "typescript",
      tsx: "typescript",
      java: "java",
    };
    if (!extension || !fileLanguages[extension]) {
      setError("Choose a supported .py, .js, .jsx, .ts, .tsx, or .java source file.");
      return;
    }
    if (file.size > 200_000) {
      setError("The source file exceeds the 200 KB upload limit.");
      return;
    }
    try {
      const source = await file.text();
      if (!source.trim()) {
        setError("The selected source file is empty.");
        return;
      }
      setError("");
      setLanguage(fileLanguages[extension]);
      setCode(source);
      setAnalysis(null);
    } catch {
      setError("The selected source file could not be read as text.");
    }
  }

  async function openReview(id: number) {
    setError("");
    try {
      setAnalysis(await getAnalysis(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review could not be loaded.");
    }
  }

  async function deleteReview(id: number) {
    try {
      await removeAnalysis(id);
      setHistory((previous) => previous.filter((item) => item.id !== id));
      if (analysis?.id === id) setAnalysis(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review could not be deleted.");
    }
  }

  function signOut() {
    const token = getToken();
    clearToken();
    setUser(null);
    setHistory([]);
    setAnalysis(null);
    setAuthError("");
    if (token) {
      void revokeSession(token).catch((err: Error) => {
        setAuthError(`Signed out on this device, but server session revocation failed: ${err.message}`);
      });
    }
  }

  if (booting) return <div className="boot-screen">Loading your workspace…</div>;
  if (!user) {
    return (
      <main className="auth-page">
        <div className="auth-brand"><span className="brand-icon"><Code2 size={20} /></span> codelens<span className="brand-ai">.ai</span></div>
        <section className="auth-card">
          <div className="eyebrow">YOUR CODE, UNDERSTOOD</div>
          <h1>{authMode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p className="muted">Static analysis and thoughtful AI review in one workspace.</p>
          {!API_CONFIGURED && (
            <p className="backend-notice" role="status">
              The production API is not connected yet. Sign-in and code review are unavailable.
            </p>
          )}
          <form onSubmit={submitAuth}>
            {authMode === "register" && <label>Your name<input name="name" autoComplete="name" minLength={2} required /></label>}
            <label>Email address<input name="email" type="email" autoComplete="email" required /></label>
            <label>Password<input name="password" type="password" autoComplete={authMode === "login" ? "current-password" : "new-password"} minLength={authMode === "register" ? 12 : 1} required /></label>
            {authError && <p className="error-message" role="alert">{authError}</p>}
            <button className="primary-button wide" disabled={loading}>{loading ? "Please wait…" : authMode === "login" ? "Sign in" : "Create account"}<ArrowUpRight size={16} /></button>
          </form>
          <p className="auth-switch">{authMode === "login" ? "New to CodeLens?" : "Already have an account?"} <button onClick={() => { setAuthMode(authMode === "login" ? "register" : "login"); setAuthError(""); }}>{authMode === "login" ? "Create an account" : "Sign in"}</button></p>
          <p className="auth-note"><ShieldCheck size={14} /> Your code is analyzed, never executed.</p>
        </section>
      </main>
    );
  }

  return (
    <div className={dark ? "app-shell dark" : "app-shell light"}>
      <aside className="sidebar">
        <div className="brand"><span className="brand-icon"><Code2 size={19} /></span><span>codelens<span className="brand-ai">.ai</span></span></div>
        <div className="workspace-label">WORKSPACE</div>
        <button className={`nav-item ${currentView === "landing" ? "active" : ""}`} onClick={() => setCurrentView("landing")}><Home size={17} /> Overview</button>
        <button className={`nav-item ${currentView === "workspace" ? "active" : ""}`} onClick={() => setCurrentView("workspace")}><FileCode2 size={17} /> Code review</button>
        <button className={`nav-item ${currentView === "docs" ? "active" : ""}`} onClick={() => setCurrentView("docs")}><BookText size={17} /> Documentation</button>
        <button className={`nav-item ${currentView === "about" ? "active" : ""}`} onClick={() => setCurrentView("about")}><Info size={17} /> About</button>
        <button className={`nav-item ${currentView === "settings" ? "active" : ""}`} onClick={() => setCurrentView("settings")}><Settings size={17} /> Settings</button>
        <button className={`nav-item ${currentView === "profile" ? "active" : ""}`} onClick={() => setCurrentView("profile")}><UserCircle2 size={17} /> Profile</button>
        <button className="nav-item" onClick={() => { setCurrentView("workspace"); document.getElementById("history")?.scrollIntoView({ behavior: "smooth" }); }}><History size={17} /> Review history <span className="nav-count">{history.length}</span></button>
        <div className="sidebar-bottom">
          <div className="privacy-box"><ShieldCheck size={16} /><div><strong>Private by design</strong><small>Source code is never executed.</small></div></div>
          <div className="user-row"><div className="avatar">{user.name.slice(0, 1).toUpperCase()}</div><div className="user-meta"><strong>{user.name}</strong><small>{user.email}</small></div><button className="icon-button" aria-label="Sign out" title="Sign out" onClick={signOut}><LogOut size={16} /></button></div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{currentView === "workspace" ? "Code review" : currentView === "landing" ? "Overview" : currentView === "docs" ? "Documentation" : currentView === "about" ? "About" : currentView === "settings" ? "Settings" : "Profile"}</strong></div><div className="top-actions"><span className="system-status"><span className="status-dot" /> Analysis service</span><button className="icon-button theme-toggle" aria-label="Toggle color theme" onClick={() => setDark(!dark)}>{dark ? <Sun size={17} /> : <Moon size={17} />}</button></div></header>
        {currentView === "workspace" ? (
          <div className="page-content">
            <div className="page-heading"><div><div className="eyebrow">CODE INTELLIGENCE</div><h1>Review your code</h1><p className="muted">Catch issues early with static analysis and optional AI feedback.</p></div><div className="heading-badge"><Activity size={15} /> Analysis workspace</div></div>
            {error && <div className="inline-error" role="alert"><TriangleAlert size={16} />{error}<button aria-label="Dismiss error" onClick={() => setError("")}><X size={15} /></button></div>}

            <details className="github-card">
              <summary><GitBranch size={16} /><span><strong>Browse a public GitHub repository</strong><small>Choose a supported source file to load into the editor.</small></span><span className="github-summary-action">Browse <ArrowUpRight size={14} /></span></summary>
              <form className="github-form" onSubmit={submitGitHubBrowse}><label className="sr-only" htmlFor="github-url">Public GitHub repository URL</label><input id="github-url" type="url" required placeholder="https://github.com/owner/repository" value={githubUrl} onChange={(event) => setGithubUrl(event.target.value)} /><button className="secondary-button" disabled={githubLoading}>{githubLoading ? "Loading…" : "Browse repository"}</button></form>
              {githubError && <p className="github-error" role="alert">{githubError}</p>}
              {githubRepository && <div className="github-files"><div className="github-repo-heading"><div><strong>{githubRepository.full_name}</strong><small>{githubRepository.description || "No description"} · branch {githubRepository.default_branch}</small></div><a href={githubRepository.html_url} target="_blank" rel="noreferrer" aria-label="Open repository on GitHub"><ExternalLink size={15} /></a></div>{githubFiles.length === 0 ? <p className="github-empty">No supported files within the configured size limit.</p> : githubFiles.map((file) => <button className="github-file-row" key={file.path} disabled={githubLoading} onClick={() => loadGitHubFile(file)}><FileCode2 size={14} /><span>{file.path}</span><small>{Math.ceil(file.size / 1024)} KB</small></button>)}</div>}
            </details>

            <section className="editor-card" id="code-editor">
              <div className="editor-toolbar"><div className="editor-file"><span className="file-icon"><Code2 size={15} /></span><span>untitled.{language === "javascript" ? "js" : language === "typescript" ? "ts" : language === "python" ? "py" : "java"}</span><span className="unsaved-dot" /></div><div className="editor-options"><label className="sr-only" htmlFor="language">Language</label><select id="language" value={language} onChange={(event) => { const selected = event.target.value as Language; setLanguage(selected); setCode(EXAMPLES[selected]); setAnalysis(null); }}><option value="python">Python</option><option value="javascript">JavaScript</option><option value="typescript">TypeScript</option><option value="java">Java</option></select><input id="source-upload" className="sr-only" type="file" accept=".py,.js,.jsx,.ts,.tsx,.java,text/plain" onChange={uploadSourceFile} /><label className="upload-button" htmlFor="source-upload"><Upload size={13} />Upload file</label><button className="clear-button" onClick={() => { setCode(""); setAnalysis(null); }}>Clear</button></div></div>
              <div className="editor-wrap"><Editor height="380px" language={language} theme={dark ? "vs-dark" : "light"} value={code} onChange={(value) => setCode(value ?? "")} options={{ minimap: { enabled: false }, fontSize: 13, lineHeight: 22, padding: { top: 16 }, scrollBeyondLastLine: false, wordWrap: "on", fontFamily: "'JetBrains Mono', monospace", automaticLayout: true, tabSize: 4 }} /></div>
              <div className="editor-footer"><div className="editor-meta"><span>{lineCount} lines</span><span className="meta-separator">·</span><span>{new TextEncoder().encode(code).length} bytes</span></div><div className="submit-options"><div className="ai-consent"><label className="ai-toggle"><input type="checkbox" checked={includeAI} onChange={(event) => setIncludeAI(event.target.checked)} /><span>Send source to Google Gemini</span><span className="optional">Optional</span></label><p className="ai-disclosure">When selected, the full source is sent to Google for AI review. Don’t include secrets or code you aren’t authorized to share.</p></div><div className="retention-consent"><label className="ai-toggle"><input type="checkbox" checked={retainSource} onChange={(event) => setRetainSource(event.target.checked)} /><span>Save source and evidence in history</span></label><p className="ai-disclosure">When off, saved reviews omit the source and finding evidence. Both remain visible for this review.</p></div><button className="primary-button" disabled={submitting || !code.trim()} onClick={submitAnalysis}><Play size={15} fill="currentColor" />{submitting ? "Analyzing…" : "Analyze code"}</button></div></div>
            </section>

            {analysis && <AnalysisPanel analysis={analysis} />}

            <section id="history" className="history-section"><div className="section-heading"><div><h2>Recent reviews</h2><p className="muted">Your saved analysis history.</p></div><span className="history-total">{history.length} {history.length === 1 ? "review" : "reviews"}</span></div>
              {history.length === 0 ? <div className="empty-state"><div className="empty-icon"><History size={20} /></div><strong>No reviews yet</strong><p>Submit code above to save your first analysis.</p></div> : <div className="history-list">{history.map((item) => <div className="history-row" key={item.id}><div className="history-language"><span className="history-file"><FileCode2 size={16} /></span><div><strong>{item.language} review</strong><small>{new Date(item.created_at).toLocaleString()}</small></div></div><div className="history-result">{item.quality_score === null ? <span className="score-pill unavailable">N/A</span> : <span className={`score-pill ${item.quality_score >= 80 ? "good" : item.quality_score >= 55 ? "medium" : "poor"}`}>{item.quality_score}<small>/100</small></span>}<button className="text-button" onClick={() => openReview(item.id)}>Open <ArrowUpRight size={14} /></button><button className="icon-button delete-button" aria-label={`Delete review ${item.id}`} onClick={() => deleteReview(item.id)}><Trash2 size={15} /></button></div></div>)}</div>}
            </section>
            <footer className="footer-note">AI-generated recommendations are hypotheses. Review changes carefully before applying.</footer>
          </div>
        ) : (
          <div className="page-content secondary-page-shell">
            {currentView === "landing" && (
              <div className="secondary-page">
                <div className="page-heading"><div><div className="eyebrow">OVERVIEW</div><h1>CodeLens AI</h1><p className="muted">From source review to safer release decisions.</p></div><div className="heading-badge"><Home size={15} /> Product overview</div></div>
                <div className="page-grid">
                  <div className="info-card"><h3>Static review</h3><p>Run linting-style checks across Python, JavaScript, TypeScript, and Java without executing user code.</p></div>
                  <div className="info-card"><h3>AI review</h3><p>Optional Gemini analysis surfaces likely issues with evidence, severity, and recommended fixes.</p></div>
                  <div className="info-card"><h3>Protected workflow</h3><p>Private-by-default handling, source retention controls, and explicit consent before sending code externally.</p></div>
                </div>
              </div>
            )}
            {currentView === "docs" && (
              <div className="secondary-page">
                <div className="page-heading"><div><div className="eyebrow">DOCUMENTATION</div><h1>How CodeLens works</h1><p className="muted">A concise guide for everyday security and code-quality reviews.</p></div><div className="heading-badge"><BookText size={15} /> Quick start</div></div>
                <div className="doc-list">
                  <div><strong>1. Select source</strong><p>Paste code, upload a supported file, or browse a public GitHub repository.</p></div>
                  <div><strong>2. Run analysis</strong><p>Review static findings and optional AI results with line-level evidence when available.</p></div>
                  <div><strong>3. Validate changes</strong><p>Use generated test scenarios to explore edge cases and decide what to fix before release.</p></div>
                </div>
              </div>
            )}
            {currentView === "about" && (
              <div className="secondary-page">
                <div className="page-heading"><div><div className="eyebrow">ABOUT</div><h1>Built for careful review</h1><p className="muted">The platform helps developers reason about code quality without pretending to be a certification system.</p></div><div className="heading-badge"><Info size={15} /> Mission</div></div>
                <div className="info-card feature-block"><p>CodeLens surfaces likely issues, explains the reasoning behind them, and keeps review history scoped to the signed-in user. Quality scores are informative, not a security guarantee.</p></div>
              </div>
            )}
            {currentView === "settings" && (
              <div className="secondary-page">
                <div className="page-heading"><div><div className="eyebrow">SETTINGS</div><h1>Workspace preferences</h1><p className="muted">Control the review experience without changing a single analyzed file.</p></div><div className="heading-badge"><Settings size={15} /> Preferences</div></div>
                <div className="settings-list">
                  <label className="setting-row"><span>Dark mode</span><input type="checkbox" checked={dark} onChange={() => setDark(!dark)} /></label>
                  <label className="setting-row"><span>Use AI review by default</span><input type="checkbox" checked={includeAI} onChange={(event) => setIncludeAI(event.target.checked)} /></label>
                  <label className="setting-row"><span>Retain source in saved history</span><input type="checkbox" checked={retainSource} onChange={(event) => setRetainSource(event.target.checked)} /></label>
                </div>
              </div>
            )}
            {currentView === "profile" && (
              <div className="secondary-page">
                <div className="page-heading"><div><div className="eyebrow">PROFILE</div><h1>{user.name}</h1><p className="muted">{user.email}</p></div><div className="heading-badge"><UserCircle2 size={15} /> Account</div></div>
                <div className="profile-card">
                  <div className="avatar large">{user.name.slice(0, 1).toUpperCase()}</div>
                  <div>
                    <h3>Signed in successfully</h3>
                    <p>{user.email}</p>
                    <small>Review history is stored per user and only available to the current account.</small>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function AnalysisPanel({ analysis }: { analysis: Analysis }) {
  const [severityFilter, setSeverityFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [testCases, setTestCases] = useState<GeneratedTestCase[]>([]);
  const [testCaseError, setTestCaseError] = useState("");
  const [generatingTestCases, setGeneratingTestCases] = useState(false);
  const visibleFindings = analysis.findings.filter((finding) => {
    const matchesSeverity = severityFilter === "all" || finding.severity === severityFilter;
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || [
      finding.title,
      finding.description,
      finding.evidence ?? "",
      finding.analyzer,
    ].some((value) => value.toLowerCase().includes(query));
    return matchesSeverity && matchesSearch;
  });

  async function generateCases() {
    if (!analysis.source_code) return;
    setGeneratingTestCases(true);
    setTestCaseError("");
    setTestCases([]);
    try {
      setTestCases(await generateTestCases(analysis.language, analysis.source_code));
    } catch (err) {
      setTestCaseError(err instanceof Error ? err.message : "Test cases could not be generated.");
    } finally {
      setGeneratingTestCases(false);
    }
  }

  function downloadReport() {
    const report = {
      product: "CodeLens AI",
      analysis_id: analysis.id,
      language: analysis.language,
      analyzed_at: analysis.created_at,
      status: analysis.status,
      quality_score: analysis.quality_score,
      static_findings: analysis.findings,
      ai_generated_potential_issues: analysis.ai_findings,
      analyzers: analysis.analyzers,
      limitations: [
        "AI findings are hypotheses and require developer verification.",
        "A quality score is not a security certification.",
        "Only the listed analyzers were run; unavailable tools were not simulated.",
      ],
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `codelens-review-${analysis.id}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <section className="results-card">
      <div className="results-header"><div><div className="eyebrow">ANALYSIS {analysis.status.toUpperCase()}</div><h2>Review results <span className="result-id">#{analysis.id}</span></h2></div><div className="result-actions">{analysis.quality_score === null ? <div className="score-large unavailable"><strong>—</strong><small>score unavailable</small></div> : <div className={`score-large ${analysis.quality_score >= 80 ? "good" : analysis.quality_score >= 55 ? "medium" : "poor"}`}><strong>{analysis.quality_score}</strong><small>/ 100 quality score</small></div>}<button className="secondary-button report-button" onClick={downloadReport}>Download report</button></div></div>
      <div className="analyzer-list">{analysis.analyzers.map((analyzer) => <div className="analyzer-status" key={analyzer.name}><span className={analyzer.available ? "analyzer-mark available" : "analyzer-mark"}>{analyzer.available ? <Check size={12} /> : <X size={12} />}</span><span><strong>{analyzer.name}</strong><small>{analyzer.message}</small></span></div>)}</div>
      {analysis.findings.length ? <div className="findings-list"><div className="findings-controls"><div className="findings-title">{visibleFindings.length} of {analysis.findings.length} static finding{analysis.findings.length === 1 ? "" : "s"}</div><input aria-label="Search findings" placeholder="Search findings" value={search} onChange={(event) => setSearch(event.target.value)} /><select aria-label="Filter by severity" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option><option value="info">Info</option></select></div>{visibleFindings.length === 0 ? <p className="no-filter-results">No findings match these filters.</p> : visibleFindings.map((finding) => <article className="finding" key={finding.id}><span className={`severity ${finding.severity}`}>{finding.severity}</span><div className="finding-body"><strong>{finding.title}</strong><p>{finding.description}</p><div className="finding-meta"><span>{finding.analyzer}</span>{finding.line && <span>Line {finding.line}</span>}{finding.evidence && <code>{finding.evidence}</code>}</div></div></article>)}</div> : <div className="no-findings"><Check size={17} /><span>No findings reported by the available analyzers.</span></div>}
      {analysis.ai_findings.length > 0 && <div className="findings-list ai-findings"><div className="findings-title">AI-generated potential issues <span>Verify before acting</span></div>{analysis.ai_findings.map((finding, index) => <article className="finding" key={index}><span className="severity info">AI</span><div className="finding-body"><strong>{finding.title}</strong><p>{finding.explanation}</p>{finding.line_start !== null && <div className="finding-meta"><span>Lines {finding.line_start}{finding.line_end !== null ? `–${finding.line_end}` : ""}</span></div>}</div></article>)}</div>}
      <section className="test-cases-section" aria-label="AI-generated test cases">
        <div className="test-cases-heading"><div><h3>Test scenarios</h3><p>AI suggestions only; not executable and not run.</p></div><button className="secondary-button" disabled={!analysis.source_code || generatingTestCases} onClick={generateCases}>{generatingTestCases ? "Generating…" : "Generate AI test cases"}</button></div>
        <p className="test-case-disclosure">Selecting Generate sends the full source to Google Gemini. Don’t include secrets or source you aren’t authorized to share.</p>
        {!analysis.source_code && <p className="test-case-note">Source was not retained for this review. To generate scenarios, rerun the analysis with source retention enabled.</p>}
        {testCaseError && <p role="alert" className="test-case-error">{testCaseError}</p>}
        {testCases.length > 0 && <div className="test-case-list">{testCases.map((testCase, index) => <article className="test-case" key={`${testCase.name}-${index}`}><div className="test-case-title"><strong>{testCase.name}</strong><span>{testCase.category}</span></div><p>{testCase.purpose}</p><dl><div><dt>Input</dt><dd><code>{testCase.input_data}</code></dd></div><div><dt>Expected result</dt><dd>{testCase.expected_result}</dd></div></dl></article>)}</div>}
      </section>
      <details className="source-details"><summary>Reviewed source · {analysis.language}</summary>{analysis.source_code ? <pre>{analysis.source_code}</pre> : <p>This review did not retain the source code. Enable “Save source and evidence in history” before a future analysis to keep it with the review.</p>}</details>
    </section>
  );
}

export default App;
