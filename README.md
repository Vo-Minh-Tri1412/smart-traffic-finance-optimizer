# Vietnam Macro Early Warning System (VN-MEWS)
**"Phát hiện khủng hoảng kinh tế Việt Nam trước khi nó xảy ra"**

This repository is the technical scaffold for the VN-MEWS project (AI Quantum HVTC challenge). 
Instead of traditional CPI forecasting, this project implements a 4-layer architecture to detect macro-economic regime shifts and early warning signals of structural breaks in the Vietnamese economy.

Read the core vision document: `docs/01_VISION_AND_STRATEGY/VN_MEWS_CORE_IDEA.md`

## Architecture overview
1. **Data Ingestion**: 100+ macro signals (GSO, SBV, IMF, Google Trends, News).
2. **Anomaly Detection Engine**: Isolation Forest + LSTM Autoencoder.
3. **Regime Classification**: Hidden Markov Model (HMM) + Changepoint Detection (Ruptures).
4. **Explainability Dashboard**: SHAP values + Correlation Networks (Streamlit).

## Quick start

Ensure you have Python 3.12 and `uv` installed.

```powershell
uv sync --frozen
uv run python -m ai_quantum_hvtc doctor
uv run ruff format --check .
uv run ruff check .
uv run mypy ai_quantum_hvtc scripts
uv run pytest
```

## Agent workflow

Read `AGENTS.md` before changing files. Future write tasks must have a manifest in `coordination/tasks/` and must pass:

```powershell
uv run python scripts/admin/validate_agent_tasks.py --task coordination/tasks/<task>.toml
```

## Data & Drive Workflow

This project connects the CS (Computer Science) team and the Economics team via Google Drive.

1. **Google Drive Setup**: Both teams mount `AI Quantum HVTC — Team Workspace` using Google Drive Desktop.
2. **Economics Handoff**: The Economics team places finalized macro indicator datasets in `03_Shared_Handoffs/From_Econ_To_CS/01_Final_Training_Data`.
3. **CS Pull Data**: The CS team runs the sync script locally to pull this data:
   ```powershell
   uv run python scripts/cloud/sync_drive.py --pull-data --apply
   ```
4. **CS Push Reports**: After running anomaly detection and generating scores in the local `outputs/` folder, the CS team pushes them back to Economics:
   ```powershell
   uv run python scripts/cloud/sync_drive.py --push-reports --apply
   ```
5. **Colab Integration**: When using Google Colab for heavy training (like LSTM Autoencoder), the CS team can natively mount Drive (`drive.mount('/content/drive')`) and read/write directly to `02_CS_Workspace` and `03_Shared_Handoffs` without needing the sync script.
