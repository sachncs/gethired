# Security Policy

## Supported versions

The latest minor version of gethired receives security updates. Older
versions are best-effort.

| Version | Supported          |
|---------|--------------------|
| 0.6.x   | :white_check_mark: |
| < 0.6   | :x:                |

## Reporting a vulnerability

Please report security issues privately via GitHub's private
vulnerability reporting on the
[gethired security tab](https://github.com/gethired/gethired/security).

Do not file a public issue for suspected vulnerabilities. Include:

- A description of the issue and its impact.
- Reproduction steps or a minimal example.
- The version(s) affected.

We aim to acknowledge new reports within 5 business days and to ship a
fix within 30 days for high-severity issues.

## Data handling

gethired processes your master resume and job description URLs locally
and sends them to the configured model provider. The CLI prompts for
consent on first use and records the timestamp in
`~/.config/gethired/consent.json`. Re-prompted every 90 days.

If you import `gethired` as a library (not via the CLI), no consent
prompt fires. You are responsible for ensuring you have the right to
share the data with your model provider.
