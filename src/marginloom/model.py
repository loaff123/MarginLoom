"""Public data models and practical input limits."""
from dataclasses import dataclass, field
from typing import Any

MAX_BYTES = 16 * 1024 * 1024
MAX_CELLS = 10_000
MAX_AXIS = 1_000
MAX_ID = 1_024
MAX_TOKEN = 256
MAX_DIGITS = 128
MAX_EXPONENT = 1_000

class InputError(ValueError):
    """The input does not satisfy the declared schema."""

def valid_id(value: Any) -> bool:
    if not isinstance(value, str) or not 0 < len(value) <= MAX_ID or '\0' in value:
        return False
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return True

@dataclass(frozen=True)
class Table:
    row_ids: tuple[str, ...]
    column_ids: tuple[str, ...]
    values: tuple[tuple[str, ...], ...]
    row_label: str = 'row'

    def __post_init__(self):
        from .decimal_codec import parse_decimal
        if not valid_id(self.row_label):
            raise InputError('row_label must be a nonempty string without NUL')
        for name in ('row_ids', 'column_ids'):
            raw = getattr(self, name)
            if isinstance(raw, (str, bytes)):
                raise InputError(f'{name} must be a sequence of IDs')
            try: ids = tuple(raw)
            except TypeError as exc: raise InputError(f'{name} must be a sequence') from exc
            if not 1 <= len(ids) <= MAX_AXIS or any(not valid_id(x) for x in ids):
                raise InputError(f'{name} must contain 1..{MAX_AXIS} valid IDs')
            if len(set(ids)) != len(ids):
                raise InputError(f'duplicate {name}')
            object.__setattr__(self, name, ids)
        if self.row_label in self.column_ids:
            raise InputError('row_label conflicts with a numeric column ID')
        if len(self.row_ids) * len(self.column_ids) > MAX_CELLS:
            raise InputError(f'table exceeds {MAX_CELLS} cells')
        try:
            if isinstance(self.values, (str, bytes)) or any(isinstance(x,(str,bytes)) for x in self.values):
                raise InputError('values must be a rectangular matrix')
            matrix = tuple(tuple(row) for row in self.values)
        except TypeError as exc: raise InputError('values must be a rectangular matrix') from exc
        if len(matrix) != len(self.row_ids) or any(len(row) != len(self.column_ids) for row in matrix):
            raise InputError('values must match row and column dimensions')
        for i, row in enumerate(matrix):
            for j, value in enumerate(row):
                try: parse_decimal(value)
                except InputError as exc: raise InputError(f'cell {self.row_ids[i]!r}/{self.column_ids[j]!r}: {exc}') from exc
        object.__setattr__(self, 'values', matrix)

@dataclass
class Result:
    status: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {'status': self.status, **self.data}

@dataclass
class Verification:
    valid: bool
    errors: list[str] = field(default_factory=list)
    scope: str = 'feasibility_and_arithmetic_not_optimality'

    def to_dict(self) -> dict:
        return {'valid':self.valid,'scope':self.scope,'errors':self.errors}
