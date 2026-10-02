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

`prepare_run_dir.py` creates a management scaffold, not a scientific experiment or result.
Run IDs are portable path components; an existing ID (including a partial folder from a failed
write) is rejected without changing its contents. Choose a new ID after inspecting a failed
reservation. There is no implicit resume, overwrite option or automatic cleanup of prior artifacts.
Common experiment input hashes and seed/split identity are still pending M0 work.
