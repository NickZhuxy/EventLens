"""Research coverage, not a forecast or an authoritative release calendar.

Descriptions are independently authored. No employer workbook content is bundled.
Priority is an analyst-editable research default, not measured historical volatility.
"""
from copy import deepcopy

MARKETS = ('CN', 'HK', 'TW', 'SEA', 'EU', 'US', 'JP', 'GLOBAL')
ASSETS = ('equities', 'bonds', 'fx', 'energy', 'agriculture', 'metals')
# id, name, markets, assets, cadence, priority, explanation, public reference
_ROWS = [
('cftc_cot', 'CFTC Commitments of Traders', 'GLOBAL US', 'fx energy agriculture metals', 'weekly', 'medium', 'Positions reported by trader category in futures markets.', 'https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm'),
('iea_omr', 'IEA Oil Market Report', 'GLOBAL', 'energy', 'monthly', 'high', 'Oil supply, demand, inventories, and market balances.', 'https://www.iea.org/reports/oil-market-report'),
('usda_wasde', 'USDA World Agricultural Supply and Demand Estimates', 'GLOBAL US', 'agriculture', 'monthly', 'high', 'Crop supply, demand, and inventory estimates.', 'https://www.usda.gov/oce/commodity/wasde'),
('wef', 'World Economic Forum annual meeting', 'GLOBAL', 'equities bonds fx', 'annual', 'medium', 'Policy and business discussions that can signal changes in priorities.', 'https://www.weforum.org/meetings/'),
('cn_politburo', 'China Politburo policy meetings', 'CN HK', 'equities bonds fx metals', 'announcement-driven', 'high', 'Policy priorities and economic support measures.', 'https://www.gov.cn/'),
('cn_pmi', 'China manufacturing PMI', 'CN HK GLOBAL', 'equities bonds fx metals energy', 'monthly', 'high', 'A survey of manufacturing activity and business conditions.', 'https://www.stats.gov.cn/sj/fbrc/bnxxfb/'),
('pboc_mlf', 'PBOC medium-term lending facility operations', 'CN HK', 'bonds fx equities', 'announcement-driven', 'high', 'Central-bank funding supplied to financial institutions.', 'https://www.pbc.gov.cn/'),
('eu_pmi', 'Eurozone manufacturing PMI', 'EU GLOBAL', 'equities bonds fx metals', 'monthly', 'medium', 'Manufacturing survey results for the euro area.', 'https://www.pmi.spglobal.com/Public/Release/ReleaseDates'),
('eu_confidence', 'Euro-area consumer confidence', 'EU', 'equities bonds fx', 'monthly', 'medium', 'Household views of economic conditions.', 'https://economy-finance.ec.europa.eu/economic-forecast-and-surveys/business-and-consumer-surveys_en'),
('us_inflation', 'US CPI and PPI', 'US GLOBAL', 'equities bonds fx energy metals', 'monthly', 'high', 'Consumer and producer price releases; each has its own release date.', 'https://www.bls.gov/schedule/'),
('us_ism', 'US ISM manufacturing PMI', 'US GLOBAL', 'equities bonds fx metals', 'monthly', 'medium', 'US manufacturing survey results.', 'https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/'),
('us_auctions', 'US Treasury coupon auctions', 'US GLOBAL', 'bonds fx', 'auction-calendar', 'high', 'Government debt supply and auction demand.', 'https://www.treasurydirect.gov/auctions/upcoming/'),
('us_unemployment', 'US unemployment rate', 'US GLOBAL', 'equities bonds fx', 'monthly', 'high', 'A labor-market indicator published in the Employment Situation release.', 'https://www.bls.gov/news.release/empsit.toc.htm'),
('us_confidence', 'US consumer confidence', 'US', 'equities bonds fx', 'monthly', 'medium', 'Household assessments and expectations in the Conference Board survey.', 'https://www.conference-board.org/topics/consumer-confidence'),
('us_employment', 'US Employment Situation / nonfarm payrolls', 'US GLOBAL', 'equities bonds fx', 'monthly', 'high', 'Payrolls, unemployment, and wages in one release.', 'https://www.bls.gov/schedule/'),
('opec', 'OPEC+ policy and monitoring meetings', 'GLOBAL', 'energy fx equities', 'announcement-driven', 'high', 'Producer decisions and monitoring of oil production commitments.', 'https://www.opec.org/'),
('npc_standing', 'NPC Standing Committee sessions', 'CN HK', 'equities bonds fx', 'announcement-driven', 'medium', 'Legislation and fiscal decisions under consideration.', 'https://www.npc.gov.cn/'),
('wgbi', 'FTSE World Government Bond Index reviews', 'GLOBAL CN', 'bonds fx', 'review-calendar', 'medium', 'Changes to bond-index eligibility and membership.', 'https://www.lseg.com/en/ftse-russell/indices/world-government-bond-index'),
('asean_finance', 'ASEAN finance ministers and central-bank governors meetings', 'SEA GLOBAL', 'equities bonds fx', 'announcement-driven', 'medium', 'Regional financial and monetary cooperation.', 'https://asean.org/'),
('npc_annual', 'National People\'s Congress annual session', 'CN HK', 'equities bonds fx metals', 'annual', 'high', 'Annual policy, budget, and economic objectives.', 'https://www.npc.gov.cn/'),
('cn_bond_delivery', 'China Treasury futures delivery and roll', 'CN', 'bonds', 'contract-calendar', 'high', 'Contract expiry, delivery obligations, and roll-related liquidity.', 'https://www.cffex.com.cn/en_new/'),
('us_refunding', 'US Treasury quarterly refunding', 'US GLOBAL', 'bonds fx', 'quarterly', 'high', 'Treasury financing plans and debt issuance sizes.', 'https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding'),
('asean_summit', 'ASEAN summit', 'SEA GLOBAL', 'equities fx', 'announcement-driven', 'medium', 'Regional trade, security, and economic policy discussions.', 'https://asean.org/'),
('taipei_industry', 'Taipei industry exhibitions and economic forums', 'TW CN', 'equities', 'organizer-calendar', 'medium', 'Industry announcements and cross-border business discussions.', 'https://www.taitra.org.tw/'),
('jackson_hole', 'Jackson Hole economic policy symposium', 'US GLOBAL', 'equities bonds fx', 'annual', 'high', 'Central-bank speeches and monetary-policy research discussions.', 'https://www.kansascityfed.org/research/jackson-hole-economic-symposium/'),
('g20', 'G20 leaders summit', 'GLOBAL', 'equities bonds fx energy', 'annual', 'medium', 'International economic policy coordination.', 'https://www.g20.org/'),
('apec', 'APEC economic leaders meeting', 'CN HK TW SEA US GLOBAL', 'equities fx', 'annual', 'medium', 'Asia-Pacific trade and economic cooperation.', 'https://www.apec.org/'),
('cewc', 'China Central Economic Work Conference', 'CN HK', 'equities bonds fx metals', 'annual', 'high', 'Economic policy priorities for the following year.', 'https://www.gov.cn/'),
('mainland_hk_business', 'Mainland–Hong Kong business cooperation meetings', 'CN HK', 'equities', 'unscheduled', 'medium', 'Cross-border business and investment policy discussions.', 'https://www.hktdc.com/'),
('hk_executive', 'Hong Kong Executive Council decisions', 'HK CN', 'equities bonds', 'announcement-driven', 'medium', 'Hong Kong government policy decisions.', 'https://www.ceo.gov.hk/exco/eng/'),
('ecb_policy', 'ECB monetary policy meeting', 'EU GLOBAL', 'equities bonds fx', 'meeting-calendar', 'high', 'Euro-area monetary policy and central-bank communication.', 'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html'),
('eu_council', 'European Council summit', 'EU GLOBAL', 'equities bonds fx energy', 'meeting-calendar', 'medium', 'European policy, fiscal, trade, and security decisions.', 'https://www.consilium.europa.eu/en/meetings/european-council/'),
('fomc', 'Federal Open Market Committee meeting', 'US GLOBAL', 'equities bonds fx energy metals', 'meeting-calendar', 'high', 'US monetary policy decisions and communication.', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'),
('us_election', 'US presidential election', 'US GLOBAL', 'equities bonds fx energy', 'election-calendar', 'high', 'Election outcomes and potential policy changes.', 'https://www.usa.gov/election'),
('jp_fx_meeting', 'Japan financial-authority coordination meetings', 'JP GLOBAL', 'fx bonds equities', 'unscheduled', 'high', 'Coordination among finance and monetary authorities during market stress.', 'https://www.mof.go.jp/english/'),
('cross_strait', 'Cross-Strait Forum', 'CN TW HK', 'equities fx', 'organizer-calendar', 'medium', 'Cross-Strait economic and policy discussions.', 'https://www.gwytb.gov.cn/'),
('wto', 'WTO ministerial conference', 'GLOBAL', 'equities fx agriculture', 'organizer-calendar', 'medium', 'Multilateral trade negotiations and decisions.', 'https://www.wto.org/english/thewto_e/minist_e/minist_e.htm'),
('trade_talks', 'Bilateral and multilateral trade negotiations', 'GLOBAL CN US EU SEA', 'equities fx metals agriculture', 'unscheduled', 'high', 'Tariffs, market access, and trade agreements.', 'https://www.wto.org/'),
('sovereign_credit', 'Emerging-market sovereign debt stress', 'GLOBAL SEA', 'bonds fx equities', 'unscheduled', 'high', 'Debt negotiations, financing stress, and sovereign-credit developments.', 'https://www.imf.org/en/News'),
('ndrc_commodities', 'NDRC commodity-market interventions', 'CN GLOBAL', 'energy metals agriculture', 'unscheduled', 'high', 'Supply, reserve, and price-policy announcements for commodities.', 'https://en.ndrc.gov.cn/'),
('energy_grain_geopolitics', 'Energy and grain trade disruptions and agreements', 'GLOBAL EU', 'energy agriculture fx', 'unscheduled', 'high', 'Conflict-related changes to exports, transport, and supply agreements.', 'https://news.un.org/en/'),
]
CATALOG = {row[0]: dict(family_id=row[0], name=row[1], markets=row[2].split(), assets=row[3].split(),
                       cadence=row[4], priority=row[5], explanation=row[6], reference_url=row[7],
                       calendar_family='us_employment' if row[0] == 'us_unemployment' else row[0])
           for row in _ROWS}


def intersects(source_markets, requested):
    # GLOBAL is a cross-market tag, not the US market in disguise.
    return 'GLOBAL' in source_markets or 'GLOBAL' in requested or bool(set(source_markets) & set(requested))


def catalog(markets=None):
    return [deepcopy(v) for v in CATALOG.values() if intersects(v['markets'], markets or MARKETS)]


def watchlist(events, markets):
    covered = {e.get('family_id', 'fomc') for e in events}
    result = []
    for item in catalog(markets):
        family = item['calendar_family']
        if family in covered:
            continue
        covered.add(family)
        result.append({**item, 'family_id': family, 'event_id': 'watch-'+family,
                       'start_date': None, 'end_date': None, 'timezone': 'UTC',
                       'date_precision': 'unknown', 'date_status': 'watchlist', 'date_evidence': [],
                       'category': family, 'coverage_note': 'No dated occurrence verified in this window.'})
    return result
