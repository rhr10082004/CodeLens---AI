import json
import shutil
# Only fixed static analyzer executables are launched with a fixed argv list.
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.core.config import get_settings
from app.schemas import AnalyzerStatus, Finding

EXTENSIONS = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "java": ".java",
}
def _node_modules() -> Path:
    configured = get_settings().frontend_node_modules_path
    return Path(configured) if configured else Path(__file__).resolve().parents[2] / "frontend" / "node_modules"


def _run(command: list[str], cwd: str) -> tuple[bool, str, str]:
    try:
        # Submitted data is provided via a file, never through an executable or argument.
        result = subprocess.run(  # nosec B603
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            cwd=cwd,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return False, "", "Analyzer timed out after 15 seconds."
    except OSError:
        return False, "", "Analyzer could not be started."
    return True, result.stdout, result.stderr


def _source_line(source: str, line: int | None) -> str | None:
    if line is None:
        return None
    lines = source.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()[:500] or None
    return None


def _failed(name: str, message: str) -> tuple[AnalyzerStatus, list[Finding]]:
    return AnalyzerStatus(name=name, available=False, message=message), []


def _ruff(source: str) -> tuple[AnalyzerStatus, list[Finding]]:
    executable = shutil.which("ruff")
    if not executable:
        return _failed("Ruff", "Install Ruff to enable Python linting.")
    with tempfile.TemporaryDirectory(prefix="codelens-") as directory:
        path = Path(directory) / "submitted.py"
        path.write_text(source, encoding="utf-8")
        succeeded, stdout, error = _run(
            [executable, "check", "--output-format=json", str(path)], directory
        )
        if not succeeded:
            return _failed("Ruff", error)
    try:
        records: list[dict[str, Any]] = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        return _failed("Ruff", "Ruff failed to return valid structured results.")
    findings = [
        Finding(
            id=f"ruff-{item.get('code', 'unknown')}-{item.get('location', {}).get('row', 0)}",
            title=item.get("message", "Lint finding"),
            description=item.get("message", "Lint finding"),
            severity="low",
            file_path="submitted.py",
            line=item.get("location", {}).get("row"),
            evidence=item.get("code"),
            analyzer="Ruff",
            suggested_correction=(item.get("fix") or {}).get("message"),
        )
        for item in records
    ]
    return AnalyzerStatus(name="Ruff", available=True, message=f"Completed with {len(findings)} finding(s)."), findings


def _bandit(source: str) -> tuple[AnalyzerStatus, list[Finding]]:
    executable = shutil.which("bandit")
    if not executable:
        return _failed("Bandit", "Install Bandit to enable Python security linting.")
    with tempfile.TemporaryDirectory(prefix="codelens-") as directory:
        path = Path(directory) / "submitted.py"
        path.write_text(source, encoding="utf-8")
        succeeded, stdout, error = _run([executable, "-f", "json", str(path)], directory)
        if not succeeded:
            return _failed("Bandit", error)
    try:
        records = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return _failed("Bandit", "Bandit failed to return valid structured results.")
    findings = [
        Finding(
            id=f"bandit-{item.get('test_id', 'unknown')}-{item.get('line_number', 0)}",
            title=item.get("test_name", "Security lint finding"),
            description=item.get("issue_text", "Security lint finding"),
            severity={"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(
                item.get("issue_severity"), "info"
            ),
            file_path="submitted.py",
            line=item.get("line_number"),
            evidence=item.get("code"),
            analyzer="Bandit",
            suggested_correction=None,
        )
        for item in records.get("results", [])
    ]
    return AnalyzerStatus(name="Bandit", available=True, message=f"Completed with {len(findings)} finding(s)."), findings


def _eslint(source: str, language: str) -> tuple[AnalyzerStatus, list[Finding]]:
    node = shutil.which("node")
    node_modules = _node_modules()
    eslint = node_modules / "eslint" / "bin" / "eslint.js"
    parser = node_modules / "@typescript-eslint" / "parser" / "dist" / "index.js"
    if not node or not eslint.is_file() or not parser.is_file():
        return _failed(
            "ESLint",
            "ESLint and @typescript-eslint/parser must be installed with the frontend dependencies.",
        )
    extension = ".ts" if language == "typescript" else ".js"
    with tempfile.TemporaryDirectory(prefix="codelens-") as directory:
        root = Path(directory)
        source_path = root / f"submitted{extension}"
        config_path = root / "eslint.config.mjs"
        source_path.write_text(source, encoding="utf-8")
        config_path.write_text(
            "import parser from "
            + json.dumps(parser.resolve().as_uri())
            + ";\n"
            + "export default [{"
            + 'files:["**/*.{js,jsx,ts,tsx}"],'
            + "languageOptions:{parser,parserOptions:{ecmaVersion:'latest',sourceType:'module',ecmaFeatures:{jsx:true}}},"
            + "rules:{eqeqeq:['error','always'],"
            + "'no-eval':'error','no-implied-eval':'error','no-debugger':'warn',"
            + "'no-constant-condition':'warn'}"
            + "}];\n",
            encoding="utf-8",
        )
        succeeded, stdout, error = _run(
            [
                node,
                str(eslint),
                "--no-config-lookup",
                "--no-ignore",
                "--config",
                str(config_path),
                "--format",
                "json",
                str(source_path),
            ],
            directory,
        )
        if not succeeded:
            return _failed("ESLint", error)
    try:
        reports = json.loads(stdout)
        messages = reports[0].get("messages", [])
    except (json.JSONDecodeError, IndexError, AttributeError, TypeError):
        return _failed("ESLint", "ESLint failed to return valid structured results.")
    findings = [
        Finding(
            id=f"eslint-{item.get('ruleId') or 'parse'}-{item.get('line') or 0}-{index}",
            title=item.get("message", "Lint finding"),
            description=item.get("message", "Lint finding"),
            severity="medium" if item.get("severity") == 2 else "low",
            file_path=f"submitted{extension}",
            line=item.get("line"),
            evidence=_source_line(source, item.get("line")),
            analyzer="ESLint",
            suggested_correction=None,
        )
        for index, item in enumerate(messages)
    ]
    return AnalyzerStatus(name="ESLint", available=True, message=f"Completed with {len(findings)} finding(s)."), findings


def _checkstyle(source: str) -> tuple[AnalyzerStatus, list[Finding]]:
    jar = get_settings().checkstyle_jar
    java = shutil.which("java")
    if not jar or not Path(jar).is_file() or not java:
        return _failed(
            "Checkstyle",
            "Java source linting requires Java and a configured CHECKSTYLE_JAR; source is not compiled or executed.",
        )
    with tempfile.TemporaryDirectory(prefix="codelens-") as directory:
        root = Path(directory)
        path = root / "Submitted.java"
        config = root / "checkstyle.xml"
        path.write_text(source, encoding="utf-8")
        config.write_text(
            """<?xml version="1.0"?>
<!DOCTYPE module PUBLIC
  "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN"
  "https://checkstyle.org/dtds/configuration_1_3.dtd">
<module name="Checker">
  <module name="TreeWalker">
    <module name="AvoidInlineConditionals"/>
    <module name="EmptyStatement"/>
    <module name="EqualsAvoidNull"/>
    <module name="FallThrough"/>
    <module name="MissingSwitchDefault"/>
    <module name="NeedBraces"/>
    <module name="OneStatementPerLine"/>
    <module name="SimplifyBooleanExpression"/>
    <module name="UnusedImports"/>
  </module>
</module>
""",
            encoding="utf-8",
        )
        succeeded, stdout, error = _run(
            [java, "-jar", str(Path(jar).resolve()), "-c", str(config), "-f", "xml", str(path)],
            directory,
        )
        if not succeeded:
            return _failed("Checkstyle", error)
    try:
        report = ET.fromstring(stdout)
        errors = report.findall(".//error")
    except (ET.ParseError, DefusedXmlException):
        return _failed("Checkstyle", "Checkstyle failed to return valid structured results.")
    findings = [
        Finding(
            id=f"checkstyle-{item.get('source', 'finding')}-{item.get('line', '0')}-{index}",
            title=(item.get("source", "Checkstyle finding").rsplit(".", 1)[-1]),
            description=item.get("message", "Checkstyle finding"),
            severity={"error": "medium", "warning": "low", "info": "info"}.get(
                item.get("severity", "warning"), "low"
            ),
            file_path="Submitted.java",
            line=int(item.get("line", "0")) or None,
            evidence=_source_line(source, int(item.get("line", "0")) or None),
            analyzer="Checkstyle",
            suggested_correction=None,
        )
        for index, item in enumerate(errors)
    ]
    return AnalyzerStatus(name="Checkstyle", available=True, message=f"Completed with {len(findings)} finding(s)."), findings


def analyze(language: str, source: str) -> tuple[list[AnalyzerStatus], list[Finding]]:
    if language == "python":
        ruff_status, ruff_findings = _ruff(source)
        bandit_status, bandit_findings = _bandit(source)
        return [ruff_status, bandit_status], ruff_findings + bandit_findings
    if language in {"javascript", "typescript"}:
        status, findings = _eslint(source, language)
        return [status], findings
    status, findings = _checkstyle(source)
    return [status], findings


def calculate_quality_score(finding_count: int) -> int:
    return max(0, min(100, 100 - 5 * finding_count))
