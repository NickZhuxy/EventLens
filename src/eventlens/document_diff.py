"""Sentence-level difflib baseline; no model, labels, or issuer-specific rules."""
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from .core import Metric, number
from .extraction import QUARTER, explanation_candidates

GUIDANCE = re.compile(r'guidance|outlook|target|expect|anticipat|forecast', re.I)
ANNUAL = re.compile(r'\b(?:fiscal\s+(?:year\s+)?(?:20)?\d{2}|FY\s*(?:20)?\d{2}|full[ -]year\s+(?:of\s+)?20\d{2})\b', re.I)
REVENUE = re.compile(r'\b(?:(?:total|net)\s+)*revenue\b', re.I)
RANGE = re.compile(r'\$\s*(\d[\d,]*(?:\.\d+)?)\s*(billion|million)?\s*(?:to|and|[-–—])\s*\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(billion|million)?', re.I)
POINT = re.compile(r'\$\s*(\d[\d,]*(?:\.\d+)?)\s*(billion|million)\b', re.I)


@dataclass(frozen=True)
class Sentence:
    text: str
    start: int
    end: int


def sentences(text):
    """Split prose at terminal punctuation; retain each table row and heading."""
    result=[]
    for line in re.finditer(r'[^\n]+', text):
        # Decimal points and abbreviations are not followed by an uppercase word.
        for part in re.finditer(r'.+?(?:[.!?](?=\s+[A-Z“])|$)', line[0]):
            value=part[0]; left=len(value)-len(value.lstrip()); value=value.strip()
            if value:
                start=line.start()+part.start()+left
                result.append(Sentence(value,start,start+len(value)))
    return result


def _horizon(match):
    year=re.search(r'(\d{4}|\d{2})\b',match[0])[1]
    return 'FY'+('20'+year if len(year)==2 else year)


def candidates(source, units, horizon):
    """Parse guidance sentences/rows with an explicit annual heading in local context.

    Range matching uses a whitespace/table-separator view; all quoted spans still
    come from the unmodified snapshot. More than one range is ambiguous.
    """
    result=[]
    for index, unit in enumerate(units):
        hit=REVENUE.search(unit.text)
        if not hit or re.search(r'subscription|segment|constant.currency',unit.text[:hit.start()],re.I):
            continue
        before=source.text[max(0,unit.start-1200):unit.end]
        hs=list(ANNUAL.finditer(before))
        if not hs:continue
        last=hs[-1]
        if _horizon(last)!=horizon:continue
        # Begin at the heading's line, not at the middle of its fiscal-year token.
        local=before.rfind('\n',0,last.start())+1
        start=max(0,unit.start-1200)+local
        start=min(start,unit.start)
        context=source.text[start:unit.end]
        if QUARTER.search(context) or not GUIDANCE.search(context):continue
        if re.search(r'constant.currency|segment revenue|subscription revenue',unit.text,re.I):continue
        flat=re.sub(r'[|\s]+',' ',unit.text)
        matches=list(RANGE.finditer(flat))
        status='provided';low=high=None;scale=None
        if re.search(r'withdraw|suspend|no longer provid',unit.text,re.I):
            status='withdrawn';scale='USD'
        elif len(matches)==1:
            m=matches[0];low,high=str(number(m[1])),str(number(m[3]))
            if m[2] and m[4] and m[2].lower()!=m[4].lower():continue
            scale=(m[4] or m[2] or '').lower()
            if not scale and re.search(r'in millions',context,re.I):scale='million'
        elif not matches:
            points=list(POINT.finditer(flat))
            if len(points)!=1:continue
            bridge=flat[REVENUE.search(flat).end():points[0].start()]
            if not re.fullmatch(r'(?:\s|[|:]|of|is|will be|approximately|expected to be)*',bridge,re.I):continue
            low=high=str(number(points[0][1]));scale=points[0][2].lower()
        else:continue
        if not scale:continue
        # Include the scale heading in the literal quote when it supplies units.
        evidence=unit.text if scale=='USD' or scale in unit.text.lower() else context
        try:
            metric=Metric(source.source_id,source.issuer,'revenue','USD',scale,'reported',horizon,
                'fiscal','total_revenue_as_reported',status,low,high,evidence,context)
        except ValueError:continue
        result.append((index,metric))
    return result


def extract_pair(old, new, horizon, run):
    units=[sentences(s.text) for s in (old,new)]
    keys=[[re.sub(r'\s+',' ',u.text).strip() for u in side] for side in units]
    opcodes=SequenceMatcher(None,*keys,autojunk=False).get_opcodes()
    changes=[]
    for tag,a,b,c,d in opcodes:
        if tag=='equal':continue
        relevant=[]
        for side,lo,hi,source in [(0,a,b,old),(1,c,d,new)]:
            for index in range(lo,hi):
                u=units[side][index]
                if REVENUE.search(u.text) and re.search(r'\d|withdraw|suspend',u.text,re.I):
                    relevant.append({'source_id':source.source_id,'sentence':index,
                                     'start':u.start,'end':u.end,'quote':u.text})
        if relevant:changes.append({'operation':tag,'old_sentences':[a,b],'new_sentences':[c,d],'spans':relevant})
    found=[candidates(s,u,horizon) for s,u in zip((old,new),units)]
    # Collapse repeated identical current guidance, but never pick one of competing values.
    unique=[]
    for side in found:
        values={}
        for index,m in side:
            signature=(m.status,m.currency,m.bounds() if m.status=='provided' else None)
            values.setdefault(signature,(index,m))
        unique.append(list(values.values()))
    trace={'stage':'document_diff','algorithm':'difflib.SequenceMatcher sentence-level; autojunk=False',
           'sentence_counts':[len(u) for u in units], 'changed_guidance_candidates':changes,
           'annual_candidate_counts':[len(v) for v in unique], 'issues':[]}
    run['trace'].append(trace)
    if any(len(v)!=1 for v in unique):
        trace['issues'].append('missing_or_ambiguous_annual_guidance_pair')
        return [None,None]
    (oi,om),(ni,nm)=[v[0] for v in unique]
    relation=next((tag for tag,a,b,c,d in opcodes if a<=oi<b and c<=ni<d),None)
    if relation is None:
        # Reordered sentences can be delete+insert. Require similar wording.
        mask=lambda t:re.sub(r'\d[\d,.]*','<n>',t.lower())
        similarity=SequenceMatcher(None,mask(units[0][oi].text),mask(units[1][ni].text),autojunk=False).ratio()
        trace['reordered_sentence_similarity']=similarity
        if similarity<0.5:
            trace['issues'].append('unmatched_guidance_sentences');return [None,None]
        relation='delete_insert'
    trace['selected_alignment']=relation
    trace['selected_sentence_indices']=[oi,ni]
    trace['issues'].append('equal_guidance_retained_for_maintained_cases' if relation=='equal' else 'changed_guidance_pair')
    run['explanations']=[x for s in (old,new) for x in explanation_candidates(s)]
    return [om,nm]
