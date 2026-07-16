"""Data acquisition & archival: observations, NWS reports, numerical forecasts."""


class DataSourceError(RuntimeError):
    """Base class for data-source failures."""


class ForecastSourceUnavailable(DataSourceError):
    """A forecast source cannot be used in the current environment.

    Raised (never silently swallowed) when required dependencies (e.g. cfgrib/Herbie)
    or network access are missing. Callers fall back explicitly and record the reason.
    """


class ReportParseError(DataSourceError):
    """The NWS Daily Climate Report could not be parsed into the expected schema."""


class ObservationError(DataSourceError):
    """Observation retrieval/parsing failed."""
