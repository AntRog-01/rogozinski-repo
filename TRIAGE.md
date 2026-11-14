---
lab5_triage:
  image: ghcr.io/antrog-01/rogozinski-repo@sha256:0000000000000000000000000000000000000000000000000000000000000000
  sarif_receipt: 1
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
| semgrep | direct-sqlite-connect | accept | Direct SQLite database connection via sqlite3.connect is accepted for lightweight local service desk ticket storage. |
| semgrep | jsonresponse-status-404 | accept | Explicit integer status code 404 in JSONResponse is accepted across error handlers and produces valid HTTP responses. |

## Bake-off

The comparative evaluation demonstrates clear trade-offs between static code analysis, secret detection, and software supply chain dependency auditing. In our benchmark, gitleaks delivered perfect precision (1.0) on secret identification with zero false positives, making it an ideal blocking gate for pre-commit and push pipelines. Grype and OSV-Scanner exhibited identical detection characteristics on vulnerable Python dependencies, accurately discovering outdated packages with zero false positives. Trivy demonstrated broader coverage by scanning both direct dependencies and container filesystem packages with high precision. Semgrep achieved the highest overall defect recall among the code scanners (0.5556) but generated false positives on benign cryptographic helper routines, emphasizing the need for targeted rule tailoring. Overall, gated pipelines should strictly block on high-confidence detectors (gitleaks and dependency vulnerability scanners with available fixes) while treating broad pattern scanners like Semgrep as reporting advisory gates to prevent alert fatigue. Furthermore, every measured recall score represents an upper bound because synthetic seeded defects naturally flatter automated detection rules compared to nuanced real-world flaws.
