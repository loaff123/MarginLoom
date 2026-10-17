#!/usr/bin/env python3
"""Run an installed CLI against caller-provided AirPassengers CSV and synthetic cases.

No download is performed. Source/derived cell-level real data remain in the caller's
chosen evidence directory; do not redistribute without applicable permission.
"""
import argparse
import csv
from fractions import Fraction
import hashlib
import json
import platform
from pathlib import Path
import random
import subprocess
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--executable',required=True,type=Path)
    parser.add_argument('--airpassengers',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();args.output.mkdir(exist_ok=False)
    out=args.output;results=[]
    def run(label,command,expected):
        started=time.perf_counter()
        p=subprocess.run([str(args.executable),*map(str,command)],capture_output=True,text=True,cwd=out)
        elapsed=time.perf_counter()-started
        data={'label':label,'command':[str(args.executable),*map(str,command)],'expected_exit':expected,'exit':p.returncode,'seconds':elapsed,'stdout':p.stdout,'stderr':p.stderr}
        results.append(data)
        (out/'results.json').write_text(json.dumps({'platform':platform.platform(),'python':platform.python_version(),'runs':results},indent=2))
        if p.returncode!=expected:raise RuntimeError(f'{label}: expected {expected}, got {p.returncode}: {p.stderr} {p.stdout}')
        return json.loads(p.stdout)
    def write_csv(path,rows):
        with path.open('w',newline='',encoding='utf-8') as f:csv.writer(f,lineterminator='\n').writerows(rows)
    def write_contract(path,q,mode='balanced',**extra):
        path.write_text(json.dumps({'schema_version':1,'mode':mode,'quantum':q,'row_label':'year',**extra}))
    raw=args.airpassengers.read_bytes()
    rows=list(csv.DictReader(raw.decode('utf-8').splitlines()))
    years=list(dict.fromkeys(x['year'] for x in rows));months=list(dict.fromkeys(x['month'] for x in rows))
    if len(years)!=12 or len(months)!=12 or len(rows)!=144:raise ValueError('expected the 144-value 12x12 AirPassengers example')
    cells={(x['year'],x['month']):x['passengers'] for x in rows}
    if len(cells)!=144:raise ValueError('duplicate year/month')
    matrix=[[cells[y,m] for m in months] for y in years]
    source=out/'airpassengers.csv';write_csv(source,[['year',*months],*[[y,*r] for y,r in zip(years,matrix)]])
    summary={'source_url':'https://raw.githubusercontent.com/mwaskom/seaborn-data/master/flights.csv','source_sha256':hashlib.sha256(raw).hexdigest(),'redistribution':'dataset-specific permission unestablished; raw and derived tables excluded from archive','profiles':[]}
    for base in [10,20,50,100,200]:
        contract=out/f'balanced-{base}.json';write_contract(contract,str(base));report=out/f'profile-{base}'
        run(f'round-{base}',['round',source,'--contract',contract,'--out',report],0)
        run(f'verify-{base}',['verify',source,'--contract',contract,'--report',report],0)
        audit=json.loads((report/'audit.json').read_text())
        exported=list(csv.reader((report/'rounded.csv').open()))
        selected=[[Fraction(x) for x in row[1:]] for row in exported[1:]]
        original=[[Fraction(x) for x in row] for row in matrix]
        assert all(x.denominator==1 for row in selected for x in row)
        assert sum(map(sum,selected))==round(sum(map(sum,original))/base)*base
        assert [[str(x) for x in row] for row in selected]==audit['selected']
        summary['profiles'].append({'quantum':str(base),'objective':audit['objective'],'rounded_sha256':hashlib.sha256((report/'rounded.csv').read_bytes()).hexdigest(),'verified':True})
    for base,expected in [(20,0),(10,3)]:
        nearest=out/f'prescribed-nearest-{base}.json'
        rt={y:str(round(sum(Fraction(x) for x in row)/base)*base) for y,row in zip(years,matrix)}
        ct={month:str(round(sum(Fraction(matrix[i][j]) for i in range(12))/base)*base) for j,month in enumerate(months)}
        write_contract(nearest,str(base),'prescribed',row_targets=rt,column_targets=ct)
        destination=out/f'prescribed-nearest-{base}-report'
        run(f'prescribed-nearest-{base}',['round',source,'--contract',nearest,'--out',destination],expected)
        run(f'verify-prescribed-{base}',['verify',source,'--contract',nearest,'--report',destination],0)
        if expected:
            summary[f'prescribed_nearest_{base}']=json.loads((destination/'diagnosis.json').read_text())['diagnosis']
        else:
            summary[f'prescribed_nearest_{base}']={'status':'optimal','objective':json.loads((destination/'audit.json').read_text())['objective']}
    # Saved contract, new numeric data and a new destination.
    updated=out/'airpassengers-updated.csv';copy=[row[:] for row in matrix];copy[0][0]=str(int(copy[0][0])+7)
    write_csv(updated,[['year',*months],*[[y,*r] for y,r in zip(years,copy)]])
    run('updated-source',['round',updated,'--contract',out/'balanced-20.json','--out',out/'updated-report'],0)
    run('verify-updated',['verify',updated,'--contract',out/'balanced-20.json','--report',out/'updated-report'],0)
    rng=random.Random(20261008);synthetic=out/'synthetic-100x100.csv';synthetic_contract=out/'synthetic.json'
    numbers=[[rng.randint(-10000,10000) for _ in range(100)] for _ in range(100)]
    tokens=[[('-' if v<0 else '')+str(abs(v)//10)+'.'+str(abs(v)%10) for v in row] for row in numbers]
    write_csv(synthetic,[['year',*[f'c{j}' for j in range(100)]],*[[f'r{i}',*row] for i,row in enumerate(tokens)]])
    write_contract(synthetic_contract,'1')
    run('synthetic-100x100',['round',synthetic,'--contract',synthetic_contract,'--out',out/'synthetic-report'],0)
    run('verify-synthetic-100x100',['verify',synthetic,'--contract',synthetic_contract,'--report',out/'synthetic-report'],0)
    extreme=out/'extreme.csv';write_csv(extreme,[['year','large','small'],['r0','1e1000','1e-1000']])
    extreme_contract=out/'extreme.json';write_contract(extreme_contract,'3e-1000')
    run('mixed-exponent-non-power-ten',['round',extreme,'--contract',extreme_contract,'--out',out/'extreme-report'],0)
    run('verify-extreme',['verify',extreme,'--contract',extreme_contract,'--report',out/'extreme-report'],0)
    summary.update(platform=platform.platform(),driver_python=platform.python_version(),runs=len(results),all_expected_exits=all(r['exit']==r['expected_exit'] for r in results),durations={r['label']:r['seconds'] for r in results})
    try:
        import resource
        summary['peak_child_maxrss_raw']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        summary['memory_note']='Cumulative child-process peak max RSS reported by the OS since driver start; Linux unit KiB, macOS bytes. Not a per-input guarantee.'
    except ImportError:summary['memory_note']='resource.getrusage unavailable on this platform'
    (out/'aggregate-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
