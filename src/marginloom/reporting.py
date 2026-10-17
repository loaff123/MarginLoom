"""Standalone reports with exclusive destinations and explicit incomplete state."""
import csv
import hashlib
import html
import json
import os
from pathlib import Path
from .contracts import Contract
from .model import Result
from .table_io import read_bytes,decode,strict_json,table_from_bytes
from .solve import solve
from .verify import verify_report

_FIELDS = ['source','lower','upper','nearest','selected','delta']

def _json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def _csv(path,rows):
    with path.open('w',encoding='utf-8',newline='') as stream:
        csv.writer(stream,lineterminator='\n').writerows(rows)

def _html(data):
    esc=lambda x:html.escape(str(x),quote=True)
    title='MarginLoom rounding report' if data['status']=='optimal' else 'MarginLoom infeasible contract'
    body=[f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>',
          '<style>body{font:16px system-ui,sans-serif;max-width:1100px;margin:3em auto;padding:0 1em;color:#193442;background:#f9fcfd}h1,h2{color:#173d58}table{border-collapse:collapse;margin:1em 0;width:100%}th,td{padding:.55em;border:1px solid #c7d7df;text-align:right;overflow-wrap:anywhere}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}.note{padding:1em;border-left:4px solid #418f9e;background:#edf5f7}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>',
          f'<h1>{title}</h1><p>Contract: <strong>{esc(data["contract"]["mode"])}</strong>. Quantum: {esc(data["contract"]["quantum"])} in original source units.</p>']
    if data['status']=='infeasible':
        d=data['diagnosis'];body.append(f'<p class="note">{esc(d["message"])}</p>')
        if d['kind']=='capacity_cut':
            body.append(f'<p>Rows: {esc(", ".join(d["rows"]) or "(none)")}. Columns: {esc(", ".join(d["columns"]) or "(none)")}.</p>')
            body.append(f'<p>Required residual flow: {d["required"]}; available capacity: {d["available"]}; shortage: {d["shortage"]}, all in integer quantum increments.</p><p>This is one sufficient obstruction, not a unique or minimum-cardinality explanation.</p>')
        body.append(f'<pre>{esc(json.dumps(d,ensure_ascii=False,indent=2))}</pre><p>No rounded table was produced. Choose a different explicit contract or provide compatible targets; no target repair was performed.</p>')
    else:
        o=data['objective'];body.append(f'<p class="note">Feasibility and arithmetic checked independently. The integer-flow backend reports an optimum for this contract; the saved-report verifier does not prove optimality.</p><p>Absolute changes: cells {esc(o["cells"])}, rows {esc(o["rows"])}, columns {esc(o["columns"])}. Primary objective: {esc(o["primary"])}.</p>')
        body.append('<h2>Rounded values</h2><div class="scroll"><table><thead><tr>')
        for label in [data['row_label'],*data['columns'],'Row total']:body.append(f'<th>{esc(label)}</th>')
        body.append('</tr></thead><tbody>')
        for label,row,margin in zip(data['rows'],data['selected'],data['margins']['rows']):
            body.append('<tr>'+''.join(f'<td>{esc(x)}</td>' for x in [label,*row,margin['selected']])+'</tr>')
        body.append('<tr>'+''.join(f'<th>{esc(x)}</th>' for x in ['Column total',*[x['selected'] for x in data['margins']['columns']],data['margins']['grand']['selected']])+'</tr></tbody></table></div>')
        body.append('<h2>Margin reconciliation</h2><div class="scroll"><table><tr>'+''.join(f'<th>{esc(x)}</th>' for x in ['Axis','ID',*_FIELDS])+'</tr>')
        for axis,plural in [('Row','rows'),('Column','columns')]:
            for item in data['margins'][plural]:body.append('<tr>'+''.join(f'<td>{esc(x)}</td>' for x in [axis,item['id'],*[item[k] for k in _FIELDS]])+'</tr>')
        body.append('</table></div>')
        cell_departures=sum(c['selected']!=c['nearest'] for row in data['cells'] for c in row)
        margin_departures=sum(x['selected']!=x['nearest'] for group in ('rows','columns') for x in data['margins'][group])
        body.append(f'<h2>Why some numbers differ from separate rounding</h2><p>{cell_departures} cells and {margin_departures} margins differ from independently nearest-even rounding. Joint cell, row, column and grand-total constraints can require those choices. Ties may resolve differently with another backend version.</p>')
        if data['contract']['mode']=='prescribed':body.append('<p>Prescribed mode minimizes cell error. The recorded row and column errors are fixed by caller targets and are not part of its primary objective.</p>')
    body.append('<p>For ordinary reporting. Rounding changes values; this is not a privacy, financial or legal guarantee. Hashes bind file identity, not authenticity. CSV labels are preserved verbatim: import labels as text in spreadsheet applications.</p></html>')
    return ''.join(body)+'\n'

def _publish_file(source,destination):
    os.replace(source,destination)

def _finish(destination,staging):
    staging.rmdir()
    (destination/'INCOMPLETE').unlink()

def write_report(input_path:Path,contract_path:Path,destination:Path) -> Result:
    input_path,contract_path,destination=map(Path,(input_path,contract_path,destination))
    input_bytes=read_bytes(input_path);contract_bytes=read_bytes(contract_path)
    contract=Contract.from_dict(strict_json(decode(contract_bytes)))
    table=table_from_bytes(input_bytes,input_path.suffix.lower(),contract)
    # Reject invalid input before reserving a destination. solve still validates its API inputs.
    from .flow import prepare
    prepare(table,contract)
    destination.mkdir(exist_ok=False)
    marker=destination/'INCOMPLETE';stage=destination/'.staging'
    try:
        marker.write_text('Report has not completed independent verification and publication.\n',encoding='utf-8')
        stage.mkdir()
        result=solve(table,contract)
        if result.status not in ('optimal','infeasible'):
            marker.write_text(json.dumps(result.to_dict())+'\n',encoding='utf-8');return result
        data=result.to_dict()
        data['sources']={'input_sha256':hashlib.sha256(input_bytes).hexdigest(),'contract_sha256':hashlib.sha256(contract_bytes).hexdigest()}
        if result.status=='optimal':
            _csv(stage/'rounded.csv',[[table.row_label,*table.column_ids]]+[[label,*row] for label,row in zip(table.row_ids,data['selected'])])
            margins=[['axis','id',*_FIELDS]]
            for axis,plural in [('row','rows'),('column','columns')]:
                for item in data['margins'][plural]:margins.append([axis,item['id'],*[item[k] for k in _FIELDS]])
            margins.append(['grand','',*[data['margins']['grand'][k] for k in _FIELDS]])
            _csv(stage/'margins.csv',margins)
            metadata='audit.json';artifacts=['rounded.csv','margins.csv','report.html']
        else:
            data.update(schema_version=1,contract=contract.to_dict(),rows=list(table.row_ids),columns=list(table.column_ids))
            metadata='diagnosis.json';artifacts=['report.html']
        (stage/'report.html').write_text(_html(data),encoding='utf-8')
        data['artifacts']={name:hashlib.sha256((stage/name).read_bytes()).hexdigest() for name in artifacts}
        _json(stage/metadata,data)
        verification=verify_report(input_path,contract_path,stage)
        if not verification.valid:raise RuntimeError('staged report failed independent verification: '+'; '.join(verification.errors))
        for name in artifacts+[metadata]:_publish_file(stage/name,destination/name)
        _finish(destination,stage)
        return result
    except KeyboardInterrupt:
        result=Result('incomplete',{'diagnosis':{'kind':'interrupted','message':'Report publication was interrupted.'}})
    except Exception as exc:
        result=Result('error',{'diagnosis':{'kind':'report_error','message':f'{type(exc).__name__}: {exc}'}})
    try:marker.write_text(json.dumps(result.to_dict())+'\n',encoding='utf-8')
    except OSError:pass
    return result
