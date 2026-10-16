#!/usr/bin/env python3
"""Rebuild expanded source snapshots and cases from immutable reader captures, offline."""
import argparse
from datetime import datetime, time, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from eventlens.core import digest, load_corpus, canonical
from eventlens.corpus import normalize_capture

ROOT = Path(__file__).resolve().parents[1]


def assemble(root):
    read = lambda p: json.loads((root / p).read_text())
    manifest = read('data/pilot_v1/manifest.json')
    cases = read('data/pilot_v1/cases.json')
    labels = read('data/pilot_v1/labels.draft.json')
    freeze = read('configs/corpus_v2_split.json')
    audit, outputs = [], {}
    for record in read('data/corpus_v2_selection.json')['sources']:
        raw = root / 'data' / record['capture']
        capture = json.loads(raw.read_text())
        sid = record['source_id']
        if capture['id'] != sid:
            raise ValueError('capture identity mismatch')
        text, coverage = normalize_capture(capture)
        # Metadata is audited against saved bytes, not inferred during evaluation.
        if record['release_date_evidence'] not in text.replace('\xa0', ' '):
            raise ValueError('release date evidence missing')
        date = datetime.fromisoformat(record['release_date']).date()
        at = datetime.combine(date, time(23, 59, 59), ZoneInfo('America/New_York')).isoformat()
        path = f'snapshots/{sid}.txt'
        outputs['data/' + path] = text
        manifest['sources'].append(dict(source_id=sid, issuer=sid.split('-')[0], url=capture['url'],
            published_at=at, available_at=at, retrieved_at=capture['retrieved_at'],
            reporting_period=record['reporting_period'], forecast_horizons=record['forecast_horizons'],
            content_hash=digest(text), snapshot_kind='complete_web_reader_rendered_text_not_original_HTML',
            timestamp_precision='date_only_conservative_end_America_New_York', path=path))
        audit.append(dict(source_id=sid, url=capture['url'], retrieved_at=capture['retrieved_at'],
            raw_capture=record['capture'], raw_sha256=digest(raw.read_bytes()),
            document_kind=record['document_kind'], **coverage))
    sources = {r['source_id']: r for r in manifest['sources']}
    series = {
        'ADBE': ['ADBE-2024-Q4','ADBE-2025-Q1','ADBE-2025-Q2','ADBE-2025-Q3'],
        'CRM': ['CRM-2023-Q4','CRM-2024-Q1','CRM-2024-Q2','CRM-2024-Q3'],
        'ADSK': ['ADSK-2025-Q4','ADSK-2026-Q1-SEC','ADSK-2026-Q2-SEC','ADSK-2026-Q3'],
    }
    for issuer in ['INTU','SNPS','BOX','CDNS','ZM','ZS','DDOG','OKTA','HUBS']:
        series[issuer] = [f'{issuer}-2024-Q4'] + [f'{issuer}-2025-Q{q}' for q in [1,2,3]]
    for issuer, ids in series.items():
        horizon = sources[ids[0]]['forecast_horizons'][0]
        for old, new in zip(ids, ids[1:]):
            # The original Autodesk pair stays immutable; SEC copies do not add another event.
            if any(c['issuer']==issuer and c['old'].removesuffix('-SEC')==old.removesuffix('-SEC')
                   and c['new'].removesuffix('-SEC')==new.removesuffix('-SEC') for c in cases):
                continue
            start = old.split('-')[2] if old.split('-')[1]==new.split('-')[1] else 'priorQ4'
            case_id = f'{issuer}-{horizon}-{start}-{new.split("-")[2]}'
            cutoff = (datetime.fromisoformat(sources[new]['available_at']) + timedelta(seconds=1)).isoformat()
            cases.append(dict(case_id=case_id, issuer=issuer, old=old, new=new, horizon=horizon,
                metric='revenue', cutoff=cutoff, split='development' if issuer in freeze['development_issuers'] else 'heldout', synthetic=False))
    labels['source_hashes'] = {sid:s['content_hash'] for sid,s in sources.items()}
    labels['warning'] = 'Only the original three pairs have AI-drafted labels. Expanded pairs are pending; no labels reviewed by Nick.'
    for c in cases:
        if c['case_id'] not in labels['cases']:
            labels['cases'][c['case_id']] = {'status':'pending', 'reviewed_by':None, 'reviewed_at':None}
    outputs.update({'data/manifest.json':manifest, 'data/cases.json':cases,
                    'data/labels.draft.json':labels, 'data/capture_audit_v2.json':audit})
    return outputs


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    outputs=assemble(ROOT)
    for path, value in outputs.items():
        content=value if isinstance(value,str) else json.dumps(value,indent=2,ensure_ascii=False)+'\n'
        p=ROOT/path
        if args.check:
            if not p.exists() or p.read_text()!=content: raise ValueError('rebuild mismatch: '+path)
        else:
            p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    _,sources=load_corpus(ROOT/'data/manifest.json')
    print(json.dumps({'checked':args.check,'sources':len(sources),'pairs':len(outputs['data/cases.json']),
                      'issuers':len({s.issuer for s in sources.values()}),'complete_new_captures':len(outputs['data/capture_audit_v2.json'])}))

if __name__=='__main__':main()
