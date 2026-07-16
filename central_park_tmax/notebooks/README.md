# Notebooks

Analysis notebooks that consume artifacts produced by the pipelines (`data/`, `reports/`).
They are optional exploration aids; the CLI + Python API are the primary interface.

- `01_data_audit` — GHCN observation coverage, QC flags, plausibility.
- `02_report_version_audit` — NWS CLI report versions, revisions, expiration eligibility.
- `03_feature_exploration` — feature distributions and target relationships.
- `04_model_comparison` — backtest metrics by model and forecast vintage.
- `05_contract_calibration` — integer/contract probability reliability diagrams.

Generate the inputs first, e.g. `python -m central_park_tmax demo --synthetic`, then open a
notebook and load the CSV/JSON artifacts under `data/` and `reports/`.
