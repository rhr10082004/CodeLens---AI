import shutil
from pathlib import Path

import pytest

import app.analysis as analysis
from app.analysis import analyze


@pytest.mark.parametrize(
    ("language", "source", "expected_rule"),
    [
        ("javascript", "const value = 1 == '1';\n", "eqeqeq"),
        ("typescript", "const value: number = 1 == 1;\n", "eqeqeq"),
    ],
)
def test_eslint_reports_real_rule_and_line(language: str, source: str, expected_rule: str) -> None:
    if not shutil.which("node"):
        pytest.skip("Node.js is not installed.")
    statuses, findings = analyze(language, source)
    if not statuses[0].available:
        pytest.skip(statuses[0].message)
    assert statuses[0].name == "ESLint"
    assert any(item.id.startswith(f"eslint-{expected_rule}-") and item.line == 1 for item in findings)


def test_java_reports_analyzer_unavailable_without_configuration() -> None:
    statuses, findings = analyze("java", "class Example {}")
    assert len(statuses) == 1
    assert statuses[0].name == "Checkstyle"
    if not statuses[0].available:
        assert findings == []
        assert "not compiled or executed" in statuses[0].message


def test_checkstyle_results_are_parsed_as_static_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jar = tmp_path / "checkstyle.jar"
    jar.write_bytes(b"test placeholder")
    monkeypatch.setattr(
        analysis,
        "get_settings",
        lambda: type("TestSettings", (), {"checkstyle_jar": str(jar)})(),
    )
    monkeypatch.setattr(analysis.shutil, "which", lambda _name: "java")
    report = (
        '<checkstyle><file name="Submitted.java"><error line="2" severity="warning" '
        'message="Use braces" source="com.puppycrawl.tools.checkstyle.checks.blocks.NeedBracesCheck"/>'
        "</file></checkstyle>"
    )
    monkeypatch.setattr(analysis, "_run", lambda *_args: (True, report, ""))
    status, findings = analysis._checkstyle("class Example {\nif (true) return;\n}")
    assert status.available
    assert findings[0].line == 2
    assert findings[0].evidence == "if (true) return;"
    assert findings[0].analyzer == "Checkstyle"
