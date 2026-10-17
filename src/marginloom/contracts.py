"""The two deliberately separate rounding contracts."""
from dataclasses import dataclass
from .decimal_codec import parse_decimal
from .model import InputError, valid_id

@dataclass(frozen=True)
class Contract:
    mode: str
    quantum: str
    row_label: str
    nonnegative: bool = False
    row_targets: dict[str,str] | None = None
    column_targets: dict[str,str] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> 'Contract':
        required = {'schema_version','mode','quantum','row_label'}
        allowed = required | {'nonnegative','row_targets','column_targets'}
        if not isinstance(data,dict) or not required <= data.keys() or data.keys() - allowed:
            raise InputError('contract has missing or unknown keys')
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise InputError('schema_version must be integer 1')
        if data['mode'] not in ('balanced','prescribed'):
            raise InputError('mode must be balanced or prescribed')
        n,_ = parse_decimal(data['quantum'])
        if n <= 0: raise InputError('quantum must be positive')
        if not valid_id(data['row_label']): raise InputError('invalid row_label')
        if type(data.get('nonnegative',False)) is not bool:
            raise InputError('nonnegative must be boolean')
        targets = {}
        for name in ('row_targets','column_targets'):
            if data['mode'] == 'balanced':
                if name in data: raise InputError('balanced mode forbids prescribed targets')
                targets[name] = None
            else:
                value = data.get(name)
                if not isinstance(value,dict) or not value or any(not valid_id(k) for k in value):
                    raise InputError(f'{name} must be an object keyed by every input ID')
                for token in value.values(): parse_decimal(token)
                targets[name] = dict(value)
        return cls(data['mode'],data['quantum'],data['row_label'],data.get('nonnegative',False),**targets)

    def to_dict(self) -> dict:
        data = {'schema_version':1,'mode':self.mode,'quantum':self.quantum,
                'row_label':self.row_label,'nonnegative':self.nonnegative}
        if self.mode == 'prescribed':
            data.update(row_targets=self.row_targets,column_targets=self.column_targets)
        return data
