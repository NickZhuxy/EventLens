"""Multi-market workflow and calendar failure/regression checks."""
from dataclasses import replace
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from eventlens.core import digest
from eventlens.llm import MockAdapter
from eventlens.macro.agent import run_brief
from eventlens.macro.catalog import CATALOG, MARKETS
from eventlens.macro.records import calendar, validate_case
from eventlens.macro.report import render_brief, render_calendar_csv
from eventlens.macro.schedules import encode_schedule
from eventlens.macro.tools import ResearchTools
from eventlens.macro.validation import validate_brief
from eventlens.service.api import create_app
from eventlens.service.ingestion import make_source
from eventlens.service.providers import parse_ecb, parse_nbs, parse_usda, parse_bls, parse_nyfed, refresh_nyfed, record, refresh_calendars, check_url
from eventlens.service.settings import Settings, DEFAULT_CONFIG
from eventlens.service.store import Database
from eventlens.service.worker import Worker

CASE = dict(case_id='global-window', as_of='2026-10-08T12:00:00Z', start_date='2026-10-08',
            end_date='2026-11-07', markets=list(MARKETS), split='synthetic', question='Assess macro risks across markets.')
TOKEN = 'global-test-token-not-for-deployment'
ECB = '''<dt>28/10/2026</dt><dd>Governing Council: monetary policy meeting (Day 1)</dd>
<dt>29/10/2026</dt><dd>Governing Council: monetary policy meeting (Day 2)</dd>
<dt>29/10/2026</dt><dd>Press conference</dd>
<dt>25/11/2026</dt><dd>Governing Council: non-monetary policy meeting</dd>'''


def source(text, kind='calendar', topics=None, markets=None):
    return make_source(title='Synthetic regression fixture', publisher='Test publisher', url='https://example.org/'+kind,
                       published_at='2026-10-07T12:00:00Z', retrieved_at='2026-10-07T13:00:00Z',
                       document_date='2026-10-07', kind=kind, text=text, topics=topics or ['ecb_policy'], markets=markets or ['EU'])


def ecb_source():
    text, events = parse_ecb(ECB)
    return source(encode_schedule(text, events), markets=['EU','GLOBAL'])


class GlobalMacroTests(unittest.TestCase):
    def test_catalog_covers_reference_workflow_and_merges_employment_indicators(self):
        self.assertEqual(len(CATALOG), 41)
        self.assertEqual({m for f in CATALOG.values() for m in f['markets']}, set(MARKETS))
        self.assertEqual(CATALOG['us_unemployment']['calendar_family'], 'us_employment')
        tools = ResearchTools({}, CASE, include_watchlist=True)
        self.assertEqual(len(tools.events), 40)
        self.assertTrue(all(e['start_date'] is None and e['date_status'] == 'watchlist' for e in tools.events))

    def test_market_validation_accepts_regions_and_rejects_unknowns(self):
        for market in MARKETS:
            validate_case({**CASE, 'markets':[market]})
        with self.assertRaises(ValueError):
            validate_case({**CASE, 'markets':['INVALID']})

    def test_ecb_pair_deduplicates_press_conference(self):
        s = ecb_source(); events = calendar({s.source_id:s}, CASE)
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]['start_date'], events[0]['end_date']), ('2026-10-28','2026-10-29'))
        self.assertEqual(len(events[0]['date_evidence']), 2)
        self.assertEqual(calendar({s.source_id:s}, {**CASE,'markets':['TW']}), events)  # ECB is global exposure.

    def test_missing_day_one_label_can_use_adjacent_day_two(self):
        text, rows = parse_ecb(ECB.replace(' (Day 1)', ''))
        self.assertEqual(rows[0]['start_date'], '2026-10-28')
        with self.assertRaises(ValueError):
            parse_ecb(ECB.replace('28/10/2026', '26/10/2026'))

    def test_nbs_holiday_release_is_not_last_day_rule(self):
        cells = ['31/六', '……', '4/三 注5 31/二', '30/四','31/日','30/二','31/五','31/一','30/三','31/六','30/一','31/四']
        html = '<h1>2026年国家统计局主要统计信息发布日程表</h1><table><tr><td>4</td><td>采购经理指数月度报告</td>'+''.join('<td>'+x+'</td>' for x in cells)+'</tr></table>'
        text, rows = parse_nbs(html)
        self.assertEqual([r['start_date'] for r in rows if r['start_date'][5:7] == '03'], ['2026-03-04','2026-03-31'])
        self.assertTrue(all(r['date_status'] == 'tentative' for r in rows))
        encode_schedule(text, rows)

    def test_usda_twelve_explicit_dates(self):
        dates = 'Jan. 12, Feb. 10, Mar. 10, Apr. 9, May 12, Jun. 11, Jul. 10, Aug. 12, Sep. 11, Oct. 9, Nov. 10, and Dec. 10'
        text, rows = parse_usda('<p>In 2026 the WASDE report will be released on '+dates+'.</p>')
        self.assertEqual(rows[9]['start_date'], '2026-10-09')
        self.assertEqual(len(rows), 12)
        with self.assertRaises(ValueError):
            parse_usda('<p>Layout changed</p>')

    def test_inflation_releases_stay_separate_and_employment_deduplicates(self):
        text = '2026-10-14 CPI and PPI. 2026-10-02 Employment Situation and unemployment rate.'
        rows = [record('us_inflation','2026-10-14',[text],name='US CPI'),
                record('us_inflation','2026-10-14',[text],name='US PPI'),
                record('us_employment','2026-10-02',[text]), record('us_unemployment','2026-10-02',[text])]
        s = source(encode_schedule(text, rows), markets=['US'])
        events = calendar({s.source_id:s}, {**CASE,'start_date':'2026-10-01','end_date':'2026-10-31','as_of':'2026-10-01T00:00:00Z'})
        self.assertEqual(events, [])  # Future-acquired schedule must not leak into replay.
        case = {**CASE, 'start_date':'2026-10-02', 'as_of':'2026-10-02T12:00:00Z', 'end_date':'2026-11-01'}
        s = replace(s,published_at='2026-10-01T00:00:00Z',available_at='2026-10-01T00:00:00Z',
                    retrieved_at='2026-10-01T01:00:00Z',document_date='2026-10-01')
        events = calendar({s.source_id:s}, case)
        self.assertEqual(len(events),3)

    def test_partial_date_window_preserved(self):
        text = 'The policy meeting is expected in late October. Exact date is not announced.'
        s = source(encode_schedule(text,[record('cn_politburo','2026-10-21',[text],end='2026-10-31',status='window',zone='Asia/Shanghai')]),markets=['CN'])
        event = calendar({s.source_id:s},CASE)[0]
        self.assertEqual(event['date_precision'],'window')
        self.assertEqual(event['date_status'],'window')

    def test_current_sources_do_not_leak_after_cutoff(self):
        s = ecb_source()
        s = replace(s,retrieved_at='2026-10-09T00:00:00Z')
        self.assertEqual(calendar({s.source_id:s},CASE,'snapshot'),[])
        self.assertEqual(len(calendar({s.source_id:s},CASE,'publication')),1)

    def test_structural_errors_are_rejected(self):
        for changes in [{'family_id':'unknown'}, {'start_date':'2026-11-01'}, {'quotes':['absent']}, {'date_status':'guessed'}]:
            row=record('ecb_policy','2026-10-28',['Evidence text'])
            with self.assertRaises(ValueError):
                encode_schedule('Evidence text',[{**row,**changes}])

    def test_refresh_failure_keeps_other_providers_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Database(Path(directory)/'state.sqlite')
            def fetch(url):
                if 'bls.gov' in url: raise RuntimeError('calendar_http_error_403')
                return ECB
            first=refresh_calendars(db,['bls','ecb'],fetch=fetch)
            self.assertEqual(first['added'],1)
            self.assertEqual(first['errors'][0]['provider'],'bls')
            second=refresh_calendars(db,['ecb'],fetch=fetch)
            self.assertEqual(second['unchanged'],1)
            self.assertEqual(second['source_ids'],first['source_ids'])
            self.assertIn('first observed',db.source_details(first['source_ids'][0])['provenance']['timestamp_basis'])

    def test_calendar_url_scope_rejects_credentials_and_redirect_targets(self):
        for url in ['http://www.ecb.europa.eu/', 'https://evil.example/', 'https://www.bls.gov/schedule/2026/home.htm?next=evil']:
            with self.assertRaises(ValueError): check_url(url)

    def test_broad_baseline_does_not_attach_fed_policy_to_other_events(self):
        s=ecb_source()
        run=run_brief({s.source_id:s},CASE,'rules',DEFAULT_CONFIG,include_watchlist=True)
        self.assertTrue(run['validation']['valid'],run['validation'])
        self.assertEqual(run['status'],'partial')
        self.assertLessEqual(len(run['brief']['items']),8)
        self.assertNotIn('federal funds',render_brief(run,{s.source_id:s}))
        rows=list(csv.DictReader(io.StringIO(render_calendar_csv(run,{s.source_id:s}))))
        self.assertEqual(len(rows),40)
        self.assertEqual(next(r for r in rows if r['Event']=='China Politburo policy meetings')['Date from'],'')

    def test_agent_researches_history_and_views_then_repairs_wrong_source_type(self):
        s=ecb_source()
        history=source('During the earlier policy shock, bond volatility increased and market liquidity declined.','market_history')
        analyst=source('Example Research: the upcoming meeting could leave bond markets sensitive to changes in policy communication.','analyst_report')
        sources={x.source_id:x for x in [s,history,analyst]}
        tools=ResearchTools(sources,CASE,include_watchlist=True)
        event=next(e for e in tools.events if e['event_id'].startswith('ecb_policy-'))
        history_cite={'source_id':history.source_id,'start':0,'end':len(history.text),'quote':history.text}
        analyst_cite={'source_id':analyst.source_id,'start':0,'end':len(analyst.text),'quote':analyst.text}
        good={'items':[{'event_id':event['event_id'],'claims':[
            {'kind':'historical_impact','context':'historical','statement':history.text,'channel':None,'evidence':[history_cite]},
            {'kind':'analyst_view','context':'current','statement':analyst.text,'channel':None,'evidence':[analyst_cite]},
            {'kind':'risk','context':'current','statement':'European bonds could face volatility around policy communication.','channel':'volatility','evidence':[analyst_cite]}],
            'gaps':['Current consensus has not been established.']}],'omissions':[]}
        bad=json.loads(json.dumps(good));bad['items'][0]['claims'][0]['evidence']=[analyst_cite]
        def action(name,args): return {'action':'tool','name':name,'arguments':args,'reason':'Inspect event evidence.'}
        actions=[action('list_events',{}),action('read_source',{'source_id':history.source_id,'start':0,'end':len(history.text)}),
                 action('read_source',{'source_id':analyst.source_id,'start':0,'end':len(analyst.text)}),
                 {'action':'finish','brief':bad},{'action':'finish','brief':good}]
        run=run_brief(sources,CASE,'agent',DEFAULT_CONFIG,MockAdapter(actions),include_watchlist=True)
        self.assertEqual(run['execution_kind'],'mock')
        self.assertTrue(run['validation']['valid'],run)
        self.assertEqual([x['valid'] for x in run['trace'] if x['stage']=='draft_validation'],[False,True])
        self.assertIn('Historical impact',render_brief(run,sources))
        self.assertIn('Analyst view',render_brief(run,sources))

    def test_csv_does_not_execute_imported_formulas(self):
        s=ecb_source();run=run_brief({s.source_id:s},CASE,'rules',DEFAULT_CONFIG,include_watchlist=True)
        run['calendar'][0]['name']='=HYPERLINK("https://example.org")'
        self.assertIn("'=HYPERLINK",render_calendar_csv(run,{s.source_id:s}))

    def test_nyfed_calendar_supplies_separate_inflation_dates(self):
        html = '<table><td class="ts-data-table-head">October 2026</td><td><div>14 <a>Consumer Price Index</a></div></td><td><div>15 <a>Producer Price Index (PPI)</a></div></td><td><div>02 <a>Employment Situation</a></div></td></table>'
        text, rows = parse_nyfed(html)
        self.assertEqual([(r['family_id'],r['start_date']) for r in rows],
                         [('us_inflation','2026-10-14'),('us_inflation','2026-10-15'),('us_employment','2026-10-02')])
        encode_schedule(text,rows)
        with self.assertRaises(ValueError): parse_nyfed(html.replace('October 2026','No month supplied'))

    def test_nyfed_stops_outside_allowlist_but_keeps_current_month(self):
        html = '<td class="ts-data-table-head">October 2026</td><td>14 <a>Consumer Price Index</a></td><a href="https://evil.example/">NEXT MONTH</a>'
        with tempfile.TemporaryDirectory() as directory:
            visited=[]
            def fetch(url): visited.append(url);return html
            result=refresh_nyfed(Database(Path(directory)/'state.sqlite'),fetch)
            self.assertEqual(len(visited),1)
            self.assertEqual(result['added'],1)
            self.assertEqual(len(result['errors']),1)

    def test_bls_employment_does_not_include_veterans_report(self):
        html='<h1>Schedule of Selected Releases 2026</h1><table><tr><td>Friday, October 2, 2026</td><td>Employment Situation for September 2026</td></tr><tr><td>Tuesday, April 28, 2026</td><td>Employment Situation of Veterans for Annual 2025</td></tr></table>'
        text, rows=parse_bls(html)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['start_date'],'2026-10-02')

    def test_watchlist_setting_changes_input_identity_and_keeps_global_output(self):
        s=ecb_source();sources={s.source_id:s}
        with_watch=run_brief(sources,CASE,'rules',DEFAULT_CONFIG,include_watchlist=True)
        dated_only=run_brief(sources,CASE,'rules',DEFAULT_CONFIG,include_watchlist=False)
        self.assertNotEqual(with_watch['input_hash'],dated_only['input_hash'])
        self.assertEqual(len(dated_only['calendar']),1)
        self.assertTrue(dated_only['broad_scope'])
        self.assertIn('Important events',render_brief(dated_only,sources))

    def test_api_global_default_and_worker_export(self):
        with tempfile.TemporaryDirectory() as directory:
            settings=Settings(Path(directory),TOKEN)
            client=TestClient(create_app(settings),headers={'Authorization':'Bearer '+TOKEN})
            with client:
                self.assertEqual(len(client.get('/v1/catalog').json()['families']),41)
                s=ecb_source();db=Database(settings.database);db.add_source(s,{'method':'test'})
                body={k:CASE[k] for k in ['as_of','start_date','end_date']};body['method']='rules'
                response=client.post('/v1/briefs',json=body);self.assertEqual(response.status_code,202,response.text)
                job=response.json();Worker(settings).tick()
                result=db.get(job['id']);self.assertEqual(result['status'],'succeeded',result)
                self.assertEqual(result['result']['run']['case']['markets'],list(MARKETS))
                export=client.get('/v1/jobs/'+job['id']+'/calendar.csv')
                self.assertEqual(export.status_code,200)
                self.assertIn('Historical impact',export.text)
                self.assertIn('China Politburo',export.text)

    def test_analyst_calendar_import_validates_and_research_sources_keep_markets(self):
        with tempfile.TemporaryDirectory() as directory:
            client=TestClient(create_app(Settings(Path(directory),TOKEN)),headers={'Authorization':'Bearer '+TOKEN})
            with client:
                text='The meeting is planned for late October; the exact date has not been announced. This is a synthetic test source.'
                body=dict(title='Synthetic policy calendar',publisher='Test',url='https://example.org/calendar',
                    published_at='2026-10-01T12:00:00Z',document_date='2026-10-01',text=text,markets=['CN'],topics=['cn_politburo'],
                    events=[record('cn_politburo','2026-10-21',[text],end='2026-10-31',status='window',zone='Asia/Shanghai')])
                response=client.post('/v1/calendar',json=body)
                self.assertEqual(response.status_code,201,response.text)
                body['events'][0]['quotes']=['not in the source']
                self.assertEqual(client.post('/v1/calendar',json=body).status_code,422)


if __name__=='__main__': unittest.main()
