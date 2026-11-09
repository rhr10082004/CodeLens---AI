# Security Policy

## Reporting

Do not disclose a suspected vulnerability publicly before it has been investigated. This project has no dedicated security contact configured yet; report issues privately to the repository owner once one is established.

## Security design

- Submitted source code is never executed by the service.
- Passwords are hashed using Argon2.
- API routes that access account or analysis data require a signed bearer token and verify user ownership.
- Secrets are read from backend environment variables and must not be committed.
- Source size, analyzer time, and request time are bounded.
- AI output is untrusted and schema-validated. AI findings are suggestions, not confirmed vulnerabilities.
- Only supported language extensions are accepted for analysis.

The application is under active development and has not undergone an independent security audit. Do not use it as a security certification or send sensitive source to an external AI provider unless authorized.
