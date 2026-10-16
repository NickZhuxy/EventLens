"""Pair-bound, explicit withdrawal of all financial guidance for an annual period."""
from copy import deepcopy
from dataclasses import asdict,replace
import re
from . import evidence_v8 as previous
from .core import Metric,canonical,digest,timestamp
from .evidence_v5 import span

KIND='explicit_annual_all_financial_guidance_withdrawal'


def withdrawal_candidate(source,prior,horizon):
    """An unqualified financial-guidance suspension includes the prior revenue target.

    Identity (currency, basis, definition and units) comes from the unique prior
    accepted target, not from invented values in the withdrawal notice. This
    narrow screen rejects hypothetical/negative/partial-period statements.
    """
    metric=Metric(**prior['metric'])
    if (horizon not in source.forecast_horizons or metric.horizon!=horizon
            or metric.status!='provided' or metric.issuer!=source.issuer):return None
    candidates=[]
    for line in re.finditer(r'[^\n]+',source.text):
        quote=line[0]
        if len(quote)>800 or re.search(r'\b(?:not|never|may|might|could|would|if|unless|previously|formerly)\b',quote,re.I):continue
        action=re.search(r'\b(?:has|have)\s+(?:suspended|withdrawn)\s+(?:its|our|their|all)\s+financial\s+guidance\s+for\b',quote,re.I)
        if not action:continue
        year=re.escape(horizon[2:])
        scope=(r'\s+(?:(?:the\s+)?(?:first|second|third|fourth)\s+quarter\s+of\s+fiscal\s+year\s+'
               +year+r'\s+and\s+)?(?:the\s+)?full\s+fiscal\s+year\s+'+year+r'\s*\.?\s*')
        if not re.fullmatch(scope,quote[action.end():],re.I):continue
        annual=re.search(r'\bfull\s+fiscal\s+year\s+'+re.escape(horizon[2:])+r'\b',quote[action.end():],re.I)
        if not annual:continue
        annual_start=line.start()+action.end()+annual.start()
        evidence=span(source,line.start(),line.end())
        withdrawn=replace(metric,source_id=source.source_id,status='withdrawn',lower=None,upper=None,
                          evidence=quote,horizon_evidence=quote)
        proof={'kind':KIND,'withdrawal_statement':evidence,
               'annual_scope':span(source,annual_start,annual_start+len(annual[0])),
               'prior_guidance':deepcopy(prior['evidence']),
               'prior_metric_id':prior['metric_id'],
               'identity_rule':'Unqualified all-financial-guidance withdrawal; inherit the unique prior revenue target identity. No new value is inferred.'}
        mid='m_'+digest(canonical({'metric':asdict(withdrawn),'proof':proof}))[:24]
        candidates.append({'metric_id':mid,'metric':asdict(withdrawn),'proof':proof,'evidence':evidence,'semantic_review':'pending'})
    return candidates[0] if len(candidates)==1 else None


class EvidenceTools(previous.EvidenceTools):
    def __init__(self,sources,allowed,cutoff,horizon):
        super().__init__(sources,allowed,cutoff,horizon)
        self.pair=tuple(allowed)
        self.metrics=self._catalogs()

    def _catalogs(self):
        catalogs={sid:previous.guidance_catalog(s,self.horizon) for sid,s in self.sources.items()}
        if len(self.pair)==2:
            old,new=self.pair
            if (old!=new and timestamp(self.sources[old].published_at)<timestamp(self.sources[new].published_at)
                    and len(catalogs[old])==1 and not catalogs[new]):
                candidate=withdrawal_candidate(self.sources[new],catalogs[old][0],self.horizon)
                if candidate:catalogs[new]=[candidate]
        return catalogs

    def resolve_metric(self,mid):
        c=self.visible_metrics.get(mid)
        if c is None or c['proof']['kind']!=KIND:return super().resolve_metric(mid)
        sid=c['metric']['source_id'];fresh=self._catalogs()
        if len(fresh[sid])!=1 or c not in fresh[sid]:raise ValueError('withdrawal_registry_mismatch')
        return Metric(**c['metric']),{'metric':deepcopy(c['metric']),'metric_id':mid,'evidence_binding':deepcopy(c['proof']),
            'validation':{'literal_valid':True,'semantic_screen':KIND,'errors':[],
                          'human_semantic_review':'pending','identity_inherited_from':c['proof']['prior_metric_id']}}

    def execute(self,name,args):
        result=super().execute(name,args)
        if name=='inspect_guidance':
            for item in result['metric_candidates']:
                stored=next(c for c in self.metrics[args['source_id']] if c['metric_id']==item['metric_id'])
                if stored['proof']['kind']==KIND:
                    prior=stored['proof']['prior_guidance']
                    item['proof']['bindings'].pop('prior_guidance',None)
                    item['proof']['identity_inheritance']={
                        'prior_metric_id':stored['proof']['prior_metric_id'],
                        **{k:prior[k] for k in ('source_id','source_hash','start','end')},
                        'rule':stored['proof']['identity_rule']}
        return result
