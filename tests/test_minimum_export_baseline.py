from trd_bot.main import app
from trd_bot.research import (
    EXPERIMENT_REPORT_CSV_COLUMNS,
    EXPERIMENT_REPORT_CSV_SCHEMA_VERSION,
)

MINIMUM_EXPORT_PATH = (
    "/api/v1/research/experiments/{experiment_id}/report/presets/{preset_id}/export.csv"
)


def test_v02_minimum_export_surface_is_one_versioned_csv_operation() -> None:
    paths = app.openapi()["paths"]
    export_operations = {
        (method.upper(), path)
        for path, path_item in paths.items()
        for method in path_item
        if "export" in path
    }

    assert export_operations == {("GET", MINIMUM_EXPORT_PATH)}

    success = paths[MINIMUM_EXPORT_PATH]["get"]["responses"]["200"]
    assert success["content"]["text/csv"]["schema"] == {"type": "string"}


def test_v02_minimum_export_schema_identity_is_frozen() -> None:
    assert EXPERIMENT_REPORT_CSV_SCHEMA_VERSION == "experiment-report-csv-v1"
    assert EXPERIMENT_REPORT_CSV_COLUMNS == ("section", "metric", "value")
