#!/usr/bin/env python3
"""Install a copied project into a fresh environment and verify saved-data execution."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

root=Path(__file__).resolve().parents[1]
work=root/'work';work.mkdir(exist_ok=True)
folder=Path(tempfile.mkdtemp(prefix='fresh-check-',dir=work))
project=folder/'project';project.mkdir()
for name in ['src','tests','data','configs','fixtures','deploy']:
    shutil.copytree(root/name,project/name,ignore=shutil.ignore_patterns('__pycache__','*.egg-info','reviews.jsonl'))
shutil.copy2(root/'pyproject.toml',project/'pyproject.toml')
venv=folder/'venv'
log=[]
env=os.environ.copy();env.pop('PYTHONPATH',None)
# Live credentials are unnecessary for this check and are not propagated.
for k in ['EVENTLENS_API_KEY','OPENAI_API_KEY','DEEPSEEK_API_KEY','EVENTLENS_MODEL','EVENTLENS_BASE_URL','EVENTLENS_REASONING_EFFORT']:
    env.pop(k,None)

def execute(args):
    result=subprocess.run([str(x) for x in args],cwd=project,env=env,text=True,capture_output=True,timeout=180)
    log.append({'command':[str(x) for x in args],'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    if result.returncode:
        raise RuntimeError('fresh verification command failed; see log')
    return result.stdout

ok=False
try:
    execute([sys.executable,'-m','venv',venv])
    python=venv/'bin/python';cli=venv/'bin/eventlens'
    execute([python,'-m','pip','install','-c','deploy/requirements.lock','.[service,test]'])
    location=execute([python,'-c','import eventlens; print(eventlens.__file__)']).strip()
    if 'site-packages' not in location:raise AssertionError('not using installed package')
    execute([python,'-m','unittest','discover','-s','tests','-v'])
    inventory=json.loads(execute([cli,'validate']))
    first=json.loads(execute([cli,'ingest']));second=json.loads(execute([cli,'ingest']))
    assert first['added']==6 and second['added']==0 and second['total_sources']==6
    execute([cli,'demo']);execute([cli,'mock-demo'])
    execute([cli,'evaluate','--out','reports/fresh-offline'])
    baseline=root/'reports/offline-v2/runs';fresh=project/'reports/fresh-offline/runs'
    checked=[]
    for path in sorted(baseline.glob('*.json')):
        a=json.loads(path.read_text());b=json.loads((fresh/path.name).read_text())
        for field in ['case','source_hashes','extractions','explanations','comparison','explanation_conclusion','conclusion','errors']:
            assert a[field]==b[field],(path.name,field)
        checked.append(path.name)
    assert len(checked)==12
    macro_inventory=json.loads(execute([cli,'macro','validate']))
    assert macro_inventory['sources']==5 and macro_inventory['cases']==2
    macro_first=json.loads(execute([cli,'macro','ingest']))
    macro_second=json.loads(execute([cli,'macro','ingest']))
    assert macro_first['added']==5 and macro_second['added']==0
    execute([cli,'macro','brief','--out','work/macro-brief'])
    execute([cli,'macro','mock-demo','--repair','--out','work/macro-repair'])
    execute([cli,'macro','brief','--cutoff-mode','snapshot','--out','work/macro-strict'])
    repair=json.loads((project/'work/macro-repair/run.json').read_text())
    assert repair['execution_kind']=='mock' and repair['status']=='ready_for_review'
    assert [s['valid'] for s in repair['trace'] if s['stage']=='draft_validation']==[False,True]
    strict=json.loads((project/'work/macro-strict/run.json').read_text())
    assert strict['status']=='insufficient_evidence' and strict['eligible_source_ids']==[]
    execute([cli,'macro','evaluate','--out','reports/fresh-macro'])
    macro_checked=[]
    for case in ['july-2025-fomc','september-2025-fomc']:
        name=case+'-rules'
        original=json.loads((root/'reports/macro-v1/runs'/name/'run.json').read_text())
        copied=json.loads((project/'reports/fresh-macro/runs'/name/'run.json').read_text())
        for field in ['case','source_hashes','calendar','brief','status','validation','errors','input_hash']:
            assert original[field]==copied[field],(name,field)
        macro_checked.append(name)
    ok=True
finally:
    report={'created_at':datetime.now(timezone.utc).isoformat(),'success':ok,'fresh_directory':str(folder),
            'python':sys.version,'commands':log,'replicated_run_files':locals().get('checked',[]),
            'replicated_macro_runs':locals().get('macro_checked',[]),
            'comparison_excludes':'run UUIDs, wall-clock timestamps and latency; compares all evidence and conclusions'}
    (root/'reports/fresh_environment_macro.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'success':ok,'replicated_runs':len(checked),'replicated_macro_runs':len(macro_checked),
                  'report':'reports/fresh_environment_macro.json'}))
