from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, Row
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError
from sqlalchemy.exc import SQLAlchemyError

from .config import (
    get_oracle_dsn,
    get_oracle_password,
    get_oracle_user,
    get_oracle_wallet_dir,
    get_oracle_wallet_password,
)


ORACLE_TIMESTAMP_SQL = "TO_CHAR(SYSTIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')"
_ENGINE: Engine | None = None


class OracleRow:
    def __init__(self, row: Row[Any]):
        self._values = tuple(row)
        self._mapping = {str(key).lower(): value for key, value in row._mapping.items()}

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key.lower()]


class OracleCursor:
    def __init__(
        self,
        rows: Sequence[Row[Any]] | None = None,
        lastrowid: int | None = None,
    ):
        self._rows = [OracleRow(row) for row in rows or ()]
        self.lastrowid = lastrowid

    def fetchone(self) -> OracleRow | None:
        if not self._rows:
            return None
        return self._rows.pop(0)

    def fetchall(self) -> list[OracleRow]:
        rows = self._rows
        self._rows = []
        return rows


class OracleConnection:
    def __init__(self, connection: Connection):
        self._connection = connection

    def __enter__(self) -> OracleConnection:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> OracleCursor:
        if sql.strip().upper() == "BEGIN":
            return OracleCursor()

        parameters = tuple(parameters or ())
        ignore_integrity_errors = bool(
            re.match(r"^\s*INSERT\s+OR\s+IGNORE\b", sql, flags=re.IGNORECASE)
        )
        sql = re.sub(r"^\s*INSERT\s+OR\s+IGNORE\b", "INSERT", sql, flags=re.IGNORECASE)
        sql, parameters = _rewrite_datetime_now(sql, parameters)
        sql, parameters = _rewrite_limit_clause(sql, parameters)
        sql = sql.replace("CURRENT_TIMESTAMP", ORACLE_TIMESTAMP_SQL)
        prepared_sql, named_parameters = _prepare_oracle_statement(sql, parameters)

        try:
            result = self._connection.execute(text(prepared_sql), named_parameters)
            rows = result.fetchall() if result.returns_rows else []
            return OracleCursor(
                rows,
                _last_inserted_id(self._connection, sql),
            )
        except SQLAlchemyIntegrityError as error:
            if ignore_integrity_errors:
                return OracleCursor()
            raise sqlite3.IntegrityError(str(error)) from error
        except SQLAlchemyError as error:
            raise sqlite3.Error(str(error)) from error

    def executemany(
        self,
        sql: str,
        parameter_sets: Iterable[Sequence[Any]],
    ) -> OracleCursor:
        last_cursor = OracleCursor()
        for parameters in parameter_sets:
            last_cursor = self.execute(sql, parameters)
        return last_cursor

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def get_oracle_engine() -> Engine:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    connect_args: dict[str, str] = {
        "user": get_oracle_user(),
        "password": get_oracle_password(),
        "dsn": get_oracle_dsn(),
    }
    wallet_dir = get_oracle_wallet_dir()
    if wallet_dir is not None:
        connect_args["config_dir"] = wallet_dir
        connect_args["wallet_location"] = wallet_dir
    wallet_password = get_oracle_wallet_password()
    if wallet_password is not None:
        connect_args["wallet_password"] = wallet_password

    _ENGINE = create_engine("oracle+oracledb://", connect_args=connect_args, future=True)
    return _ENGINE


def get_oracle_connection() -> OracleConnection:
    return OracleConnection(get_oracle_engine().connect())


def _prepare_oracle_statement(
    sql: str,
    parameters: Sequence[Any],
) -> tuple[str, dict[str, Any]]:
    named_parameters: dict[str, Any] = {}
    pieces: list[str] = []
    parameter_index = 0
    in_single_quote = False
    character_index = 0

    while character_index < len(sql):
        character = sql[character_index]
        if character == "'":
            pieces.append(character)
            if character_index + 1 < len(sql) and sql[character_index + 1] == "'":
                pieces.append(sql[character_index + 1])
                character_index += 2
                continue
            in_single_quote = not in_single_quote
        elif character == "?" and not in_single_quote:
            if parameter_index >= len(parameters):
                raise sqlite3.Error("SQL parameter count does not match placeholders.")
            name = f"p{parameter_index}"
            pieces.append(f":{name}")
            named_parameters[name] = parameters[parameter_index]
            parameter_index += 1
        else:
            pieces.append(character)
        character_index += 1

    if parameter_index != len(parameters):
        raise sqlite3.Error("SQL parameter count does not match placeholders.")
    return "".join(pieces), named_parameters


def _rewrite_limit_clause(sql: str, parameters: Sequence[Any]) -> tuple[str, Sequence[Any]]:
    match = re.search(r"\s+LIMIT\s+(\?|\d+)\s*$", sql, flags=re.IGNORECASE)
    if match is None:
        return sql, parameters
    limit_token = match.group(1)
    remaining_parameters = parameters
    if limit_token == "?":
        if not parameters:
            raise sqlite3.Error("LIMIT placeholder is missing a value.")
        limit_value = int(parameters[-1])
        remaining_parameters = parameters[:-1]
    else:
        limit_value = int(limit_token)
    if limit_value < 1:
        raise sqlite3.Error("LIMIT must be positive.")
    return (
        f"{sql[:match.start()]} FETCH FIRST {limit_value} ROWS ONLY",
        remaining_parameters,
    )


def _rewrite_datetime_now(sql: str, parameters: Sequence[Any]) -> tuple[str, Sequence[Any]]:
    match = re.search(
        r"datetime\(\s*'now'\s*,\s*(\?|'[+-]\d+\s+hours?')\s*\)",
        sql,
        flags=re.IGNORECASE,
    )
    if match is None:
        return sql, parameters

    offset_token = match.group(1)
    remaining_parameters = list(parameters)
    if offset_token == "?":
        parameter_index = _count_placeholders(sql[: match.start(1)])
        if parameter_index >= len(remaining_parameters):
            raise sqlite3.Error("datetime offset placeholder is missing a value.")
        offset = str(remaining_parameters.pop(parameter_index))
    else:
        offset = offset_token.strip("'")

    offset_match = re.fullmatch(r"([+-])(\d+)\s+hours?", offset.strip(), re.IGNORECASE)
    if offset_match is None:
        raise sqlite3.Error(f"Unsupported datetime offset for Oracle: {offset}")

    operator = "+" if offset_match.group(1) == "+" else "-"
    hours = int(offset_match.group(2))
    oracle_expression = (
        f"TO_CHAR(SYSTIMESTAMP {operator} INTERVAL '{hours}' HOUR, "
        "'YYYY-MM-DD HH24:MI:SS')"
    )
    rewritten_sql = f"{sql[:match.start()]}{oracle_expression}{sql[match.end():]}"
    return rewritten_sql, tuple(remaining_parameters)


def _count_placeholders(sql: str) -> int:
    placeholder_count = 0
    in_single_quote = False
    character_index = 0
    while character_index < len(sql):
        character = sql[character_index]
        if character == "'":
            if character_index + 1 < len(sql) and sql[character_index + 1] == "'":
                character_index += 2
                continue
            in_single_quote = not in_single_quote
        elif character == "?" and not in_single_quote:
            placeholder_count += 1
        character_index += 1
    return placeholder_count


def _last_inserted_id(
    connection: Connection,
    sql: str,
) -> int | None:
    match = re.match(
        r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        sql,
        re.IGNORECASE,
    )
    if match is None:
        return None
    table_name = match.group(1)
    row = connection.execute(text(f"SELECT MAX(id) AS id FROM {table_name}")).fetchone()
    return int(row[0]) if row is not None and row[0] is not None else None
