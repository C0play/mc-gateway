from typing import Any
from dataclasses import dataclass

import threading
import csv
import os

from .logger import logger



@dataclass
class CSVParams:
    path: str
    fieldnames: list[str]


class CSVStorage():
    """A base class for managing files with data stored in row/column format"""
    
    def __init__(self, params: CSVParams) -> None:
        self.path = params.path
        self.fieldnames = params.fieldnames
        self.lock = threading.Lock()


    def read_rows(self) -> list[dict[str, Any]]:
        with self.lock:
            try:
                with open(self.path, mode="r", newline="") as f:
                    reader = csv.DictReader(f)
                    return [row for row in reader]
            except:
                logger.exception(f"failed to read rows")
                raise


    def insert(self, values: dict[str, Any]) -> None:
        """Append one row to the file, creating the file and header row if needed."""

        with self.lock:
            try:
                file_exists = os.path.exists(self.path)
                with open(self.path, mode="a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self.fieldnames, quoting=csv.QUOTE_NONNUMERIC)
                    if not file_exists:
                        writer.writeheader()
                    writer.writerow(values)
            except:
                logger.exception(f"failed to append row {values}")
                raise


    def delete(self, where: dict[str, Any]) -> None:
        """Remove given row from file safely. Exact field to field match is needed."""

        rows = self.read_rows()
        # Normalize types to string for consistent comparison with CSV (DictReader returns strings)
        where = {k: str(v) for k, v in where.items()}
        with self.lock:
            backup = None
            try:
                try:
                    with open(self.path, "rb") as f:
                        backup = f.read()
                except FileNotFoundError:
                    backup = None

                with open(self.path, mode="w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self.fieldnames, quoting=csv.QUOTE_NONNUMERIC)
                    writer.writeheader()
                    for r in rows:
                        logger.debug(f"{where} == {r}")
                        if where == r:
                            continue
                        logger.debug(f"writing row {r} to {self.path}")
                        writer.writerow(r)
            
            except Exception:
                logger.exception(f"failed to remove row {where}")
                if backup is not None:
                    try:
                        with open(self.path, "wb") as f:
                            f.write(backup)
                    except Exception:
                        logger.critical(f"failed to restore file from backup when removing {where}")
                raise


    def select(self, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Returns True if a row with matching key-value pairs exists.\n
        If the row has more fields than provided, returns True if every provided field matches a field in the row.\n
        If no where parameters were provided, returns all rows."""

        # Normalize where values to strings (CSV rows are all strings)
        if where is not None:
            where = {k: str(v) for k, v in where.items()}
        with self.lock:
            try:
                rows = []
                with open(self.path, mode="r", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if not where or all(row.get(key) == value for key, value in where.items()):
                            rows.append(row)  
                return rows
            except:
                logger.exception(f"failed to search for fields {where}")
                raise