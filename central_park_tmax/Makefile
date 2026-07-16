.PHONY: help install install-dev test lint demo build-observations build-report-archive \
        build-forecast-archive build-dataset backtest train predict run-daily clean

PY ?= python
PKG = central_park_tmax

help:
	@echo "Targets:"
	@echo "  install            Install core package (pip install -e .)"
	@echo "  install-dev        Install with dev + boosting extras"
	@echo "  test               Run the pytest suite"
	@echo "  demo               Run the offline synthetic end-to-end smoke test"
	@echo "  build-observations Download & process GHCN-Daily observations"
	@echo "  build-report-archive  Retrieve & version NWS Daily Climate Reports"
	@echo "  build-dataset      Build the leakage-safe training dataset"
	@echo "  backtest           Rolling-origin backtest with metrics + plots"
	@echo "  train              Train the residual models"
	@echo "  run-daily          Produce tomorrow's forecast + contract probabilities"

install:
	$(PY) -m pip install -e .

install-dev:
	$(PY) -m pip install -e ".[dev,boosting]"

test:
	$(PY) -m pytest -q

demo:
	$(PY) -m $(PKG) demo --synthetic

build-observations:
	$(PY) -m $(PKG) build-observations

build-report-archive:
	$(PY) -m $(PKG) build-report-archive

build-forecast-archive:
	$(PY) -m $(PKG) build-forecast-archive

build-dataset:
	$(PY) -m $(PKG) build-dataset

backtest:
	$(PY) -m $(PKG) backtest

train:
	$(PY) -m $(PKG) train

predict:
	$(PY) -m $(PKG) predict-tomorrow

run-daily:
	$(PY) -m $(PKG) run-daily

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
