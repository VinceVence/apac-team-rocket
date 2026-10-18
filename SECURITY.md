# Security

This is a synthetic prototype. Do not send real customer reports, production transaction exports or bank credentials through its public demo.

## Credentials and history

Use your own Application Default Credentials outside the repository. Never commit API keys, service-account keys, OAuth tokens, environment files, private keys, databases or raw exports. Project IDs, service-account resource names and the app URL are identifiers, not authentication secrets.

The release audit scans historical file versions as well as current files. CI runs Gitleaks with redacted output and read-only repository permissions. Pattern scanning cannot guarantee that every credential is detected. If a secret is committed, revoke or rotate it first; deleting the latest file does not erase Git history. Coordinate any history rewrite with the team.

## Agent boundaries

Reports and retrieved text are untrusted. The server binds evidence scope, validates tool arguments and retains usage reservations when execution is uncertain. Models supply advisory evidence. Analysts approve resolutions and separately activate tested safeguards. No model call occurs per payment.

Accounting survives restarts. Never reset cost counters, enable automatic retries or run multiple writers against the shared ledger. See [operations](docs/operations.md).

## Report a concern

Contact the repository owner privately. Provide affected paths and commit IDs with sensitive values redacted. Do not put secrets, customer data or exploit details in a public issue.
