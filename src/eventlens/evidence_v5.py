"""Versioned source references and conservative annual table-column grounding.

No model labels, issuer names, or synthetic expected answers enter this module.
The old quotation validator is retained for simple rows/prose. Mixed-period tables
use a separate, explicit structural proof, never an override of its error list.
"""
from copy import deepcopy
from dataclasses import asdict
import re

from .core import Metric, canonical, digest, number
from .document_diff import candidates, sentences
from .extraction import extract, validate_evidence
from .retrieval import ReadTools


def flat(text):
    return ' '.join(text.split())


def span(source, start, end):
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source.text):
        raise ValueError('invalid_evidence_offsets')
    return {'evidence_id': 'e_'+digest(canonical([source.source_id, source.content_hash, start, end]))[:24],
            'source_id': source.source_id, 'source_hash': source.content_hash,
            'start': start, 'end': end, 'quote': source.text[start:end], 'url': source.url,
            'origin': 'synthetic' if source.snapshot_kind.startswith('SYNTHETIC') else 'disclosure',
            'literal_valid': True, 'semantic_review': 'pending'}


def pipe_rows(text, base=0):
    """Keep physical offsets while joining line breaks inside a pipe-table cell."""
    pending, start, offset = '', 0, base
    for line in text.splitlines(keepends=True):
        if not pending:
            start = offset
        pending += line
        offset += len(line)
        if '|' not in pending:
            pending = ''
            continue
        if line.rstrip().endswith('|'):
            cells = []
            for m in re.finditer(r'[^|]+', pending):
                raw = m[0]
                left, right = len(raw)-len(raw.lstrip()), len(raw.rstrip())
                if left < right:
                    cells.append({'text': raw[left:right], 'start': start+m.start()+left,
                                  'end': start+m.start()+right})
            yield {'start': start, 'end': offset-len(line)+len(line.rstrip('\n')), 'cells': cells}
            pending = ''
        elif len(pending) > 4000:
            pending = ''


def table_candidates(source, horizon):
    """Admit only fully mapped Low/High groups with explicit period headers.

    Reader text loses HTML colspan attributes. Therefore require equal counts of
    period groups, Low/High pairs, dates and dollar-value pairs in the same order.
    Other layouts abstain. The fiscal group's year must match the question AND
    source metadata. A row containing quarterly values is not itself sufficient.
    """
    if horizon not in source.forecast_horizons or not re.fullmatch(r'FY20\d{2}', horizon):
        return []
    result = []
    for heading in re.finditer(r'^.*\bFull\s+Fiscal\s+Year\s+(20\d{2})\s+(?:Financial\s+)?(?:Targets|Guidance|Outlook)\b[^\n]*', source.text, re.I | re.M):
        if 'FY'+heading[1] != horizon:
            continue
        if re.search(r'constant.currency|adjusted|non.GAAP|segment|CAD|AUD|HKD|Canadian|Australian',heading[0],re.I):
            continue
        block_end = min(len(source.text), heading.end()+2600)
        rows = list(pipe_rows(source.text[heading.end():block_end], heading.end()))
        for index, row in enumerate(rows):
            cells = row['cells']
            if not cells or not re.fullmatch(r'(?:Total\s+)?Revenue', flat(cells[0]['text']), re.I):
                continue
            before = rows[:index]
            periods = [r for r in before if r['cells'] and all(re.fullmatch(
                r'Range for (?:Three Months|Fiscal Year) Ending(?: [A-Za-z]+ \d{1,2}, 20\d{2})?',
                flat(c['text']), re.I) for c in r['cells'])]
            if len(periods) != 1:
                continue
            groups = periods[0]['cells']
            n = len(groups)
            if not 2 <= n <= 4:
                continue
            lowhigh = [r for r in before if [flat(c['text']).lower() for c in r['cells']] == ['low','high']*n]
            if len(lowhigh) != 1 or periods[0]['start'] >= lowhigh[0]['start']:
                continue
            annual = [i for i,c in enumerate(groups) if re.match(r'Range for Fiscal Year\b',flat(c['text']),re.I)]
            if len(annual) != 1:
                continue
            years = [re.findall(r'\b20\d{2}\b',c['text']) for c in groups]
            date_row = None
            if not all(len(y)==1 for y in years):
                dates = [r for r in before if periods[0]['end'] < r['start'] < lowhigh[0]['start']
                         and len(r['cells']) == n and all(re.fullmatch(
                             r'[A-Za-z]+\s+\d{1,2},\s+20\d{2}',flat(c['text'])) for c in r['cells'])]
                if len(dates) != 1 or any(years):
                    continue
                date_row = dates[0]
                years = [re.findall(r'\b20\d{2}\b',c['text']) for c in date_row['cells']]
            g = annual[0]
            if years[g] != [horizon[2:]]:
                continue
            # No unaccounted semantic table cells may occur between period and values.
            permitted = {id(periods[0]), id(lowhigh[0])}
            if date_row:
                permitted.add(id(date_row))
            if any(r['cells'] and id(r) not in permitted for r in before
                   if r['start'] >= periods[0]['start']):
                continue
            values = cells[1:]
            if len(values) != n*4:
                continue
            if any(flat(values[i]['text']) != '$' for i in range(0,len(values),2)):
                continue
            if any(not re.fullmatch(r'\d[\d,]*(?:\.\d+)?',flat(values[i]['text'])) for i in range(1,len(values),2)):
                continue
            unit_text = source.text[heading.end():periods[0]['start']]
            units = list(re.finditer(r'\(in\s+(millions|billions)(?:\s+except\s+per\s+share\s+amounts)?\)',unit_text,re.I))
            if len(units) != 1 or re.search(r'CAD|AUD|HKD|Canadian|Australian',unit_text,re.I):
                continue
            lo, hi = values[4*g+1], values[4*g+3]
            if number(flat(lo['text'])) > number(flat(hi['text'])):
                continue
            unit = units[0][1].lower()[:-1]
            evidence = source.text[heading.start():row['end']]
            metric = Metric(source.source_id, source.issuer, 'revenue','USD',unit,'reported',horizon,
                'fiscal','total_revenue_as_reported','provided',str(number(flat(lo['text']))),
                str(number(flat(hi['text']))),evidence,evidence)
            ustart=heading.end()+units[0].start(); uend=heading.end()+units[0].end()
            proof={'kind':'explicit_annual_column', 'group_index':g,'period_group_count':n,
                'heading':span(source,heading.start(),heading.end()),
                'period':span(source,groups[g]['start'],groups[g]['end']),
                'date':span(source,(date_row['cells'][g] if date_row else groups[g])['start'],
                                   (date_row['cells'][g] if date_row else groups[g])['end']),
                'unit':span(source,ustart,uend),'row':span(source,row['start'],row['end']),
                'lower_cell':span(source,lo['start'],lo['end']), 'upper_cell':span(source,hi['start'],hi['end']),
                'low_high_labels':[span(source,c['start'],c['end']) for c in lowhigh[0]['cells'][2*g:2*g+2]],
                'currency_cells':[span(source,values[i]['start'],values[i]['end']) for i in (4*g,4*g+2)]}
            result.append((metric,proof))
    return result


def guidance_catalog(source, horizon):
    found=[]
    simple,_=extract(source,horizon)
    options=([simple] if simple else [])+[m for _,m in candidates(source,sentences(source.text),horizon)]
    for m in options:
        check=validate_evidence(m,source)
        if not check['errors']:
            found.append((m,{'kind':'legacy_literal_screen','validation':check}))
    found.extend(table_candidates(source,horizon))
    unique={}
    for metric,proof in found:
        key=(metric.status,metric.currency,metric.bounds() if metric.status=='provided' else None,metric.horizon)
        if key in unique:
            continue
        start=source.text.index(metric.horizon_evidence)
        reference=span(source,start,start+len(metric.horizon_evidence))
        mid='m_'+digest(canonical({'metric':asdict(metric),'proof':proof}))[:24]
        unique[key]={'metric_id':mid,'metric':asdict(metric),'proof':proof,'evidence':reference,
                     'semantic_review':'pending'}
    return list(unique.values())


def explanation_catalog(source, horizon, limit=12):
    """Rank short literal statements across the WHOLE disclosure, not top windows.

    This supplies candidates; polarity, consistency, causal support and period/scope
    equivalence are model proposals and subsequent human judgments, never rule labels.
    """
    ranked=[]
    for unit in sentences(source.text):
        q=unit.text
        if '|' in q or not 20 <= len(q) <= 1800:
            continue
        guidance=bool(re.search(r'\b(?:guidance|outlook|target\w*|forecast\w*)\b',q,re.I))
        driver=bool(re.search(r'\b(?:because|due to|attribut\w*|caus\w*|driv\w*|drove|reflect\w*|headwind\w*|tailwind\w*|contribut\w*|explain\w*|responsible|accounted for|demand|currency|pricing|volume|acquisition\w*)\b',q,re.I))
        if not guidance or not driver:
            continue
        year=bool(re.search(r'\b'+horizon[2:]+r'\b|\bFY\s*'+horizon[2:]+r'\b',q,re.I))
        boiler=bool(re.search(r'forward.looking|risk factors|actual results may|no obligation',q,re.I))
        score=8+int(year)-8*boiler
        ranked.append((score,unit))
    ranked.sort(key=lambda item:(-item[0],item[1].start))
    selected=[]; seen=set()
    for score,u in ranked:
        key=flat(u.text).lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append({**span(source,u.start,u.end),'retrieval_score':score})
        if len(selected)==limit:
            break
    return selected


def proof_view(proof):
    """The contiguous evidence quote already includes these exact subspans.

    Keep compact offsets in tool messages; retain the complete hash-bound proof in
    accepted extraction records. This avoids repeating the same URL/hash per cell.
    """
    out={k:proof[k] for k in ('kind','group_index','period_group_count') if k in proof}
    out['bindings']={}
    for key,value in proof.items():
        if isinstance(value,dict) and 'start' in value:
            out['bindings'][key]=[value['start'],value['end']]
        elif isinstance(value,list):
            out['bindings'][key]=[[v['start'],v['end']] for v in value]
    return out


def citation_view(c):
    # Hash/URL/origin remain in the registry and saved accepted citations. The
    # source-specific evidence ID commits to that hash and these exact offsets.
    return {k:c[k] for k in ('evidence_id','source_id','start','end','quote')}


class EvidenceTools:
    """Pair/cutoff-scoped evidence registry. Publication is separate from reads."""
    def __init__(self,sources,allowed,cutoff,horizon):
        self.read=ReadTools(sources,allowed,cutoff)
        self.sources=self.read.sources
        self.horizon=horizon
        self.metrics={sid:guidance_catalog(s,horizon) for sid,s in self.sources.items()}
        self.citations={}; self.visible_metrics={}; self.reviewed=set()

    def execute(self,name,args):
        if name in {'inspect_guidance','review_explanations'}:
            if set(args)!={'source_id'}:
                raise ValueError('review_requires_source_id_only')
            s=self.read._source(args['source_id'])
            if name=='inspect_guidance':
                return {'source_id':s.source_id,'review':name,'metric_candidates':[
                    {'metric_id':c['metric_id'],'metric':{k:v for k,v in c['metric'].items() if k not in {'evidence','horizon_evidence'}},
                     'evidence':citation_view(c['evidence']),'proof':proof_view(c['proof'])} for c in self.metrics[s.source_id]],
                    'ambiguous':len(self.metrics[s.source_id])>1,
                    'limitation':'Bounded parser candidates, not human labels. Empty means unavailable or unsupported layout.'}
            return {'source_id':s.source_id,'review':name,
                    'citations':[citation_view(c) for c in explanation_catalog(s,self.horizon)],
                    'limitation':'Ranked statement candidates, not a complete search or confirmed causal/conflict judgments.'}
        output=self.read.execute(name,args)
        parts=output.get('passages',[output])
        return {'citations':[citation_view(span(self.sources[p['source_id']],p['start'],p['end'])) for p in parts]}

    def publish(self,output):
        """Called only after every action in a batch has succeeded."""
        if 'review' in output:
            self.reviewed.add((output['source_id'],output['review']))
        for c in output.get('metric_candidates',[]):
            sid=c['metric']['source_id']
            original=next(m for m in self.metrics[sid] if m['metric_id']==c['metric_id'])
            self.visible_metrics[c['metric_id']]=original
            self.citations[c['evidence']['evidence_id']]=original['evidence']
        for c in output.get('citations',[]):
            original=span(self.sources[c['source_id']],c['start'],c['end'])
            if citation_view(original)!=c:
                raise ValueError('citation_publication_mismatch')
            self.citations[c['evidence_id']]=original

    def pending(self):
        return [[sid,name] for sid in self.sources for name in ('inspect_guidance','review_explanations')
                if (sid,name) not in self.reviewed]

    def resolve_citation(self,eid):
        if eid not in self.citations:
            raise ValueError('citation_id_not_in_retrieved_context')
        c=self.citations[eid];s=self.sources[c['source_id']]
        if c['source_hash']!=s.content_hash or c['quote']!=s.text[c['start']:c['end']]:
            raise ValueError('citation_registry_mismatch')
        return deepcopy(c)

    def resolve_metric(self,mid):
        if mid not in self.visible_metrics:
            raise ValueError('metric_id_not_in_retrieved_context')
        c=self.visible_metrics[mid];sid=c['metric']['source_id']
        if len(self.metrics[sid])!=1:
            raise ValueError('ambiguous_guidance_candidates')
        # Reconstruct from immutable source text; model cannot change bounds/units.
        expected=guidance_catalog(self.sources[sid],self.horizon)
        if c not in expected:
            raise ValueError('metric_registry_mismatch')
        metric=Metric(**c['metric'])
        return metric,{'metric':asdict(metric),'metric_id':mid,'evidence_binding':deepcopy(c['proof']),
                      'validation':{'literal_valid':True,'semantic_screen':c['proof']['kind'],
                                    'errors':[],'human_semantic_review':'pending'}}
