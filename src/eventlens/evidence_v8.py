"""Conservative point-target screen; historical v5 catalogs remain frozen."""
from copy import deepcopy
import re
from . import evidence_v5 as previous
from .core import Metric, number
from .document_diff import POINT, RANGE, REVENUE


def point_target_issue(metric):
    """A single monetary impact is not an absolute annual revenue target.

    Retain explicit ranges. For a lone point target require the revenue noun before
    the matching amount and reject impact/delta language. This intentionally can
    abstain on unsupported point syntax; it does not infer a replacement value.
    """
    if metric['status'] != 'provided' or number(metric['lower']) != number(metric['upper']):
        return None
    text=previous.flat(metric['evidence'])
    if RANGE.search(text):
        return None
    revenue=REVENUE.search(text)
    amounts=[m for m in POINT.finditer(text) if number(m[1])==number(metric['lower'])
             and m[2].lower()==metric['unit']]
    if len(amounts)==1:
        amount=amounts[0]
        bridge=text[revenue.end():amount.start()] if revenue and revenue.end()<=amount.start() else text[max(0,amount.start()-60):amount.start()]
        impact=r'headwind|tailwind|impact|incremental|contribution|increase|decrease|growth|change|revision'
        if re.search(r'\b(?:'+impact+r')\b',bridge,re.I) or re.match(r'\s*(?:of\s+)?(?:'+impact+r')\b',text[amount.end():],re.I):
            return 'point_amount_describes_impact_or_change'
    if not revenue or len(amounts)!=1 or amounts[0].start()<revenue.end():
        return 'point_target_requires_revenue_before_amount'
    return None


def guidance_catalog(source,horizon):
    return [c for c in previous.guidance_catalog(source,horizon) if point_target_issue(c['metric']) is None]


def rejected_candidates(source,horizon):
    return [{'metric_id':c['metric_id'],'metric':c['metric'],'reason':point_target_issue(c['metric'])}
            for c in previous.guidance_catalog(source,horizon) if point_target_issue(c['metric']) is not None]


class EvidenceTools(previous.EvidenceTools):
    def __init__(self,sources,allowed,cutoff,horizon):
        super().__init__(sources,allowed,cutoff,horizon)
        self.metrics={sid:guidance_catalog(s,horizon) for sid,s in self.sources.items()}

    def resolve_metric(self,mid):
        if mid not in self.visible_metrics:
            raise ValueError('metric_id_not_in_retrieved_context')
        c=self.visible_metrics[mid];sid=c['metric']['source_id']
        if len(self.metrics[sid])!=1:
            raise ValueError('ambiguous_guidance_candidates')
        if c not in guidance_catalog(self.sources[sid],self.horizon):
            raise ValueError('metric_registry_mismatch')
        metric=Metric(**c['metric'])
        return metric,{'metric':deepcopy(c['metric']),'metric_id':mid,'evidence_binding':deepcopy(c['proof']),
            'validation':{'literal_valid':True,'semantic_screen':c['proof']['kind'],
                          'point_target_screen':'passed_or_not_applicable','errors':[],'human_semantic_review':'pending'}}
