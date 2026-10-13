"""Transparent denominators; draft labels cannot become adjudicated gold by accident."""
from collections import defaultdict
from decimal import Decimal
from .core import Metric, compare


def signature(metric):
    m = Metric(**metric)
    return (m.source_id,m.issuer,m.metric,m.currency,m.basis,m.horizon,m.calendar,m.definition,m.status,
            m.bounds() if m.status=='provided' else (None,None))


def score(runs, labels):
    if labels['status'] not in {'ai_draft','human_reviewed'}:
        raise ValueError('invalid label status')
    if labels['status']=='human_reviewed' and not (labels.get('reviewed_by') and labels.get('reviewed_at')):
        raise ValueError('reviewed labels require reviewer and timestamp')
    groups=defaultdict(list)
    for run in runs:
        groups[(run['method'],run['case']['split'])].append(run)
    metrics=[]
    for (method,split), rows in sorted(groups.items()):
        tp=fp=fn=comparisons=scored_comparisons=arithmetic_errors=literal_errors=screen_errors=claims=abstentions=0
        expected_abstentions=correct_abstentions=status_correct=0
        tokens=[]
        for r in rows:
            synthetic=r['case'].get('synthetic',False)
            if r['comparison']['calculation']:comparisons+=1
            if synthetic:
                expected=r['case']['expected_status']
                status_correct += r['conclusion']==expected
                if expected=='insufficient_evidence':
                    expected_abstentions+=1
                    correct_abstentions+=r['conclusion']==expected
            else:
                truth=labels['cases'][r['case']['case_id']]
                gold={signature(x) for x in truth['metrics']}
                # Score emitted candidates, including rejected ones: invalid output is not hidden.
                predicted={signature(x['metric']) for x in r['extractions']}
                tp+=len(gold&predicted);fp+=len(predicted-gold);fn+=len(gold-predicted)
                status_correct+=r['conclusion']==truth['expected_status']
                calc=r['comparison']['calculation']
                if calc:
                    scored_comparisons+=1
                    arithmetic_errors+=Decimal(calc['midpoint_delta'])!=Decimal(truth['expected_midpoint_delta_usd'])
            for x in r['extractions']:
                literal_errors+=not x['validation']['literal_valid']
                screen_errors+=bool(x['validation']['errors'])
            claims+=len(r['explanations'])
            abstentions+=r['conclusion']=='insufficient_evidence'
            if r['tokens'] is not None:tokens.append(r['tokens']['total_tokens'])
        synthetic=split.startswith('synthetic')
        metrics.append({'method':method,'split':split,'case_count':len(rows),
            'provisional':labels['status']!='human_reviewed','label_status':labels['status'],
            'extraction_true_positive':None if synthetic else tp,
            'extraction_false_positive':None if synthetic else fp,
            'extraction_false_negative':None if synthetic else fn,
            'extraction_precision':None if synthetic or tp+fp==0 else tp/(tp+fp),
            'extraction_recall':None if synthetic or tp+fn==0 else tp/(tp+fn),
            'emitted_numerical_comparisons':comparisons,'numerically_scored_comparisons':scored_comparisons,
            'numerical_comparison_errors':arithmetic_errors if scored_comparisons else None,
            'literal_evidence_errors':literal_errors,'automated_semantic_screen_failures':screen_errors,
            'human_evidence_support_errors':None,'human_reviewed_observations':0,
            'explanation_candidates_pending_review':claims,'abstentions':abstentions,
            'expected_abstention_cases':expected_abstentions,'appropriate_abstentions':correct_abstentions,
            'status_correct':status_correct,'calls':sum(r['calls'] for r in rows),
            'total_tokens':sum(tokens) if len(tokens)==len(rows) else None,
            'latency_ms_sum':sum(r['latency_ms'] for r in rows)})
    return metrics


def report_text(summary):
    lines=['# EventLens evaluation', '', ('All accuracy results below are provisional against AI-drafted labels. Nick has not reviewed these labels.' if any(m['provisional'] for m in summary['metrics']) else 'Extraction labels are marked human-reviewed in labels_used.json. Semantic observation review remains separate.'), '',
           f"Corpus: {summary['corpus']['documents']} normalized public source snapshots; {summary['corpus']['eligible_comparisons']} eligible same-horizon real pairs; {summary['corpus']['issuers']} issuers.",
           'Synthetic controls are counted separately. No live model evaluation was run unless the methods list explicitly says live.', '',
           '| Method | Split | Cases | Precision | Recall | Numeric errors / emitted | Abstentions | Calls |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for x in summary['metrics']:
        fmt=lambda v:'unmeasured' if v is None else f'{v:.3f}'
        lines.append(f"| {x['method']} | {x['split']} | {x['case_count']} | {fmt(x['extraction_precision'])} | {fmt(x['extraction_recall'])} | {x['numerical_comparison_errors']} / {x['emitted_numerical_comparisons']} | {x['abstentions']} | {x['calls']} |")
    lines+=['','## Method status','']
    lines += [f"- {m}: {status}" for m,status in summary['methods'].items()]
    lines+=['','## Interpretation and limits','',
      'A match requires the source, issuer, metric, currency, basis, fiscal horizon, definition, status and normalized bounds to agree. Equivalent million/billion units count as equal. Precision includes all emitted candidates, including candidates rejected by the evidence screen.',
      'Numerical errors are counted only when a calculation is emitted. Missed comparisons and extraction false negatives remain visible; zero arithmetic errors does not mean all cases succeeded.',
      'Literal evidence checks and lexical semantic screens are automated. Human evidence-support errors are unmeasured. Management explanations are review candidates; no verified causal decomposition is claimed.',
      'The three real pairs are a convenience sample of upward revisions. They do not estimate broad financial extraction performance. The issuer split was set before held-out runs, but source selection and labels used AI assistance and were not blinded.',
      'The snapshots were retrieved in 2026. The disclosure cutoff is a date-based replay assumption, with date-only publications set conservatively to end of day in New York. It does not prove historical byte availability. Use --cutoff-mode snapshot for a strict retrieval-time bound; these old cutoffs then abstain.',
      'The Autodesk Q2 FY2026 capture contains its main release and outlook but only part of the financial appendix because subsequent retrieval returned HTTP 403. See data/capture_audit.json. Quotes are checked against saved normalized text, not the original HTML byte stream.',
      'B receives the complete saved pair snapshots in one call. C starts with metadata and selects bounded read-only retrieval calls over the same pair. The model, cutoff and questions are shared. Context and call budgets differ and are recorded; this is not a compute-matched comparison.',
      'Calls and latency are measured per run. Missing provider token usage is null, never zero. Mock controller tests are engineering checks and are excluded from the real evaluation.',
      '', '## Abstentions and conflict flags', '']
    for f in summary['failures']:
        lines.append(f"- {f['case_id']} ({f['method']}): {f['status']} — {f['reason']}")
    lines+=['','See summary.json, runs/*.json, review_queue.json, and provenance.json in this directory for the raw evidence.','']
    return '\n'.join(lines)
