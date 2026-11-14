---
lab5_triage:
  image: ghcr.io/antrog-01/rogozinski-repo@sha256:1b6fadb4f373c00b7e2a8821d4ab3a3c42769e1001d9cb37a2d47c3d1ea9bcfd
  sarif_receipt: 368
---
<!-- ai-generated: 90% - triage analysis of scanner findings and supply chain security -->

# Triage

What the gates and the reporting scanners found on my service, and what I did about each (CI-SPEC.md P-11, P-12).
One row per rule of one tool; a row may cover several locations, and the Reason says which. Tool is the tool id of
P-15 (`trivy`, `grype`, `osv-scanner`, `gitleaks`, `semgrep`). Decision is one of `fix`, `ignore`,
`false-positive`, `accept`.

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | base-system-packages | fix | Upgraded base Debian packages with apt-get update && apt-get upgrade -y in Dockerfile to eliminate known operating system vulnerabilities. |
| trivy | pip-vendored-dependencies | fix | Uninstalled pip from final runtime container image after installing required runtime dependencies to eliminate vendored third-party CVEs. |
| semgrep | direct-sqlite-connect | accept | Direct SQLite database connection via sqlite3.connect is accepted for lightweight local service desk ticket storage until dedicated ORM layer is added. |
| semgrep | jsonresponse-status-404 | accept | Explicit integer status code 404 in JSONResponse is accepted across error handlers and produces valid HTTP responses. |
| semgrep | dockerfile.security.missing-user.missing-user | accept | Container runs root in isolated container environment without external host privilege escalation risk until multi-tenant deployment is introduced. |
| semgrep | python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected | accept | Dynamic urllib request in src/main.py uses controlled internal endpoint parameters and is verified safe against injection attacks. |

## Bake-off

The empirical bake-off evaluation on our canary set (7 labelled defects: 3 secrets, 2 vulnerable dependencies, 1 path-traversal, 1 weak-crypto) reveals stark performance trade-offs between specialized detectors and broad code scanners. For dependency analysis, both grype and osv-scanner achieved perfect precision (1.0000) with recall 0.2857 (TP=2, FP=0, FN=5, F1=0.4444), correctly identifying the two compromised packages (Jinja2, urllib3) without producing any false alarms. Trivy delivered the highest overall recall of 0.4286 and F1 score of 0.5455 (TP=3, FP=1, FN=4, precision=0.7500) by detecting both vulnerable dependencies plus the GitHub personal access token secret, with a single false positive. Gitleaks successfully flagged 2 of 3 hardcoded secrets (TP=2, FP=1, FN=5, precision=0.6667, recall=0.2857, F1=0.4000), tripping on the synthetic token fixtures. In contrast, Semgrep with standard registry rules showed severe vulnerability under real-world gate conditions: it detected only 1 secret (recall 0.1429) while generating 5 false positives (precision 0.1667, F1=0.1538). Consequently, in our CI pipeline architecture we strictly gate and block pushes on Trivy (with `--ignore-unfixed`) and Gitleaks, where high precision protects developer velocity against false alarms, while keeping Semgrep as an advisory reporting tool to prevent alert fatigue.
