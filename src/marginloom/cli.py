"""The installed marginloom command-line interface."""
import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .model import InputError
from .table_io import load_contract,load_table
from .solve import inspect_table
from .reporting import write_report
from .verify import verify_report

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(prog='marginloom',description='Exact two-dimensional decimal rounding for coherent reports.')
    parser.add_argument('--version',action='version',version=__version__)
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ('round','inspect','verify'):
        sub=commands.add_parser(name)
        sub.add_argument('input',type=Path);sub.add_argument('--contract',type=Path,required=True)
        if name=='round':sub.add_argument('--out',type=Path,required=True)
        if name=='verify':sub.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='verify':
            v=verify_report(args.input,args.contract,args.report);data=v.to_dict();code=0 if v.valid else 4
        elif args.command=='round':
            result=write_report(args.input,args.contract,args.out)
            data={'status':result.status,'report':str(args.out)}
            if 'diagnosis' in result.data:data['diagnosis']=result.data['diagnosis']
            code={'optimal':0,'infeasible':3,'error':1,'incomplete':130}[result.status]
        else:
            contract=load_contract(args.contract);table=load_table(args.input,contract)
            data=inspect_table(table,contract);code={'feasible':0,'infeasible':3,'error':1}[data['status']]
        print(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2));return code
    except InputError as exc:
        print(json.dumps({'status':'invalid_input','message':str(exc)},ensure_ascii=False),file=sys.stderr);return 2
    except KeyboardInterrupt:
        print('{"status":"incomplete","message":"Interrupted."}',file=sys.stderr);return 130
    except OSError as exc:
        print(json.dumps({'status':'error','message':str(exc)},ensure_ascii=False),file=sys.stderr);return 1
