"""Strict labeled CSV/JSON source loading."""
import csv
import io
import json
from pathlib import Path
from .model import InputError, Table, MAX_BYTES
from .contracts import Contract

def read_bytes(path: Path) -> bytes:
    with Path(path).open('rb') as stream: data = stream.read(MAX_BYTES+1)
    if len(data) > MAX_BYTES: raise InputError(f'{path}: exceeds {MAX_BYTES} bytes')
    return data

def _pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result: raise InputError(f'duplicate JSON key {key!r}')
        result[key] = value
    return result

def strict_json(text: str):
    try:
        return json.loads(text,object_pairs_hook=_pairs,
                          parse_constant=lambda token: (_ for _ in ()).throw(InputError(f'invalid JSON constant {token}')))
    except (ValueError, RecursionError) as exc:
        raise InputError(f'invalid JSON: {exc}') from exc

def decode(data: bytes) -> str:
    try: return data.decode('utf-8-sig')
    except UnicodeDecodeError as exc: raise InputError('source must be UTF-8') from exc

def load_contract(path: Path) -> Contract:
    return Contract.from_dict(strict_json(decode(read_bytes(path))))

def load_table(path: Path, contract: Contract) -> Table:
    return table_from_bytes(read_bytes(path), Path(path).suffix.lower(), contract)

def table_from_bytes(raw: bytes, suffix: str, contract: Contract) -> Table:
    text = decode(raw)
    if suffix == '.json':
        data = strict_json(text)
        keys = {'schema_version','row_label','rows','columns','values'}
        if not isinstance(data,dict) or data.keys() != keys:
            raise InputError('table JSON has missing or unknown keys')
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise InputError('table schema_version must be integer 1')
        if any(not isinstance(data[k],list) for k in ('rows','columns','values')) or any(not isinstance(row,list) for row in data['values']):
            raise InputError('rows, columns and each values row must be JSON arrays')
        if data['row_label'] != contract.row_label: raise InputError('row_label differs from contract')
        return Table(data['rows'],data['columns'],data['values'],data['row_label'])
    try: rows = list(csv.reader(io.StringIO(text,newline=''),strict=True))
    except csv.Error as exc: raise InputError(f'invalid CSV: {exc}') from exc
    if not rows: raise InputError('empty CSV')
    header = rows[0]
    if len(header) != len(set(header)) or header.count(contract.row_label) != 1:
        raise InputError('CSV requires unique headers and exactly the designated row_label')
    label = header.index(contract.row_label)
    if any(len(row) != len(header) for row in rows[1:]): raise InputError('ragged CSV')
    return Table([row[label] for row in rows[1:]],
                 header[:label]+header[label+1:],
                 [row[:label]+row[label+1:] for row in rows[1:]], contract.row_label)
