"""Decimal text to integer coefficient/exponent, without floating arithmetic."""
import re
from .model import InputError, MAX_TOKEN, MAX_DIGITS, MAX_EXPONENT

_PATTERN = re.compile(r'([+-]?)([0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE]([+-]?[0-9]+))?\Z')

def parse_decimal(text: str) -> tuple[int,int]:
    if not isinstance(text, str) or not text or len(text) > MAX_TOKEN:
        raise InputError(f'decimal must be a string of 1..{MAX_TOKEN} characters')
    match = _PATTERN.fullmatch(text)
    if match is None:
        raise InputError(f'invalid finite decimal string: {text!r}')
    sign, mantissa, exp = match.groups()
    digits = mantissa.replace('.', '')
    if len(digits) > MAX_DIGITS:
        raise InputError(f'decimal mantissa exceeds {MAX_DIGITS} digits')
    exponent = int(exp or '0')
    if abs(exponent) > MAX_EXPONENT:
        raise InputError(f'decimal exponent exceeds +/-{MAX_EXPONENT}')
    exponent -= len(mantissa.partition('.')[2])
    value = int(digits) * (-1 if sign == '-' else 1)
    return (value, exponent) if value else (0,0)

def format_scaled(amount: int, exponent: int) -> str:
    if amount == 0: return '0'
    sign = '-' if amount < 0 else ''
    digits = str(abs(amount))
    if exponent >= 0: return sign + digits + '0' * exponent
    pos = len(digits) + exponent
    if pos <= 0: text = '0.' + '0' * -pos + digits
    else: text = digits[:pos] + '.' + digits[pos:]
    return sign + text.rstrip('0').rstrip('.')

def floor_ceil(amount: int, quantum: int) -> tuple[int,int]:
    lo, remainder = divmod(amount, quantum)
    return lo, lo + bool(remainder)

def nearest_even(amount: int, quantum: int) -> int:
    lo, remainder = divmod(amount, quantum)
    return lo + (2 * remainder > quantum or (2 * remainder == quantum and lo % 2 != 0))

def common_scale(tokens: list[str]) -> tuple[list[int],int]:
    parsed = [parse_decimal(x) for x in tokens]
    exponent = min(e for _,e in parsed)
    return [n * 10 ** (e-exponent) for n,e in parsed], exponent
