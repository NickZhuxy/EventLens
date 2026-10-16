#!/usr/bin/env python3
"""Create a source-linked, unadjudicated collection/review inventory. No gold labels."""
import argparse
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from eventlens.core import load_corpus, digest

ROOT=Path(__file__).resolve().parents[1]


def span(source,needle,before=0,after=0):
    start=source.text.index(needle);end=start+len(needle)
    start=max(0,start-before);end=min(len(source.text),end+after)
    return {'source_id':source.source_id,'source_hash':source.content_hash,'url':source.url,
            'start':start,'end':end,'quote':source.text[start:end]}


def inventory():
    _,sources=load_corpus(ROOT/'data/manifest.json')
    cases=json.loads((ROOT/'data/cases.json').read_text())
    rows=[]
    for c in cases:
        row={'case_id':c['case_id'],'split':c['split'],'metric':c['metric'],'period':c['horizon'],
             'old_range':None,'new_range':None,'direction':None,'issuer_explanation':None,
             'explanation_conflict':None,'reviewed_by':None,'reviewed_at':None,'review_status':'pending'}
        for side in ['old','new']:
            s=sources[c[side]]
            year=c['horizon'][2:]; yy=year[-2:]
            pattern=rf'\b(?:FY\s*(?:{year}|{yy})|fiscal\s+(?:year\s+)?{year}|full[ -]year\s+(?:of\s+)?{year})\b'
            candidates=[]
            for m in re.finditer(pattern,s.text,re.I):
                text=s.text[max(0,m.start()-150):m.end()+900]
                if re.search(r'guidance|outlook|targets|expect',text,re.I) and re.search(r'revenue',text,re.I):
                    candidates.append(span(s,m[0],before=150,after=900) if s.text.index(m[0])==m.start() else
                                      {'source_id':s.source_id,'source_hash':s.content_hash,'url':s.url,
                                       'start':max(0,m.start()-150),'end':min(len(s.text),m.end()+900),'quote':text})
            row[side]={'source_id':s.source_id,'url':s.url,'snapshot':'data/snapshots/'+s.source_id+'.txt',
                       'source_hash':s.content_hash,'candidate_spans':candidates[:8],
                       'instruction':'Check full source; windows are collection aids, not validated labels.'}
        rows.append(row)
    def exact(sid,needle,before=0,after=0):return span(sources[sid],needle,before,after)
    natural=[
        {'kind':'one_sided_range_change','case_id':'CRM-FY2024-Q2-Q3',
         'note':'Upper bound stays at 34.8; lower bound moves from 34.7 to 34.75. Draft observation.',
         'spans':[exact('CRM-2024-Q2','Raises Full Year FY24 Revenue Guidance',1,100),exact('CRM-2024-Q3','Narrows Full Year FY24 Revenue Guidance',1,100)]},
        {'kind':'prior_guidance_restated','case_id':'INTU-FY2025-Q2-Q3',
         'note':'New guidance statement repeats the previous growth range; this is not an accounting restatement.',
         'spans':[exact('INTU-2025-Q3','up from previous guidance for growth',100,50)]},
        {'kind':'units_and_definition_change','case_id':'SNPS-FY2025-Q2-Q3',
         'note':'Old annual table uses millions; new annual headline uses billions. Acquisition also changes consolidation scope; do not assume like-for-like comparability.',
         'spans':[exact('SNPS-2025-Q2','(in millions except per share amounts)',80,500),
                  exact('SNPS-2025-Q3','Expecting full-year 2025 revenue',0,150),
                  exact('SNPS-2025-Q3','Results reflect the closing of Ansys acquisition',0,65)]},
        {'kind':'reported_vs_constant_currency','case_id':'BOX-FY2025-priorQ4-Q1',
         'note':'Reported dollar range falls while constant-currency discussion says increase. This is a basis distinction, not proof of a contradiction.',
         'spans':[exact('BOX-2024-Q4','Revenue is expected to be in the range of $1.08 billion',0,160),
                  exact('BOX-2025-Q1','Revenue is expected to be in the range of $1.075 billion',0,250)]},
        {'kind':'guidance_withdrawn','case_id':'SNPS-FY2025-Q2-WITHDRAWAL',
         'old':'SNPS-2025-Q2','new':'SNPS-2025-WITHDRAWAL','horizon':'FY2025',
         'counted_in_quarterly_pairs':False,'note':'Natural supplemental 8-K; not an Exhibit 99.1 quarterly earnings release.',
         'spans':[exact('SNPS-2025-WITHDRAWAL','In connection with BIS Letter',0,200)]},
        {'kind':'fiscal_year_rollover','case_id':'ADBE-FY2025-Q3-Q4-ROLLOVER',
         'old':'ADBE-2025-Q3','new':'ADBE-2025-Q4','counted_in_quarterly_pairs':False,
         'note':'FY2025 versus FY2026 annual targets must not be compared as revisions for the same horizon.',
         'spans':[exact('ADBE-2025-Q3','Total revenue  | $23.65',220,70),exact('ADBE-2025-Q4','Total revenue  | $25.90',220,70)]}
    ]
    for x in natural:x['review_status']='AI collected; Nick review pending'
    return {'status':'unadjudicated; not ground truth','quarterly_pairs':len(cases),'issuers':len({c['issuer'] for c in cases}),
            'development_pairs':sum(c['split']=='development' for c in cases),'heldout_pairs':sum(c['split']=='heldout' for c in cases),
            'pairs_with_both_sources_on_sec':sum(all('www.sec.gov/Archives/' in sources[c[k]].url for k in ['old','new']) for c in cases),
            'legacy_exception':'Original Autodesk Q1-Q2 issuer-site pair retained; complete SEC copies also saved. The duplicate is not counted again.',
            'split_freeze_sha256':digest((ROOT/'configs/corpus_v2_split.json').read_bytes()),
            'method_d_freeze_sha256':digest((ROOT/'configs/document_diff_freeze.json').read_bytes()),
            'human_reviewed_labels':0,'source_documents':len(sources),'review_rows':rows,'natural_hard_cases':natural}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    content=json.dumps(inventory(),indent=2,ensure_ascii=False)+'\n'
    if args.out.exists():
        if args.out.read_text()!=content:raise ValueError('refusing to replace a different review inventory')
    else:args.out.write_text(content)
    print(args.out)
