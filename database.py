import argparse
import csv
import re
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pandas as pd

from bms_drivers.base import BatteryReading
from config import load_config
from log_files import find_log_files


DATABASE_FILENAME = "battery_monitor.sqlite3"
CELL_COLUMN_PATTERN = re.compile(r"^Zelle(\d+)_V$")
NUMERIC_COLUMNS = {
    "Spannung_V": "voltage_v",
    "Strom_A": "current_a",
    "Leistung_W": "power_w",
    "SOC_Prozent": "soc_percent",
    "Restkapazitaet_Ah": "remaining_capacity_ah",
    "Temp_C": "temperature_c",
    "Drift_mV": "drift_mv",
}
BASE_CSV_COLUMNS = [
    "Zeitstempel",
    "Status",
    "Spannung_V",
    "Strom_A",
    "Leistung_W",
    "SOC_Prozent",
    "Restkapazitaet_Ah",
    "Temp_C",
]


def _format_timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.replace(microsecond=0, tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    parsed = datetime.fromisoformat(str(value))
    return parsed.replace(microsecond=0, tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _optional_float(value: object, field: str, source: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{source}: invalid number in {field}: {value!r}") from error


def _bucket_expression(alias: str, bucket_seconds: int) -> str:
    if bucket_seconds == 15 * 60:
        return (
            f"strftime('%Y-%m-%d %H:', {alias}.timestamp) || "
            f"printf('%02d:00', (CAST(strftime('%M', {alias}.timestamp) AS INTEGER) "
            "/ 15) * 15)"
        )
    if bucket_seconds == 60 * 60:
        return f"strftime('%Y-%m-%d %H:00:00', {alias}.timestamp)"
    if bucket_seconds == 6 * 60 * 60:
        return (
            f"strftime('%Y-%m-%d ', {alias}.timestamp) || "
            f"printf('%02d:00:00', (CAST(strftime('%H', {alias}.timestamp) AS INTEGER) "
            "/ 6) * 6)"
        )
    if bucket_seconds == 24 * 60 * 60:
        return f"strftime('%Y-%m-%d 00:00:00', {alias}.timestamp)"
    raise ValueError(f"Unsupported aggregation interval: {bucket_seconds} seconds")


def resolution_for_span(span_days: float) -> tuple[int | None, str]:
    if span_days <= 0.25:
        return None, "1 Min (Original)"
    if span_days <= 3:
        return 15 * 60, "15 Min (Tagesansicht)"
    if span_days <= 21:
        return 60 * 60, "1 Std (Wochenansicht)"
    if span_days <= 120:
        return 6 * 60 * 60, "6 Std (Monatsansicht)"
    return 24 * 60 * 60, "1 Tag (Jahresansicht)"


class BatteryDatabase:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else Path.cwd() / DATABASE_FILENAME
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS measurements (
                    driver TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    voltage_v REAL NOT NULL,
                    current_a REAL NOT NULL,
                    power_w REAL NOT NULL,
                    soc_percent REAL NOT NULL,
                    remaining_capacity_ah REAL NOT NULL,
                    temperature_c REAL,
                    drift_mv REAL,
                    PRIMARY KEY (driver, timestamp)
                );
                CREATE TABLE IF NOT EXISTS cell_voltages (
                    driver TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    cell_index INTEGER NOT NULL,
                    voltage_v REAL NOT NULL,
                    PRIMARY KEY (driver, timestamp, cell_index),
                    FOREIGN KEY (driver, timestamp)
                        REFERENCES measurements (driver, timestamp)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS csv_imports (
                    path TEXT NOT NULL,
                    driver TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    modified_ns INTEGER NOT NULL,
                    imported_at TEXT NOT NULL,
                    rows_imported INTEGER NOT NULL,
                    PRIMARY KEY (path, driver)
                );
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def insert_reading(
        self,
        reading: BatteryReading,
        driver: str,
        timestamp: datetime | None = None,
    ) -> str:
        timestamp_text = _format_timestamp(timestamp or datetime.now())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO measurements (
                    driver, timestamp, status, voltage_v, current_a, power_w,
                    soc_percent, remaining_capacity_ah, temperature_c, drift_mv
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(driver, timestamp) DO UPDATE SET
                    status=excluded.status,
                    voltage_v=excluded.voltage_v,
                    current_a=excluded.current_a,
                    power_w=excluded.power_w,
                    soc_percent=excluded.soc_percent,
                    remaining_capacity_ah=excluded.remaining_capacity_ah,
                    temperature_c=excluded.temperature_c,
                    drift_mv=excluded.drift_mv
                """,
                (
                    driver,
                    timestamp_text,
                    reading.status,
                    reading.voltage_v,
                    reading.current_a,
                    reading.power_w,
                    reading.soc_percent,
                    reading.remaining_capacity_ah,
                    reading.temperature_c,
                    reading.drift_mv,
                ),
            )
            connection.execute(
                "DELETE FROM cell_voltages WHERE driver=? AND timestamp=?",
                (driver, timestamp_text),
            )
            connection.executemany(
                """
                INSERT INTO cell_voltages (driver, timestamp, cell_index, voltage_v)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (driver, timestamp_text, index, voltage)
                    for index, voltage in enumerate(reading.cell_voltages_v)
                ],
            )
        return timestamp_text

    def import_csv_files(self, driver: str, files: list[str] | None = None) -> int:
        imported_rows = 0
        for filename in files if files is not None else find_log_files(driver):
            path = Path(filename).resolve()
            stat = path.stat()
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    """
                    SELECT size_bytes, modified_ns FROM csv_imports
                    WHERE path=? AND driver=?
                    """,
                    (str(path), driver),
                ).fetchone()
                if (
                    prior is not None
                    and prior["size_bytes"] == stat.st_size
                    and prior["modified_ns"] == stat.st_mtime_ns
                ):
                    continue

                rows_imported = 0
                try:
                    with path.open(encoding="utf-8-sig", newline="") as csv_file:
                        reader = csv.DictReader(csv_file, delimiter=";")
                        required = {"Zeitstempel", "Status", *BASE_CSV_COLUMNS[2:7]}
                        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                            raise ValueError("CSV is missing required measurement columns.")
                        cell_columns = sorted(
                            (
                                column for column in reader.fieldnames
                                if CELL_COLUMN_PATTERN.fullmatch(column)
                            ),
                            key=lambda column: int(CELL_COLUMN_PATTERN.fullmatch(column).group(1)),
                        )
                        for row_number, row in enumerate(reader, start=2):
                            source = f"{path}:{row_number}"
                            try:
                                timestamp_text = _format_timestamp(row["Zeitstempel"])
                            except (TypeError, ValueError) as error:
                                raise ValueError(
                                    f"{source}: invalid timestamp {row.get('Zeitstempel')!r}"
                                ) from error
                            values = {
                                field: _optional_float(row.get(column), column, source)
                                for column, field in NUMERIC_COLUMNS.items()
                            }
                            for column in BASE_CSV_COLUMNS[2:7]:
                                if values[NUMERIC_COLUMNS[column]] is None:
                                    raise ValueError(f"{source}: {column} must not be empty.")
                            connection.execute(
                                """
                                INSERT INTO measurements (
                                    driver, timestamp, status, voltage_v, current_a,
                                    power_w, soc_percent, remaining_capacity_ah,
                                    temperature_c, drift_mv
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(driver, timestamp) DO UPDATE SET
                                    status=excluded.status,
                                    voltage_v=excluded.voltage_v,
                                    current_a=excluded.current_a,
                                    power_w=excluded.power_w,
                                    soc_percent=excluded.soc_percent,
                                    remaining_capacity_ah=excluded.remaining_capacity_ah,
                                    temperature_c=excluded.temperature_c,
                                    drift_mv=excluded.drift_mv
                                """,
                                (
                                    driver,
                                    timestamp_text,
                                    row["Status"],
                                    *(values[field] for field in NUMERIC_COLUMNS.values()),
                                ),
                            )
                            connection.execute(
                                "DELETE FROM cell_voltages WHERE driver=? AND timestamp=?",
                                (driver, timestamp_text),
                            )
                            cell_values = [
                                (
                                    driver,
                                    timestamp_text,
                                    int(CELL_COLUMN_PATTERN.fullmatch(column).group(1)) - 1,
                                    value,
                                )
                                for column in cell_columns
                                if (
                                    value := _optional_float(row.get(column), column, source)
                                ) is not None
                            ]
                            connection.executemany(
                                """
                                INSERT INTO cell_voltages (
                                    driver, timestamp, cell_index, voltage_v
                                ) VALUES (?, ?, ?, ?)
                                """,
                                cell_values,
                            )
                            rows_imported += 1
                except (OSError, csv.Error, ValueError) as error:
                    raise ValueError(f"Unable to import CSV file {path}: {error}") from error

                connection.execute(
                    """
                    INSERT INTO csv_imports (
                        path, driver, size_bytes, modified_ns, imported_at, rows_imported
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(path, driver) DO UPDATE SET
                        size_bytes=excluded.size_bytes,
                        modified_ns=excluded.modified_ns,
                        imported_at=excluded.imported_at,
                        rows_imported=excluded.rows_imported
                    """,
                    (
                        str(path),
                        driver,
                        stat.st_size,
                        stat.st_mtime_ns,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        rows_imported,
                    ),
                )
                imported_rows += rows_imported
        return imported_rows

    def get_bounds(self, driver: str) -> tuple[datetime | None, datetime | None]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT MIN(timestamp) AS first_timestamp, MAX(timestamp) AS last_timestamp
                FROM measurements WHERE driver=?
                """,
                (driver,),
            ).fetchone()
        if row["first_timestamp"] is None:
            return None, None
        return datetime.fromisoformat(row["first_timestamp"]), datetime.fromisoformat(
            row["last_timestamp"]
        )

    def count_readings(
        self, driver: str, start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> int:
        conditions = ["driver=?"]
        values: list[object] = [driver]
        if start is not None:
            conditions.append("timestamp>=?")
            values.append(_format_timestamp(start))
        if end is not None:
            conditions.append("timestamp<=?")
            values.append(_format_timestamp(end))
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM measurements WHERE {' AND '.join(conditions)}",
                values,
            ).fetchone()
        return int(row[0])

    def get_latest(self, driver: str) -> dict | None:
        frame = self.read_dataframe(driver, limit=1, descending=True)
        if frame.empty:
            return None
        return frame.iloc[0].to_dict()

    def read_dataframe(
        self,
        driver: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        bucket_seconds: int | None = None,
        limit: int | None = None,
        descending: bool = False,
    ) -> pd.DataFrame:
        conditions = ["m.driver=?"]
        parameters: list[object] = [driver]
        if start is not None:
            conditions.append("m.timestamp>=?")
            parameters.append(_format_timestamp(start))
        if end is not None:
            conditions.append("m.timestamp<=?")
            parameters.append(_format_timestamp(end))
        where_sql = " AND ".join(conditions)
        order_sql = "DESC" if descending else "ASC"
        with self._connect() as connection:
            if bucket_seconds is None:
                timestamp_column = "m.timestamp"
                select_columns = """
                    m.timestamp AS Zeitstempel, m.status AS Status,
                    m.voltage_v AS Spannung_V, m.current_a AS Strom_A,
                    m.power_w AS Leistung_W, m.soc_percent AS SOC_Prozent,
                    m.remaining_capacity_ah AS Restkapazitaet_Ah,
                    m.temperature_c AS Temp_C, m.drift_mv AS Drift_mV
                """
                sql_parameters = list(parameters)
                limit_sql = ""
                if limit is not None:
                    limit_sql = " LIMIT ?"
                    sql_parameters.append(limit)
                records = [
                    dict(row) for row in connection.execute(
                        f"""
                        SELECT {select_columns} FROM measurements m
                        WHERE {where_sql}
                        ORDER BY {timestamp_column} {order_sql}{limit_sql}
                        """,
                        sql_parameters,
                    )
                ]
                if limit is not None:
                    if records:
                        cell_rows = list(connection.execute(
                            "SELECT c.timestamp AS Zeitstempel, c.cell_index, c.voltage_v "
                            "FROM cell_voltages c WHERE c.driver=? AND c.timestamp IN "
                            f"({','.join('?' for _ in records)}) "
                            "ORDER BY c.timestamp, c.cell_index",
                            [driver, *(record["Zeitstempel"] for record in records)],
                        ))
                    else:
                        cell_rows = []
                else:
                    cell_rows = list(connection.execute(
                        f"""
                        SELECT c.timestamp AS Zeitstempel, c.cell_index, c.voltage_v
                        FROM cell_voltages c
                        JOIN measurements m
                          ON m.driver=c.driver AND m.timestamp=c.timestamp
                        WHERE {where_sql}
                        ORDER BY c.timestamp, c.cell_index
                        """,
                        parameters,
                    ))
            else:
                bucket = _bucket_expression("m", bucket_seconds)
                aggregate_columns = """
                    AVG(m.voltage_v) AS Spannung_V, AVG(m.current_a) AS Strom_A,
                    AVG(m.power_w) AS Leistung_W, AVG(m.soc_percent) AS SOC_Prozent,
                    AVG(m.remaining_capacity_ah) AS Restkapazitaet_Ah,
                    AVG(m.temperature_c) AS Temp_C, AVG(m.drift_mv) AS Drift_mV
                """
                bucket_parameters = list(parameters)
                limit_sql = ""
                if limit is not None:
                    limit_sql = " LIMIT ?"
                    bucket_parameters.append(limit)
                records = [
                    dict(row) for row in connection.execute(
                        f"""
                        SELECT {bucket} AS Zeitstempel, '' AS Status, {aggregate_columns}
                        FROM measurements m
                        WHERE {where_sql}
                        GROUP BY Zeitstempel
                        ORDER BY Zeitstempel {order_sql}{limit_sql}
                        """,
                        bucket_parameters,
                    )
                ]
                cell_rows = list(connection.execute(
                    f"""
                    SELECT {bucket} AS Zeitstempel, c.cell_index,
                           AVG(c.voltage_v) AS voltage_v
                    FROM cell_voltages c
                    JOIN measurements m
                      ON m.driver=c.driver AND m.timestamp=c.timestamp
                    WHERE {where_sql}
                    GROUP BY Zeitstempel, c.cell_index
                    ORDER BY Zeitstempel, c.cell_index
                    """,
                    parameters,
                ))

        cells_by_timestamp: dict[str, dict[int, float]] = defaultdict(dict)
        for cell in cell_rows:
            cells_by_timestamp[cell["Zeitstempel"]][cell["cell_index"]] = cell[
                "voltage_v"
            ]
        max_cell_index = max(
            (index for cells in cells_by_timestamp.values() for index in cells),
            default=-1,
        )
        for record in records:
            cells = cells_by_timestamp.get(record["Zeitstempel"], {})
            for index in range(max_cell_index + 1):
                record[f"Zelle{index + 1}_V"] = cells.get(index)
        frame = pd.DataFrame.from_records(records)
        if "Zeitstempel" in frame:
            frame["Zeitstempel"] = pd.to_datetime(frame["Zeitstempel"])
        return frame

    def export_csv_files(self, driver: str, output_dir: str | Path) -> list[Path]:
        frame = self.read_dataframe(driver)
        if frame.empty:
            return []
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        frame["Monat"] = frame["Zeitstempel"].dt.strftime("%Y-%m")
        exports = []
        for month, month_frame in frame.groupby("Monat", sort=True):
            filename = (
                f"battery_log_{month}.csv"
                if driver == "ecoworthy"
                else f"battery_log_{driver}_{month}.csv"
            )
            exports.append((output_path / filename, month_frame))
        existing = [path for path, _ in exports if path.exists()]
        if existing:
            raise FileExistsError(
                "Refusing to overwrite existing CSV files: "
                + ", ".join(str(path) for path in existing)
            )

        cell_columns = sorted(
            (
                column for column in frame.columns
                if CELL_COLUMN_PATTERN.fullmatch(column)
            ),
            key=lambda column: int(CELL_COLUMN_PATTERN.fullmatch(column).group(1)),
        )
        fieldnames = [*BASE_CSV_COLUMNS, *cell_columns, "Drift_mV"]
        for path, month_frame in exports:
            with path.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames, delimiter=";")
                writer.writeheader()
                for row in month_frame.to_dict(orient="records"):
                    output_row = {
                        "Zeitstempel": row["Zeitstempel"].strftime("%Y-%m-%d %H:%M:%S"),
                        "Status": row["Status"],
                    }
                    for column in fieldnames[2:]:
                        value = row.get(column)
                        output_row[column] = "" if pd.isna(value) else value
                    writer.writerow(output_row)
        return [path for path, _ in exports]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import or export battery measurement CSV files.")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--import-csv", action="store_true")
    operation.add_argument("--export-csv", action="store_true")
    parser.add_argument("--driver", help="BMS driver name (defaults to config.toml)")
    parser.add_argument(
        "--output-dir",
        default="csv-export",
        help="Export directory (default: csv-export; existing files are not overwritten)",
    )
    args = parser.parse_args()
    driver = args.driver or load_config().driver
    database = BatteryDatabase()
    if args.import_csv:
        imported = database.import_csv_files(driver)
        print(f"Imported {imported} measurement(s) for {driver}.")
    else:
        files = database.export_csv_files(driver, args.output_dir)
        print(f"Exported {len(files)} monthly CSV file(s) to {args.output_dir}.")


if __name__ == "__main__":
    main()
