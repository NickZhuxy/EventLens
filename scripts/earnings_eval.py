#!/usr/bin/env python3
"""Run A/D offline, or verify saved outputs and reproduce the saved results table."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from eventlens.cli import main as cli
from eventlens.core import load_corpus, digest
from eventlens.pipeline import run_pair
from eventlens.challenges import make_challenges
from eventlens.evaluation import score, report_text

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE_FIELDS=['case','method','source_hashes','input_hash','extractions','explanations',
                 'comparison','explanation_conclusion','conclusion','errors','calls','tokens','trace']


def seal(folder):
    paths=sorted(p for p in folder.rglob('*') if p.is_file() and p.name not in {'bundle_hashes.json','replay.json'})
    (folder/'bundle_hashes.json').write_text(json.dumps({str(p.relative_to(folder)):digest(p.read_bytes()) for p in paths},indent=2)+'\n')


def replay(folder):
    hashes=json.loads((folder/'bundle_hashes.json').read_text())
    for name,h in hashes.items():
        p=(folder/name).resolve()
        if not p.is_relative_to(folder.resolve()) or digest(p.read_bytes())!=h:
            raise ValueError('saved bundle hash mismatch: '+name)
    provenance=json.loads((folder/'provenance.json').read_text())
    for name,h in provenance['input_file_hashes'].items():
        if digest((ROOT/name).read_bytes())!=h:raise ValueError('input changed: '+name)
    for name,h in provenance['code_hashes'].items():
        if digest((ROOT/'src/eventlens'/name).read_bytes())!=h:raise ValueError('code changed: '+name)
    _,sources=load_corpus(ROOT/'data/manifest.json')
    cases=json.loads((ROOT/'data/cases.json').read_text())
    variants={c['case_id']:data for data,c in make_challenges(sources,cases[0])}
    runs=[]
    for p in sorted((folder/'runs').glob('*.json')):
        saved=json.loads(p.read_text())
        if saved['method'] not in {'A','D'}:raise ValueError('this replay verifies deterministic A/D only')
        data=variants.get(saved['case']['case_id'],sources)
        reproduced=run_pair(data,saved['case'],saved['method'],config=saved['config'],cutoff_mode=saved['cutoff_mode'])
        for field in EVIDENCE_FIELDS:
            if reproduced[field]!=saved[field]:raise ValueError(f'{p.name}: replay mismatch in {field}')
        runs.append(saved)
    summary=json.loads((folder/'summary.json').read_text())
    labels=json.loads((folder/'labels_used.json').read_text())
    measured=score(runs,labels)
    # Floating latency sums depend on ordering; replay retains recorded latency.
    for m in measured:
        reference=next(x for x in summary['metrics'] if (x['method'],x['split'])==(m['method'],m['split']))
        for key,value in m.items():
            if key=='latency_ms_sum':
                if abs(value-reference[key])>1e-6:raise ValueError('latency aggregation mismatch')
            elif value!=reference[key]:raise ValueError('score mismatch: '+key)
    if report_text(summary)!=(folder/'report.md').read_text():raise ValueError('report mismatch')
    return {'verified_runs':len(runs),'network_calls':0,'model_calls':0,'saved_table_reproduced':True,
            'raw_bundle_hashes_verified':len(hashes),'excluded_fields':'new run UUID, execution time and latency',
            'labels':'AI drafts for three original pairs; remaining pairs pending; zero human-reviewed labels'}


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--out',type=Path);g.add_argument('--replay',type=Path);g.add_argument('--seal',type=Path)
    args=p.parse_args()
    if args.out:
        with contextlib.redirect_stdout(io.StringIO()):
            rc=cli(['--root',str(ROOT),'evaluate','--out',str(args.out)])
        if rc:raise SystemExit(rc)
        seal(args.out);result=replay(args.out)
    elif args.seal:
        seal(args.seal);result=replay(args.seal)
    else:result=replay(args.replay)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
