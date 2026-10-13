"""A transparent extraction template; it makes no model decisions."""
from .records import citation


def build_baseline(tools):
    events = tools.execute('list_events', {})['events']
    if tools.broad_scope:
        items = []
        for event in events[:8]:
            # Extract source text only; this path does not invent an interpretation.
            evidence = event['date_evidence'][-1:]
            claims = [{'kind':'fact', 'statement':evidence[0]['quote'], 'context':'historical',
                       'channel':None, 'evidence':evidence}] if evidence else []
            items.append({'event_id':event['event_id'], 'claims':claims,
                          'gaps':['Risk, historical impact, and analyst views require cited research.']})
        return {'items':items, 'omissions':[]}
    statements = sorted((s for s in tools.sources.values() if s.kind == 'statement'),
                        key=lambda s: s.published_at, reverse=True)
    items = []
    for event in events:
        claims = []
        if statements and event.get('family_id', 'fomc') == 'fomc':
            source = statements[0]
            paragraph = next((p for p in source.text.splitlines()
                              if 'target range for the federal funds rate' in p), None)
            if paragraph:
                # Quote an actual policy decision, not a model-generated forecast.
                sentence = paragraph.split('. ')[0].rstrip('.') + '.'
                start = source.text.index(sentence)
                cite = citation(source, start, start+len(sentence))
                tools.show(cite)
                claims.append({'kind':'fact', 'statement':sentence, 'context':'historical',
                               'channel':None, 'evidence':[cite]})
        items.append({'event_id':event['event_id'], 'claims':claims,
                      'gaps':['Current market consensus is not established by this template.',
                              'Risk interpretation and historical market reactions require further research.']})
    return {'items':items, 'omissions':[]}
