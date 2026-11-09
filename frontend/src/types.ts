export type Language = "python" | "javascript" | "typescript" | "java";

export interface User {
  id: number;
  name: string;
  email: string;
}

export interface Finding {
  id: string;
  title: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  file_path: string;
  line: number | null;
  evidence: string | null;
  analyzer: string;
  suggested_correction: string | null;
}

export interface Analysis {
  id: number;
  language: Language;
  quality_score: number | null;
  status: string;
  findings: Finding[];
  ai_findings: Array<{
    title: string;
    explanation: string;
    severity: string;
    evidence: string | null;
    line_start: number | null;
    line_end: number | null;
    why_it_matters: string;
    recommended_fix: string;
    confidence: number;
  }>;
  analyzers: Array<{ name: string; available: boolean; message: string }>;
  source_code: string | null;
  created_at: string;
}

export interface GeneratedTestCase {
  name: string;
  purpose: string;
  input_data: string;
  expected_result: string;
  category: "normal" | "boundary" | "edge" | "error" | "regression";
}

export interface AnalysisSummary {
  id: number;
  language: Language;
  quality_score: number | null;
  status: string;
  created_at: string;
}

export interface GitHubRepository {
  full_name: string;
  description: string | null;
  default_branch: string;
  html_url: string;
  private: boolean;
  size: number;
}

export interface GitHubFile {
  path: string;
  size: number;
  sha: string;
}
