# Contributing

CodeLens AI is a standalone project. Keep changes scoped to this repository.

## Local checks

- Backend: `cd backend; pip install -r requirements-dev.txt; pytest`
- Frontend: `cd frontend; npm ci; npm test; npm run build`

## Safety expectations

- Never execute submitted code or repository contents.
- Do not commit credentials, `.env`, databases, virtual environments, or build outputs.
- Keep static analyzer output distinguishable from AI-generated hypotheses.
- Add tests for behavior changes and validate ownership checks for user data.
- Report analyzer limitations explicitly; do not fabricate findings or line numbers.

Use focused pull requests and describe any required environment or migration changes.
