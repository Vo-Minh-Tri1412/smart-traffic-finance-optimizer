# Artifact scripts

Artifact scripts prepare local run folders before pushing outputs to Google Drive.

Expected run folder shape:

```text
artifacts/runs/<stream>/<run_id>/
├── run_config.json
├── metrics.placeholder.json
├── logs/
├── artifacts/
└── reports/
```

The `artifacts/` root is ignored by Git. Use Google Drive for real outputs.
