# Cloud / Drive scripts

These helpers implement the intended workflow:

```text
local code -> GitHub -> Colab/Kaggle
local/Drive data -> preprocess -> Google Drive Data Hub
Colab/Kaggle training output -> Google Drive Data Hub -> local via Drive Desktop
```

`drive_desktop_sync.py` works with Google Drive Desktop paths. It defaults to dry-run and never
deletes remote or local files.
