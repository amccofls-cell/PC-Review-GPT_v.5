import json, sqlite3, re, calendar, math
from datetime import date
from pathlib import Path
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='자산배분 리밸런싱 도우미', page_icon='📊', layout='wide')


# ─────────────────────────────────────────────────────────────────────────────
# Mobile readability / responsive UI
# ─────────────────────────────────────────────────────────────────────────────
MOBILE_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
:root { --app-font: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
html, body, [class*="css"], button, input, textarea, select { font-family: var(--app-font) !important; letter-spacing: -0.012em; }
body { -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
h1, h2, h3, h4, h5, h6 { font-family: var(--app-font) !important; letter-spacing: -0.035em !important; }
div[data-testid="stMetricValue"] { font-family: var(--app-font) !important; letter-spacing: -0.03em !important; font-variant-numeric: tabular-nums; }
div[data-testid="stMetricLabel"] { font-family: var(--app-font) !important; letter-spacing: -0.015em !important; }
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 3rem !important;
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
    max-width: 100% !important;
}
div[data-testid="stMarkdownContainer"],
div[data-testid="stText"],
div[data-testid="stMetricValue"],
div[data-testid="stMetricLabel"] {
    overflow-wrap: anywhere;
    word-break: keep-all;
}
.stButton > button,
.stDownloadButton > button,
button[kind="primary"],
button[kind="secondary"] {
    min-height: 2.75rem !important;
    padding: 0.55rem 0.85rem !important;
    border-radius: 0.65rem !important;
}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
textarea {
    min-height: 2.65rem !important;
}
@media (min-width: 641px) {
    .block-container {
        max-width: 1180px !important;
        padding-left: 2.25rem !important;
        padding-right: 2.25rem !important;
    }
}
@media (max-width: 640px) {
    .block-container {
        padding-left: 0.65rem !important;
        padding-right: 0.65rem !important;
    }
    h1 { font-size: 1.55rem !important; line-height: 1.25 !important; }
    h2 { font-size: 1.30rem !important; line-height: 1.3 !important; }
    h3 { font-size: 1.12rem !important; line-height: 1.35 !important; }
    div[data-testid="stMetric"] {
        padding: 0.55rem 0.65rem !important;
        border-radius: 0.65rem !important;
    }
    div[data-testid="stMetricValue"] { font-size: 1.15rem !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.78rem !important; }
    div[data-testid="stDataFrame"],
    div[data-testid="stTable"] {
        max-width: 100% !important;
        overflow-x: auto !important;
    }
    details summary { padding: 0.75rem 0.5rem !important; }
    section[data-testid="stSidebar"] {
        min-width: min(82vw, 320px) !important;
        max-width: min(88vw, 360px) !important;
    }
}
.mobile-card {
    padding: 0.75rem 0.8rem;
    margin: 0.35rem 0 0.7rem 0;
    border-radius: 0.75rem;
    border: 1px solid rgba(128,128,128,.22);
}
.weight-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:12px 13px;margin:8px 0;box-shadow:0 1px 2px rgba(15,23,42,.03);}
.weight-head{display:flex;justify-content:space-between;gap:10px;align-items:center;font-weight:700;}
.weight-meta{font-size:.78rem;color:var(--muted);margin-top:5px;}
.weight-bar{height:12px;display:flex;overflow:hidden;border-radius:999px;background:#eef0f3;margin-top:9px;}
.weight-legend{display:flex;gap:9px;flex-wrap:wrap;font-size:.72rem;color:var(--muted);margin-top:7px;}
.weight-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:3px;}
.history-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:13px;margin:8px 0;box-shadow:0 1px 2px rgba(15,23,42,.03);}
.history-date{font-weight:750;color:var(--text);}
.history-sub{font-size:.78rem;color:var(--muted);margin-top:3px;}
/* Modern typography / controls */
.stButton > button, .stDownloadButton > button {
    font-family: var(--app-font) !important;
    font-weight: 650 !important;
    letter-spacing: -0.015em !important;
}
div[data-baseweb="select"] *, div[data-baseweb="input"] *, textarea,
div[data-testid="stDataFrame"], div[data-testid="stTable"] {
    font-family: var(--app-font) !important;
}
</style>
"""

st.markdown(MOBILE_CSS, unsafe_allow_html=True)
ROOT = Path(__file__).parent

def secret(name, default=''):
    """st.secrets.get()은 secrets.toml이 아예 없으면 기본값을 반환하지 않고 예외를 던진다(스트림릿 특유의 함정).
    그래서 항상 이 안전한 getter를 통해서만 시크릿에 접근한다."""
    try:
        return st.secrets[name]
    except Exception:
        return default

# app.py를 새로 받을 때마다 저장 위치(폴더)가 달라지면 그 옆의 portfolio.db도 매번 새로 생겨
# "데이터가 사라진 것처럼" 보인다. 그래서 스크립트 위치와 무관하게 항상 같은 사용자 홈 디렉터리 하위에
# DB를 둔다. SQLITE_PATH를 secrets에 직접 지정하면 그 값이 우선한다(예: 클라우드 배포 시 영구볼륨 경로).
try:
    _default_db_dir = Path.home() / '.asset_allocation_app'
    _default_db_dir.mkdir(parents=True, exist_ok=True)
    _default_db_path = str(_default_db_dir / 'portfolio.db')
except Exception:
    _default_db_path = str(ROOT / 'portfolio.db')
DB_PATH = secret('SQLITE_PATH', _default_db_path)

CATEGORY_OPTIONS = ['현금', '금', '선진국 주식', '신흥국 주식', '선진국 채권', '신흥국 채권', '기타']
YAHOO_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
APP_VERSION = '8.0'
KR_API_TIMEOUT = 6
YAHOO_API_TIMEOUT = 10

# ---------- Safe data normalization ----------
def safe_prices(value, fallback=None):
    if value is None:
        return list(fallback or [])
    try:
        if pd.isna(value):
            return list(fallback or [])
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        try: value = json.loads(value)
        except Exception: value = value.split(',')
    raw = value if isinstance(value, (list, tuple)) else [value]
    out = []
    for x in raw:
        try:
            if x is not None and not pd.isna(x): out.append(float(x))
        except (TypeError, ValueError): pass
    return out

def n(v, default=0.0):
    try:
        if v is None or pd.isna(v): return default
        return float(v)
    except (TypeError, ValueError): return default

def clean_records(df):
    df = df.copy()
    for c in ['target_pct', 'shares', 'close']:
        if c not in df:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    if 'prices' not in df:
        df['prices'] = [[] for _ in range(len(df))]
    df['prices'] = df['prices'].apply(safe_prices)
    for c in ['strategy', 'ticker', 'name', 'market', 'role', 'signal_ticker', 'category', 'kind', 'last_fetch_date', 'price_source']:
        if c not in df:
            df[c] = ''
        df[c] = df[c].fillna('').astype(str)
    df['signal_ticker'] = df.apply(lambda r: r['signal_ticker'] or r['ticker'], axis=1)
    df['market'] = df['market'].apply(lambda m: m if m in ('KR', 'US') else 'KR')
    df['category'] = df['category'].apply(lambda c: c if c in CATEGORY_OPTIONS else '기타')
    if 'id' not in df or df['id'].isna().any() or (df['id'] == '').any():
        df['id'] = [str(i) for i in range(len(df))]
    return df.reset_index(drop=True)

# ---------- 전략/자산 기본값 ----------
# LAA 자산 목표비중 합이 원래 매뉴얼(12.5+12.5+12.5+15.5+25+25=103%)대로면 100%를 넘어 저장이 안 됩니다.
# 국채 비중을 22%로 맞춰 정확히 100%가 되도록 보정했습니다 — 실제 원하시는 배분과 다르면 전략 구성에서 조정하세요.
DEFAULT_STRATEGIES = [
    {'code': 'LAA', 'account': '과세 연금저축', 'description': '변형 LAA — 나스닥/유로스탁스만 10개월 SMA 필터, 이탈 시 현금화. 목표비중 복원은 분기 말에만.', 'dynamic': False, 'active': True, 'annual_limit': 0.0},
    {'code': 'GSM', 'account': '비과세 연금저축', 'description': '글로벌 단순 모멘텀 — SMA 통과 후보 중 12개월 수익률 1위에 80% 투자, 20% 현금. 월 1회 리밸런싱.', 'dynamic': True, 'active': True, 'annual_limit': 0.0},
    {'code': 'ISA', 'account': 'ISA', 'description': '나스닥 레버리지 트리거 — 나스닥100 고점대비 -10% 하락 시 분할매수.', 'dynamic': False, 'active': True, 'annual_limit': 0.0},
    {'code': 'SSO', 'account': '일반계좌 2', 'description': 'S&P500 ETF + 현금성 자산. S&P500 고점대비 -15% 하락 시 현금 절반 투입.', 'dynamic': False, 'active': True, 'annual_limit': 0.0},
    {'code': 'EM', 'account': '일반계좌 1', 'description': '신흥국 분산 장기보유. 리밸런싱은 연 1회 정도만.', 'dynamic': False, 'active': True, 'annual_limit': 0.0},
]
KNOWN_STRATEGIES = {'LAA', 'GSM', 'ISA', 'SSO', 'EM'}  # 전용 리밸런싱 규칙이 있는 전략(하드코딩된 룰, 이름 변경 금지)
STRATEGY_DISPLAY_ORDER = ['LAA', 'GSM', 'ISA', 'SSO', 'EM']  # Action Plan에 보여주는 우선순위

DEFAULT_ROWS = [
    # strategy, ticker, name, market, role, target_pct, category
    ('LAA', '133690', 'TIGER 미국나스닥100', 'KR', 'NASDAQ', 12.5, '선진국 주식'),
    ('LAA', '245350', 'TIGER 유로스탁스배당30', 'KR', 'EuroStoxx', 12.5, '선진국 주식'),
    ('LAA', '360750', 'TIGER 미국S&P500', 'KR', 'S&P500', 12.5, '선진국 주식'),
    ('LAA', '251350', 'KODEX 선진국MSCI World', 'KR', 'MSCI World', 15.5, '선진국 주식'),
    ('LAA', '132030', 'KODEX 골드선물(H)', 'KR', 'Gold', 25.0, '금'),
    ('LAA', '148070', 'KIWOOM 국고채10년', 'KR', 'Bond', 22.0, '선진국 채권'),
    ('LAA', 'CASH', '현금', 'KR', '필터이탈 대기현금', 0.0, '현금'),
    ('GSM', '360750', 'TIGER 미국S&P500', 'KR', 'GSM 후보', 0.0, '선진국 주식'),
    ('GSM', '251350', 'KODEX 선진국MSCI World', 'KR', 'GSM 후보', 0.0, '선진국 주식'),
    ('GSM', '133690', 'TIGER 미국나스닥100', 'KR', 'GSM 후보', 0.0, '선진국 주식'),
    ('GSM', '245350', 'TIGER 유로스탁스배당30', 'KR', 'GSM 후보', 0.0, '선진국 주식'),
    ('GSM', 'CASH', '현금', 'KR', '대기현금', 20.0, '현금'),
    ('ISA', '418660', 'TIGER 미국나스닥100레버리지(합성)', 'KR', '-10% 트리거', 0.0, '선진국 주식'),
    ('ISA', 'CASH', '현금', 'KR', '대기현금', 100.0, '현금'),
    ('SSO', '360750', 'TIGER 미국S&P500', 'KR', 'S&P500 기준', 70.0, '선진국 주식'),
    ('SSO', '153130', 'KODEX 단기채권', 'KR', '현금성', 30.0, '현금'),
    ('EM', '069500', 'KODEX 200', 'KR', '한국', 25.0, '신흥국 주식'),
    ('EM', '', '중국 ETF 입력', 'KR', '중국', 25.0, '신흥국 주식'),
    ('EM', '', '인도 ETF 입력', 'KR', '인도', 25.0, '신흥국 주식'),
    ('EM', '', '베트남 ETF 입력', 'KR', '베트남', 25.0, '신흥국 주식'),
]
# ISA는 실제로 레버리지 상품(418660)을 매매하지만, 트리거 판단은 QQQ를 기준으로 한다.
# signal_ticker는 트리거 신호용 티커이며 실제 매매 티커와 분리한다.
# QQQ는 미국 상장 ETF이므로 트리거 조회 시 시장도 US로 강제한다.
SIGNAL_TICKER_OVERRIDE = {'418660': 'QQQ'}

def default_assets():
    rows = []
    for i, (strat, ticker, nm, mkt, role, tgt, cat) in enumerate(DEFAULT_ROWS):
        rows.append({
            'id': str(i), 'strategy': strat, 'ticker': ticker, 'name': nm, 'market': mkt, 'role': role,
            'target_pct': tgt, 'shares': 0.0, 'close': (1.0 if ticker == 'CASH' else 0.0), 'prices': [],
            'signal_ticker': SIGNAL_TICKER_OVERRIDE.get(ticker, ticker), 'category': cat,
            'last_fetch_date': '', 'price_source': '',
        })
    return pd.DataFrame(rows)

# ---------- SQLite persistence ----------
# 이 번호를 올리면(정수 +1) 다음 실행 시 price_cache가 자동으로 통째로 비워진다.
# 예전 버전의 버그(예: 모든 티커에 같은 종가가 붙던 문제)로 잘못된 값이 이미 캐시에 저장돼 있으면,
# 이후 로직을 아무리 고쳐도 캐시가 "성공"으로 잘못 응답하며 그 나쁜 값을 계속 돌려주기 때문에
# 사용자가 매번 수동으로 캐시를 지워야 했다. 이제는 코드 쪽에서 캐시가 이 버전으로 만들어진 게
# 맞는지 확인하고, 아니면 알아서 지운다.
PRICE_CACHE_SCHEMA_VERSION = '6'  # adjclose 컬럼 추가(배당재투자 기준 선택 시 사용)

def init_db():
    con = sqlite3.connect(DB_PATH); con.execute('CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY,v TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS cache_meta(k TEXT PRIMARY KEY, v TEXT)')
    # 구버전 price_cache는 (ticker,date,close) 구조라 새 날짜/시장 캐시와 호환되지 않는다.
    cols = [r[1] for r in con.execute('PRAGMA table_info(price_cache)').fetchall()]
    if cols and not {'market','ticker','date','close','source'}.issubset(set(cols)):
        con.execute('DROP TABLE price_cache')
    con.execute('CREATE TABLE IF NOT EXISTS price_cache(market TEXT, ticker TEXT, date TEXT, close REAL, adjclose REAL, source TEXT, PRIMARY KEY(market, ticker, date))')
    cur_cols = [r[1] for r in con.execute('PRAGMA table_info(price_cache)').fetchall()]
    if 'adjclose' not in cur_cols:
        try: con.execute('ALTER TABLE price_cache ADD COLUMN adjclose REAL')
        except Exception: pass
    con.execute('CREATE TABLE IF NOT EXISTS fx_cache(date TEXT PRIMARY KEY, rate REAL, source TEXT)')
    row = con.execute("SELECT v FROM cache_meta WHERE k='schema_version'").fetchone()
    if row is None or row[0] != PRICE_CACHE_SCHEMA_VERSION:
        con.execute('DELETE FROM price_cache'); con.execute('DELETE FROM fx_cache')
        con.execute("INSERT OR REPLACE INTO cache_meta(k,v) VALUES('schema_version', ?)", (PRICE_CACHE_SCHEMA_VERSION,))
    for k, v in [
        ('assets', default_assets().to_json(orient='records', force_ascii=False)),
        ('history', '[]'), ('equity', '[]'), ('cashflows', '[]'), ('benchmarks', '[]'),
        ('strategies', json.dumps(DEFAULT_STRATEGIES, ensure_ascii=False)),
        ('category_targets', json.dumps({c: 0.0 for c in CATEGORY_OPTIONS}, ensure_ascii=False)),
        ('executions', '[]'),
    ]:
        con.execute('INSERT OR IGNORE INTO kv(k,v) VALUES(?,?)', (k, v))
    con.commit(); con.close()

def get_state(k):
    init_db(); con = sqlite3.connect(DB_PATH); r = con.execute('SELECT v FROM kv WHERE k=?', (k,)).fetchone(); con.close()
    return json.loads(r[0])

def put_state(k, v):
    init_db(); con = sqlite3.connect(DB_PATH)
    con.execute('INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)', (k, json.dumps(v, ensure_ascii=False, default=str)))
    con.commit(); con.close()

# ---------- 종목별 가격 캐시 ----------
# DB 캐시와 Streamlit 메모리 캐시를 분리해서 관리한다.
# "캐시 삭제" 버튼을 눌렀는데 Yahoo 결과가 다시 나오는 문제는
# st.cache_data와 SQLite 캐시가 서로 다른 층이기 때문에 발생할 수 있다.
PRICE_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30

def _cache_market_ticker(market, ticker):
    market = str(market or 'KR').upper(); ticker = str(ticker).strip()
    return market, (kr6(ticker) if market == 'KR' else ticker.upper())

def cache_get_prices(ticker, market='KR'):
    """가격 캐시를 항상 ticker/date/close 3개 컬럼으로 반환한다.
    v7은 SQL에서 date, close만 읽은 뒤 월별/일별 로직에서 ticker 컬럼을 선택해
    KeyError("['ticker'] not in index")가 발생했다.
    """
    market, ticker_norm = _cache_market_ticker(market, ticker); init_db(); con=sqlite3.connect(DB_PATH)
    try:
        df=pd.read_sql_query('SELECT ticker, date, close, adjclose FROM price_cache WHERE market=? AND ticker=? ORDER BY date',con,params=(market,ticker_norm))
    finally:
        con.close()
    if df.empty:
        return pd.DataFrame(columns=['ticker','date','close','adjclose'])
    df['ticker']=df['ticker'].astype(str)
    df['date']=df['date'].astype(str).str.replace('-','',regex=False)
    df['close']=pd.to_numeric(df['close'],errors='coerce')
    df['adjclose']=pd.to_numeric(df['adjclose'],errors='coerce')
    df['adjclose']=df['adjclose'].fillna(df['close'])
    df=df.dropna(subset=['date','close']); df=df[df['close']>0]
    return df[['ticker','date','close','adjclose']].reset_index(drop=True)

def cache_put_prices(ticker, rows, market='KR', source=''):
    market,ticker_norm=_cache_market_ticker(market,ticker)
    if not rows: return 0
    clean=[]
    for r in rows:
        if not isinstance(r,dict): continue
        d=str(r.get('date','')).replace('-','')
        try: close=float(r.get('close'))
        except (TypeError,ValueError): continue
        if len(d)==8 and close>0:
            adj=None
            if r.get('adjclose') is not None:
                try:
                    adj=float(r.get('adjclose'))
                    if adj<=0: adj=None
                except (TypeError,ValueError): adj=None
            clean.append((market,ticker_norm,d,close,adj,str(r.get('source',source) or source)))
    if not clean: return 0
    init_db(); con=sqlite3.connect(DB_PATH)
    try: con.executemany('INSERT OR REPLACE INTO price_cache(market,ticker,date,close,adjclose,source) VALUES(?,?,?,?,?,?)',clean); con.commit()
    finally: con.close()
    return len(clean)

def cache_clear_prices():
    init_db(); con=sqlite3.connect(DB_PATH)
    try: con.execute('DELETE FROM price_cache'); con.execute('DELETE FROM fx_cache'); con.commit()
    finally: con.close()
    clear_runtime_price_cache()

def cache_clear_prices_for(ticker, market=None):
    init_db(); con=sqlite3.connect(DB_PATH)
    try:
        if market:
            market,ticker_norm=_cache_market_ticker(market,ticker); con.execute('DELETE FROM price_cache WHERE market=? AND ticker=?',(market,ticker_norm))
        else: con.execute('DELETE FROM price_cache WHERE ticker IN (?,?)',(str(ticker).upper(),kr6(ticker)))
        con.commit()
    finally: con.close()
    clear_runtime_price_cache()

def cache_clear_fx():
    init_db(); con=sqlite3.connect(DB_PATH)
    try: con.execute('DELETE FROM fx_cache'); con.commit()
    finally: con.close()
    try: get_usd_krw_rate.clear()
    except Exception: pass
    clear_runtime_price_cache()

def clear_runtime_price_cache():
    try: fetch_yahoo_range.clear()
    except Exception: pass

def clear_all_price_caches():
    clear_runtime_price_cache()
    for fn in (load_kr_individual_stocks, load_krx_universe):
        try: fn.clear()
        except Exception: pass

PRICE_POLICY_DEFAULT = 'strict'  # 'strict': 해당 날짜만 / 'prev': 직전 거래일 대체 허용(트리거 제외)
PRICE_MODE_DEFAULT = 'close'    # 'close': 원시 종가 / 'adjclose': 배당재투자 기준(미국 종목 SMA·모멘텀·트리거)

def price_policy():
    try:
        v = get_state('price_policy')
        return v if v in ('strict', 'prev') else PRICE_POLICY_DEFAULT
    except Exception:
        return PRICE_POLICY_DEFAULT

def use_adjclose():
    try:
        v = get_state('price_mode')
        return v == 'adjclose'
    except Exception:
        return False

PRICE_DATA_HELP = ('가격은 사용자가 지정한 조회일자를 그대로 기준으로 가져옵니다. 휴장일 정책이 "직전 거래일 대체"면 해당 날짜의 종가가 없는 경우에만 직전 거래일 값으로 대체하고, 이 경우 실제 사용된 거래일이 신선도 표에 함께 표시됩니다. 미국 종목은 같은 조회일자의 USD/KRW 환율을 적용해 원화 평가액을 계산합니다(환율도 같은 정책을 따릅니다).')

# ---------- KRX 종목(ETF+개별주식) 카탈로그 ----------

@st.cache_data(ttl=86400, show_spinner=False)
def load_kr_individual_stocks(asof):
    """코스피/코스닥 개별종목(삼성전자 등) 이름+코드 목록.
    KRX Open API의 etf_bydd_trd는 이름 그대로 ETF 전용이라 개별종목이 원천적으로 안 나오고,
    pykrx(비공식 스크래핑)는 KRX 사이트 변경으로 로그인 요구/파싱 실패가 잦아 신뢰할 수 없다.
    공공데이터포털의 금융위원회_주식시세정보(GetStockSecuritiesInfoService)는 정부가 운영하는
    공식 REST API라 훨씬 안정적이다. https://www.data.go.kr/data/15094808/openapi.do
    """
    key = secret('DATA_GO_SERVICE_KEY')
    empty = pd.DataFrame(columns=['ticker', 'name', 'market', 'type'])
    if not key:
        empty.attrs['error'] = 'DATA_GO_SERVICE_KEY가 secrets에 설정되어 있지 않음(개별종목 검색에 필요, data.go.kr에서 "금융위원회_주식시세정보" 활용신청 후 발급받은 키)'
        return empty
    d = pd.Timestamp(asof)
    last_err = ''
    for _ in range(10):
        try:
            rows_all = []; page = 1
            while page <= 6:
                r = requests.get(secret('DATA_GO_URL', DATA_GO_STOCK_URL_DEFAULT), params={
                    'serviceKey': key, 'resultType': 'json', 'numOfRows': 1000, 'pageNo': page,
                    'basDt': d.strftime('%Y%m%d'),
                }, timeout=KR_API_TIMEOUT)
                r.raise_for_status()
                body = (r.json().get('response') or {}).get('body') or {}
                items = (body.get('items') or {}).get('item') or []
                if isinstance(items, dict): items = [items]
                if not items: break
                rows_all.extend(items)
                total = int(body.get('totalCount', 0) or 0)
                if len(rows_all) >= total: break
                page += 1
            if rows_all:
                out = pd.DataFrame([
                    {'ticker': kr6(str(x.get('srtnCd', ''))), 'name': str(x.get('itmsNm', '')), 'mkt': str(x.get('mrktCtg', ''))}
                    for x in rows_all if x.get('srtnCd')
                ])
                out = out[out['ticker'] != '']
                if not out.empty:
                    out['type'] = out['mkt'].map(lambda m: f'주식({m})' if m else '주식')
                    out['market'] = 'KR'
                    return out[['ticker', 'name', 'market', 'type']].drop_duplicates('ticker')
        except Exception as e:
            last_err = str(e)
        d -= pd.Timedelta(days=1)
    empty.attrs['error'] = last_err or '공공데이터포털 응답이 비어 있음(휴장일 반복?)'
    return empty

@st.cache_data(ttl=86400, show_spinner=False)
def load_krx_universe(asof):
    """한국 상장 종목(ETF+개별주식) 검색용 카탈로그.
    이전에는 pykrx(비공식 스크래핑 라이브러리)에만 의존했는데, 설치가 안 돼 있거나 실패하면
    아무 안내 없이 빈 목록이 나오는 문제가 있었다. 이제는 가격 조회에 이미 쓰고 있는(즉 이미
    인증이 확인된) KRX Open API 응답에서 ETF 목록을, 공공데이터포털 API에서 개별종목 목록을
    각각 안정적으로 직접 구성한다. pykrx는 혹시 몰라 최후의 보강 수단으로만 시도한다.
    반환값에 'error' 컬럼이 있으면 검색 UI에서 그 사유를 그대로 보여준다.
    """
    frames = []; notes = []
    url, key = secret('KRX_BASE_URL'), secret('KRX_AUTH_KEY')
    if url and key:
        d = pd.Timestamp(asof); got = False; etf_err = ''
        for _ in range(10):
            try:
                r = requests.get(url, headers={'AUTH_KEY': key}, params={'basDd': d.strftime('%Y%m%d')}, timeout=KR_API_TIMEOUT)
                r.raise_for_status()
                rows = r.json().get('OutBlock_1', [])
                if rows:
                    etf_df = pd.DataFrame([
                        {'ticker': kr6(str(x.get('ISU_CD', ''))), 'name': str(x.get('ISU_NM', ''))}
                        for x in rows if x.get('ISU_CD')
                    ])
                    etf_df = etf_df[etf_df['ticker'] != '']
                    etf_df['type'] = 'ETF'
                    frames.append(etf_df); got = True
                    break
            except Exception as e:
                etf_err = str(e)
            d -= pd.Timedelta(days=1)
        if not got: notes.append(f'ETF: {etf_err or "응답이 비어 있음(휴장일 반복?)"}')
    else:
        notes.append('ETF: KRX_AUTH_KEY/KRX_BASE_URL이 secrets에 설정되어 있지 않음')

    stocks = load_kr_individual_stocks(asof)
    if not stocks.empty:
        frames.append(stocks)
    else:
        notes.append(f"개별종목: {stocks.attrs.get('error', '가져오지 못함')}")

    try:
        from pykrx import stock
        for mkt in ('KOSPI', 'KOSDAQ'):
            st_t = stock.get_market_ticker_list(pd.Timestamp(asof).strftime('%Y%m%d'), market=mkt)
            frames.append(pd.DataFrame([{'ticker': str(t), 'name': str(stock.get_market_ticker_name(t)), 'type': f'주식({mkt})'} for t in st_t]))
    except Exception:
        pass  # 개별주식 보강은 실패해도 지장 없음(조용히 건너뜀) — 이미 data.go.kr로 커버됨
    if frames:
        out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=['ticker'])
        out['market'] = 'KR'
        if not out.empty: return out
    p = ROOT / 'krx_etf_fallback.csv'
    if p.exists():
        d2 = pd.read_csv(p, dtype=str).fillna(''); d2['type'] = 'ETF'
        return d2
    empty = pd.DataFrame(columns=['ticker', 'name', 'market', 'type'])
    empty.attrs['error'] = ' / '.join(notes) if notes else '목록을 가져오지 못함'
    return empty

@st.cache_data(ttl=3600, show_spinner=False)
def search_us_symbols(query):
    if not query: return pd.DataFrame(columns=['ticker', 'name', 'exchange'])
    try:
        r = requests.get('https://query2.finance.yahoo.com/v1/finance/search',
                          params={'q': query, 'quotesCount': 15, 'newsCount': 0}, headers=YAHOO_HEADERS, timeout=15)
        r.raise_for_status(); quotes = r.json().get('quotes', [])
        rows = [{'ticker': q.get('symbol'), 'name': q.get('shortname') or q.get('longname') or q.get('symbol'), 'exchange': q.get('exchange', '')}
                for q in quotes if q.get('symbol') and q.get('quoteType') in ('EQUITY', 'ETF', None)]
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=['ticker', 'name', 'exchange'])

# ---------- KRX / data.go 가격 어댑터 ----------
def kr6(x):
    """한국 상장코드는 항상 6자리(예: 069500)인데, 어딘가에서 숫자로 한 번이라도 변환되면
    앞의 0이 사라져 '69500'처럼 5자리가 되고, 그러면 API 응답의 6자리 코드와 절대 매칭이
    안 돼 '조회는 되는데 이 종목만 안 됨' 현상이 생긴다. 비교/저장 전에 항상 6자리로 맞춘다."""
    d = re.sub(r'\D', '', str(x))
    return d.zfill(6) if d else str(x)

def normalize_payload(payload, requested=''):
    if isinstance(payload, dict):
        rows = payload.get('data', payload.get('OutBlock_1', payload.get('response', {}).get('body', {}).get('items', {}).get('item', payload)))
    else:
        rows = payload
    if isinstance(rows, dict): rows = [rows]
    out = []
    for x in rows or []:
        if not isinstance(x, dict): continue
        # KRX Open API(ETF 일별매매정보)는 종목코드 필드가 ISU_CD, 기준일자가 BAS_DD로 온다.
        # 공공데이터포털 금융위원회_주식시세정보는 종목코드가 srtnCd, 기준일자가 basDt, 종가가 clpr, 종목명이 itmsNm이다.
        # 이 키들이 빠져 있으면 모든 행의 ticker가 요청값(requested)으로 뭉개지고, 그 결과
        # 필터링이 항상 "전체 응답"을 반환해 마지막 행(임의의 한 종목) 가격이 모든 티커에 붙는 버그가 생긴다.
        raw_ticker = str(x.get('symbol', x.get('ISU_SRT_CD', x.get('ISU_CD', x.get('srtnCd', x.get('isu_srt_cd', x.get('ticker', requested)))))))
        digits = re.sub(r'\D', '', raw_ticker)
        ticker = kr6(digits) if digits else raw_ticker.replace('.KS', '').strip()
        d = str(x.get('date', x.get('basDd', x.get('BAS_DD', x.get('basDt', x.get('stck_bsop_date', '')))))).replace('-', '')
        close = x.get('close', x.get('TDD_CLSPRC', x.get('clpr', x.get('stck_clpr', x.get('price')))))
        name = x.get('name', x.get('ISU_NM', x.get('itmsNm', '')))
        if close is None or close == '-': continue
        try:
            out.append({'ticker': ticker, 'date': d, 'close': float(str(close).replace(',', '')), 'name': str(name)})
        except (ValueError, TypeError):
            pass
    return pd.DataFrame(out)

DATA_GO_STOCK_URL_DEFAULT = 'https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo'
DATA_GO_ETF_URL_DEFAULT = 'https://apis.data.go.kr/1160100/service/GetSecuritiesProductInfoService/getETFPriceInfo'
# 개별주식 일별매매정보(sto/stk_bydd_trd). 응답 OutBlock_1의 키는
# BAS_DD / ISU_CD / ISU_NM / TDD_CLSPRC로 ETF 엔드포인트와 동일 → normalize_payload 재사용.
# 모드='krx'에서 자동 우선 호출되며, 비거나 실패면 data.go.kr(data_go)로 부드럽게 넘어간다.
KRX_STK_URL_DEFAULT = 'https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd'


def fetch_day(source, ticker, day):
    ticker_norm = kr6(ticker)
    if source == 'krx':
        # 모드='krx'면 ① 개별주식 엔드포인트 → ② 기존(주로 ETF) 엔드포인트 순으로 시도.
        # 어느 한쪽이라도 해당 ticker를 찾으면 즉시 반환. 둘 다 응답이 비거나(휴장일)
        # 인증/네트워크 오류면 조용히 넘어가고, 끝에 다다르면 자동으로 data.go.kr로 폴백.
        key = secret('KRX_AUTH_KEY')
        if not key: raise RuntimeError('KRX_AUTH_KEY 미설정(secrets.toml 또는 Streamlit secrets에 추가 필요)')
        krx_tried = False
        # 같은 URL을 두 번 치는 사고 방지(사용자가 KRX_STK_URL을 KRX_BASE_URL로 지정한 경우)
        _seen = set()
        for url in (secret('KRX_STK_URL', KRX_STK_URL_DEFAULT), secret('KRX_BASE_URL', '')):
            if not url or url in _seen: continue
            _seen.add(url); krx_tried = True
            try:
                r = requests.get(url, headers={'AUTH_KEY': key},
                                 params={'basDd': day.replace('-', '')}, timeout=KR_API_TIMEOUT)
                r.raise_for_status()
                df = normalize_payload(r.json(), ticker_norm)
                if df.empty: continue                         # 휴장일・키 불일치 → 다음 URL
                hit = df[df['ticker'].eq(ticker_norm)]
                if not hit.empty: return hit                  # 종목 매칭 성공
            except Exception:
                continue                                      # 인증/타임아웃 → 다음 URL
        if krx_tried:
            source = 'data_go'                                # 자동 폴백 (사용자 모드 전환 불필요)
        else:
            raise RuntimeError('KRX_STK_URL 또는 KRX_BASE_URL이 secrets에 설정되어 있지 않음')

    key = secret('DATA_GO_SERVICE_KEY')
    if not key: raise RuntimeError('DATA_GO_SERVICE_KEY 미설정')
    etf_url = secret('DATA_GO_ETF_URL', DATA_GO_ETF_URL_DEFAULT)
    stock_url = secret('DATA_GO_URL', DATA_GO_STOCK_URL_DEFAULT)
    last_err = None
    for url in (etf_url, stock_url):
        try:
            # 금융위원회 API는 종목코드 검색이 itmsNm(종목명)이 아니라 likeSrtnCd(종목코드 LIKE검색)다.
            r = requests.get(url, params={'serviceKey': key, 'resultType': 'json', 'numOfRows': 10, 'pageNo': 1,
                                           'basDt': day.replace('-', ''), 'likeSrtnCd': ticker_norm}, timeout=KR_API_TIMEOUT)
            r.raise_for_status(); df = normalize_payload(r.json(), ticker_norm)
            if df.empty:
                last_err = RuntimeError(f'{ticker}: 응답 없음(휴장일이거나 API 설정 확인 필요)'); continue
            hit = df[df['ticker'].eq(ticker_norm)]
            if hit.empty:
                last_err = RuntimeError(f'{ticker}: 해당 일자 데이터에서 종목코드를 찾지 못함'); continue
            return hit
        except Exception as e:
            last_err = e
    raise last_err or RuntimeError(f'{ticker}: data.go.kr 조회 실패')

def fetch_data_go_range(ticker, start_day, end_day):
    """공공데이터포털에서 한 종목의 과거 구간을 한 번에 가져온다.
    날짜별 반복 호출을 피하기 위한 역사 데이터 전용 경로."""
    key = secret('DATA_GO_SERVICE_KEY')
    if not key:
        raise RuntimeError('DATA_GO_SERVICE_KEY 미설정')
    ticker_norm = kr6(ticker)
    for url in (secret('DATA_GO_ETF_URL', DATA_GO_ETF_URL_DEFAULT), secret('DATA_GO_URL', DATA_GO_STOCK_URL_DEFAULT)):
        try:
            params = {
                'serviceKey': key, 'resultType': 'json', 'numOfRows': 1000, 'pageNo': 1,
                'beginBasDt': pd.Timestamp(start_day).strftime('%Y%m%d'),
                'endBasDt': pd.Timestamp(end_day).strftime('%Y%m%d'),
                'likeSrtnCd': ticker_norm,
            }
            r = requests.get(url, params=params, timeout=KR_API_TIMEOUT)
            r.raise_for_status()
            df = normalize_payload(r.json(), ticker_norm)
            if not df.empty:
                hit = df[(df['ticker'] == ticker_norm) & (df['date'] >= params['beginBasDt']) & (df['date'] <= params['endBasDt'])]
                if not hit.empty:
                    return hit.drop_duplicates('date').sort_values('date').reset_index(drop=True)
        except Exception:
            continue
    return pd.DataFrame()


def find_trading_day_price(source, ticker, target_date, max_back=10):
    """지정 날짜의 가격만 찾는다. 휴장일이면 다른 날짜를 성공값으로 반환하지 않는다.
    내부적으로만 API가 날짜 범위를 조금 넓혀 응답하는 경우를 허용한다."""
    d = pd.Timestamp(target_date)
    try:
        x = fetch_day(source, str(ticker), d.strftime('%Y-%m-%d'))
        if not x.empty:
            hit = x[x['date'].eq(d.strftime('%Y%m%d'))]
            if not hit.empty:
                return hit.iloc[-1].to_dict()
    except Exception:
        pass
    return None


def find_month_last_trading_price(source, ticker, month_end, max_back=10):
    """SMA용 과거 월 데이터 전용: 월말이 휴장일이면 같은 달 안에서 직전 거래일을 찾는다.
    선택한 리밸런싱 기준일의 종가에는 절대 사용하지 않는다.
    """
    d = pd.Timestamp(month_end)
    month = d.month
    for back in range(max_back + 1):
        cand = d - pd.Timedelta(days=back)
        if cand.month != month:
            break
        row = find_trading_day_price(source, ticker, cand)
        if row:
            return row
    return None


def _month_end_freq():
    try:
        pd.date_range('2020-01-01', periods=2, freq='ME')
        return 'ME'
    except Exception:
        return 'M'


def _kr_cached_history(ticker):
    cached = cache_get_prices(kr6(ticker), 'KR')
    if cached.empty:
        return cached
    cached = cached.drop_duplicates('date').sort_values('date')
    return cached


def fetch_monthly(source, ticker, day, force_refresh=False):
    """SMA/모멘텀용 월별 가격을 안정적으로 확보한다.

    핵심 원칙
    - 선택일 종가는 이 함수와 완전히 분리되어 정확한 선택일만 사용한다.
    - SMA용 데이터는 최근 13개월의 각 월 마지막 거래일을 사용한다.
    - 기존 캐시가 10개월 이상이면 재사용한다.
    - 부족하면 18개월 범위 API를 먼저 다시 시도하고, 그래도 부족한 달만 단건 보완한다.
    - API가 일부 기간만 반환해도 '7개월에서 끝'나지 않도록 missing month를 채운다.
    """
    ticker_norm = kr6(ticker)
    end = pd.Timestamp(day)
    # 13개 월별 관측치를 안정적으로 만들기 위해 18개월의 일별 원천 데이터를 확보
    start = end - pd.DateOffset(months=18)
    a, b = start.strftime('%Y%m%d'), end.strftime('%Y%m%d')

    cached = _kr_cached_history(ticker_norm)
    cached = cached[(cached['date'] >= a) & (cached['date'] <= b)] if not cached.empty else cached

    def monthly_from(df):
        if df is None or df.empty:
            return pd.DataFrame(columns=['ticker','date','close'])
        x = df.copy()
        x['date_dt'] = pd.to_datetime(x['date'], format='%Y%m%d', errors='coerce')
        x = x.dropna(subset=['date_dt']).sort_values('date_dt')
        x = x[x['date_dt'] <= end]
        if x.empty:
            return pd.DataFrame(columns=['ticker','date','close'])
        x['month'] = x['date_dt'].dt.to_period('M')
        out = x.groupby('month', as_index=False).tail(1).copy()
        out['ticker'] = ticker_norm
        return out[['ticker','date','close']].sort_values('date').tail(13).reset_index(drop=True)

    out = monthly_from(cached)
    if not force_refresh and len(out) >= 13:
        return out

    # 범위 API는 18개월을 요청해 휴장일/누락 구간 때문에 13개월이 모자라는 현상을 방지
    hist = fetch_data_go_range(ticker_norm, start, end)
    if not hist.empty:
        cache_put_prices(ticker_norm, hist.to_dict('records'), market='KR', source='data_go_range')
        merged = pd.concat([cached, hist], ignore_index=True) if not cached.empty else hist.copy()
        out = monthly_from(merged.drop_duplicates('date'))

    if len(out) >= 13:
        return out

    # 그래도 부족하면 '없는 달'만 찾아 단건 조회한다. 전체 13개월을 무조건 반복 호출하지 않는다.
    existing_months = set()
    if not out.empty:
        existing_months = set(pd.to_datetime(out['date'], format='%Y%m%d').dt.to_period('M').astype(str))
    target_months = list(pd.period_range(end=end.to_period('M'), periods=13, freq='M'))
    supplement = []
    for period in target_months:
        key = str(period)
        if key in existing_months:
            continue
        month_end = period.to_timestamp(how='end').normalize()
        row = find_month_last_trading_price(source, ticker_norm, month_end, max_back=12)
        if row:
            supplement.append(row)
    if supplement:
        cache_put_prices(ticker_norm, supplement, market='KR', source='data_go_single')
        merged_parts = [x for x in [cached, hist if 'hist' in locals() else pd.DataFrame(), pd.DataFrame(supplement)] if x is not None and not x.empty]
        merged = pd.concat(merged_parts, ignore_index=True) if merged_parts else pd.DataFrame()
        out = monthly_from(merged.drop_duplicates('date'))
    return out

def fetch_daily_recent(source, ticker, day, days=120, force_refresh=False):
    ticker_norm = kr6(ticker); end = pd.Timestamp(day); start = end - pd.Timedelta(days=days)
    a = start.strftime('%Y%m%d'); b = end.strftime('%Y%m%d')
    cached = _kr_cached_history(ticker_norm)
    if not cached.empty:
        cached = cached[(cached['date'] >= a) & (cached['date'] <= b)]
    if force_refresh or cached.empty or len(cached) < max(20, int(days * 0.45)):
        hist = fetch_data_go_range(ticker_norm, start, end)
        if not hist.empty:
            cache_put_prices(ticker_norm, hist.to_dict('records'), market='KR', source='data_go_range')
            cached = hist
    return cached.drop_duplicates('date').sort_values('date') if not cached.empty else pd.DataFrame()

# ---------- Yahoo Finance 가격 어댑터 (미국 상장 종목 + 벤치마크) ----------
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_yahoo_range(symbol, period1, period2, interval='1d', refresh_key=0):
    """Yahoo chart API. query1 장애/차단 시 query2로 자동 재시도한다."""
    last_err=None
    params={'period1':int(period1),'period2':int(period2),'interval':interval,'events':'history','includeAdjustedClose':'true'}
    for host in ('query1.finance.yahoo.com', 'query2.finance.yahoo.com'):
        url=f'https://{host}/v8/finance/chart/{symbol}'
        try:
            r=requests.get(url,params=params,headers=YAHOO_HEADERS,timeout=YAHOO_API_TIMEOUT); r.raise_for_status()
            chart=r.json().get('chart') or {}
            result=chart.get('result')
            if not result:
                err=(chart.get('error') or {}).get('description') or '야후 응답 없음'
                raise RuntimeError(f'{symbol}: {err}')
            result=result[0]; ts=result.get('timestamp') or []; closes=(((result.get('indicators') or {}).get('quote') or [{}])[0]).get('close') or []
            adj_arr=(((result.get('indicators') or {}).get('adjclose') or [{}])[0]).get('adjclose') or []
            rows=[]
            for i,t in enumerate(ts):
                try: close=float(closes[i])
                except (TypeError,ValueError,IndexError): continue
                if close<=0: continue
                adj=None
                try:
                    if i < len(adj_arr) and adj_arr[i] is not None:
                        av=float(adj_arr[i])
                        adj=av if av>0 else None
                except (TypeError,ValueError,IndexError): adj=None
                rows.append({'ticker':symbol,'date':pd.Timestamp(t,unit='s').strftime('%Y%m%d'),'close':close,'adjclose':adj})
            if not rows: raise RuntimeError(f'{symbol}: 유효한 종가가 없습니다.')
            return pd.DataFrame(rows).drop_duplicates('date').sort_values('date').reset_index(drop=True)
        except Exception as e:
            last_err=e
            continue
    raise last_err or RuntimeError(f'{symbol}: Yahoo 조회 실패')

def _refresh_key(force_refresh=False): return int(pd.Timestamp.now().timestamp()) if force_refresh else 0

def fetch_yahoo_day(symbol, day, force_refresh=False):
    """지정일의 하루치 행을 adjclose 포함으로 반환한다. 직전 거래일 대체는 fetch_price_day가 처리한다."""
    target=pd.Timestamp(day).strftime('%Y%m%d'); cached=cache_get_prices(symbol,'US')
    if not cached.empty and not force_refresh:
        hit=cached[cached['date'].eq(target)]
        if not hit.empty: return pd.DataFrame([{'ticker':symbol,'date':target,'close':float(hit.iloc[0]['close']),'adjclose':n(hit.iloc[0].get('adjclose')) or None}])[['ticker','date','close','adjclose']]
    start=pd.Timestamp(day)-pd.Timedelta(days=7); end=pd.Timestamp(day)+pd.Timedelta(days=2)
    df=fetch_yahoo_range(symbol,start.timestamp(),end.timestamp(),'1d',refresh_key=_refresh_key(force_refresh)); exact=df[df['date'].eq(target)]
    if exact.empty: raise RuntimeError(f'{symbol}: {day} 종가 데이터 없음(해당 날짜 휴장일 또는 Yahoo 데이터 없음)')
    cache_put_prices(symbol,exact.to_dict('records'),market='US',source='Yahoo'); return exact.iloc[[-1]][['ticker','date','close','adjclose']]

def fetch_yahoo_daily_history(symbol, day, days=430, force_refresh=False):
    end=pd.Timestamp(day); start=end-pd.Timedelta(days=days); a=start.strftime('%Y%m%d'); b=end.strftime('%Y%m%d'); cached=cache_get_prices(symbol,'US')
    cached=cached[(cached['date']>=a)&(cached['date']<=b)] if not cached.empty else cached
    if force_refresh or cached.empty or cached['date'].min()>a or cached['date'].max()<b:
        df=fetch_yahoo_range(symbol,start.timestamp(),(end+pd.Timedelta(days=2)).timestamp(),'1d',refresh_key=_refresh_key(force_refresh))
        if not df.empty: cache_put_prices(symbol,df.to_dict('records'),market='US',source='Yahoo')
        cached=cache_get_prices(symbol,'US'); cached=cached[(cached['date']>=a)&(cached['date']<=b)] if not cached.empty else cached
    return cached

def fetch_yahoo_monthly(symbol, day, force_refresh=False):
    """adjclose 컬럼을 포함한 월말 데이터를 반환한다(모드에 따라 호출부에서 선택)."""
    daily=fetch_yahoo_daily_history(symbol,day,430,force_refresh)
    if daily.empty: return daily
    x=daily.copy(); x['date_dt']=pd.to_datetime(x['date'],format='%Y%m%d',errors='coerce'); x=x.dropna(subset=['date_dt']).sort_values('date_dt'); x['month']=x['date_dt'].dt.to_period('M')
    out=x.groupby('month',as_index=False).tail(1).copy(); out['ticker']=str(symbol)
    cols=['ticker','date','close']+(['adjclose'] if 'adjclose' in out.columns else [])
    return out[cols].sort_values('date').tail(13).reset_index(drop=True)

def fetch_yahoo_daily_recent(symbol, day, days=120, force_refresh=False): return fetch_yahoo_daily_history(symbol,day,days,force_refresh)

# ---------- 시장 라우팅 (KR -> KRX/공공데이터, US -> Yahoo) ----------
def price_col(hist_df):
    """신호(SMA/모멘텀/트리거) 계산에 쓸 가격 컬럼을 고른다.
    배당재투자 기준(adjclose) 모드이고 미국 종목에 adjclose가 있으면 adjclose를 사용하고,
    그 외에는 원시 종가(close)를 사용한다. 평가액은 항상 원시 종가로 계산한다."""
    if hist_df is not None and not hist_df.empty and use_adjclose() and 'adjclose' in hist_df.columns:
        aa = hist_df['adjclose'].dropna()
        if not aa.empty and float(aa.iloc[-1]) > 0:
            return 'adjclose'
    return 'close'

def _fallback_prev_kr(source, ticker_norm, day, force_refresh):
    """KR: 지정일이 휴장일이면 최대 10영업일 전으로 거슬러 올라가 직전 거래일 종가를 찾는다.
    반환 행의 date가 실제 사용된 거래일이므로 신선도 표에 '대체' 여부가 그대로 드러난다."""
    d = pd.Timestamp(day)
    for back in range(1, 11):
        cand = d - pd.Timedelta(days=back)
        try:
            h2 = fetch_day(source, ticker_norm, cand.strftime('%Y-%m-%d'))
        except Exception:
            continue
        if h2 is not None and not h2.empty:
            hit2 = h2[h2['date'].le(cand.strftime('%Y%m%d'))]
            if not hit2.empty:
                row = hit2.iloc[[-1]]
                cache_put_prices(ticker_norm, row.to_dict('records'), market='KR', source=source + '_prev')
                return row
    return None

def fetch_price_day(market, source, ticker, day, force_refresh=False):
    """지정일(또는 휴장일 정책에 따라 직전 거래일)의 가격을 돌려준다.
    adjclose 컬럼을 포함할 수 있으며, 평가액은 호출부에서 close만 사용한다."""
    if market == 'US':
        try:
            return fetch_yahoo_day(ticker, day, force_refresh=force_refresh)
        except Exception:
            if price_policy() != 'prev':
                raise
            hist = fetch_yahoo_daily_history(ticker, day, 30, force_refresh=force_refresh)
            target = pd.Timestamp(day)
            x = hist.copy()
            x['date_dt'] = pd.to_datetime(x['date'], format='%Y%m%d', errors='coerce')
            x = x[x['date_dt'] <= target]
            if x.empty:
                raise RuntimeError(f'{ticker}: {day} 및 직전 거래일 데이터 없음(US)')
            row = x.sort_values('date_dt').iloc[[-1]]
            cols = ['ticker', 'date', 'close'] + (['adjclose'] if 'adjclose' in row.columns else [])
            return row[cols]
    ticker_norm = kr6(ticker); target = pd.Timestamp(day).strftime('%Y%m%d')
    if not force_refresh:
        cached = cache_get_prices(ticker_norm, 'KR')
        if not cached.empty:
            hit = cached[cached['date'].eq(target)]
            if not hit.empty:
                return hit[['ticker','date','close']].tail(1)
    try:
        hit = fetch_day(source, ticker_norm, day)
    except Exception:
        hit = None
    if hit is not None and not hit.empty:
        cache_put_prices(ticker_norm, hit.to_dict('records'), market='KR', source=source)
        return hit
    if price_policy() == 'prev':
        row = _fallback_prev_kr(source, ticker_norm, day, force_refresh)
        if row is not None and not row.empty:
            return row
        raise RuntimeError(f'{ticker}: {day} 및 직전 거래일 데이터 없음')
    raise RuntimeError(f'{ticker}: {day} 종가 데이터 없음(휴장일)')

def fetch_price_monthly(market, source, ticker, day, force_refresh=False):
    return (
        fetch_yahoo_monthly(ticker, day, force_refresh=force_refresh)
        if market == 'US'
        else fetch_monthly(source, ticker, day, force_refresh=force_refresh)
    )

def fetch_price_daily_recent(market, source, ticker, day, days=120, force_refresh=False):
    return (
        fetch_yahoo_daily_recent(ticker, day, days, force_refresh=force_refresh)
        if market == 'US'
        else fetch_daily_recent(source, ticker, day, days, force_refresh=force_refresh)
    )

@st.cache_data(ttl=3600, show_spinner=False)
def get_usd_krw_rate(day=None, force_refresh=False):
    """USD/KRW 환율. 휴장일 정책이 '직전 거래일 대체'면 지정일 환율이 없을 때 직전 거래일 환율을 사용한다."""
    target_day=pd.Timestamp(day if day is not None else date.today()).strftime('%Y-%m-%d'); target=pd.Timestamp(target_day).strftime('%Y%m%d'); init_db(); con=sqlite3.connect(DB_PATH)
    try: row=con.execute('SELECT rate, source FROM fx_cache WHERE date=?',(target,)).fetchone()
    finally: con.close()
    if row is not None and not force_refresh: return float(row[0])
    try:
        start=pd.Timestamp(target_day)-pd.Timedelta(days=7); end=pd.Timestamp(target_day)+pd.Timedelta(days=2); df=fetch_yahoo_range('KRW=X',start.timestamp(),end.timestamp(),'1d',refresh_key=_refresh_key(force_refresh)); exact=df[df['date'].eq(target)]
        if exact.empty:
            if price_policy() != 'prev':
                return None
            prev_df = df[df['date'] <= target]
            if prev_df.empty:
                return None
            exact = prev_df.iloc[[-1]]
        rate=float(exact.iloc[-1]['close']); actual_day=str(exact.iloc[-1]['date']); con=sqlite3.connect(DB_PATH)
        try: con.execute('INSERT OR REPLACE INTO fx_cache(date,rate,source) VALUES(?,?,?)',(actual_day,rate,'Yahoo KRW=X')); con.commit()
        finally: con.close()
        return rate
    except Exception: return None

def fetch_price_anomaly(prices):
    """월별 가격 시퀀스에서 마지막 두 값의 변동률이 ±30%를 넘으면 (True, 변동률) 반환.
    분할·배당락·입력 오류 등 의심 신호로, 경고에만 사용한다(값을 고치지 않음)."""
    vals=[n(v) for v in prices if n(v)>0]
    if len(vals)<2: return False, None
    prev=vals[-2]
    if prev<=0: return False, None
    chg=vals[-1]/prev-1
    return (abs(chg)>=0.30), chg

# -------- 가격 신선도·출처 (설정/대시보드/리밸런싱에서 표시) --------
def cache_latest_info(ticker, market='KR'):
    """가격 캐시에서 이 종목의 가장 최근 (거래일, 출처)를 반환한다."""
    try:
        market, ticker_norm = _cache_market_ticker(market, ticker)
        init_db(); con=sqlite3.connect(DB_PATH)
        try:
            row=con.execute('SELECT date, source FROM price_cache WHERE market=? AND ticker=? ORDER BY date DESC LIMIT 1',(market,ticker_norm)).fetchone()
        finally:
            con.close()
        if not row: return None, None
        d=str(row[0])
        return (f'{d[:4]}-{d[4:6]}-{d[6:]}', row[1] or '')
    except Exception:
        return None, None

def cache_fx_latest():
    try:
        init_db(); con=sqlite3.connect(DB_PATH)
        try:
            row=con.execute('SELECT date, rate, source FROM fx_cache ORDER BY date DESC LIMIT 1').fetchone()
        finally:
            con.close()
        if not row: return None, None, None
        d=str(row[0]); return (f'{d[:4]}-{d[4:6]}-{d[6:]}', float(row[1]), row[2] or '')
    except Exception:
        return None, None, None

def fetch_yahoo_signal_drawdown(symbol, day, lookback_trading_days=120, force_refresh=False):
    """트리거용 고점대비 하락률을 계산한다.

    스냅샷 종가와 달리 트리거는 기준일이 휴장일이어도 기준일 이전 마지막
    거래일을 현재값으로 사용한다. 최근 N개 거래일의 최고 종가 대비 하락률이다.
    """
    target = pd.Timestamp(day)
    hist = fetch_yahoo_daily_history(symbol, day, 550, force_refresh=force_refresh)
    if hist.empty:
        raise RuntimeError(f'{symbol}(트리거): 최근 거래일 가격 데이터 없음')
    x = hist.copy()
    x['date_dt'] = pd.to_datetime(x['date'], format='%Y%m%d', errors='coerce')
    use_adj = use_adjclose() and 'adjclose' in x.columns
    col = 'adjclose' if use_adj else 'close'
    x[col] = pd.to_numeric(x[col], errors='coerce')
    x = x.dropna(subset=['date_dt', col]).sort_values('date_dt')
    x = x[x['date_dt'] <= target].tail(int(lookback_trading_days))
    if x.empty:
        raise RuntimeError(f'{symbol}(트리거): 기준일 이전 거래일 데이터 없음')
    if len(x) < min(20, int(lookback_trading_days)):
        raise RuntimeError(f'{symbol}(트리거): 최근 거래일 데이터가 {len(x)}개뿐입니다.')
    return drawdown_from_peak(x[col].tolist())

def drawdown_from_peak(closes):
    closes = [c for c in closes if n(c) > 0]
    if not closes: return None
    peak = max(closes); cur = closes[-1]
    if peak <= 0: return None
    return cur / peak - 1

# ---------- calculations ----------
def calc_prices(a):
    prices = safe_prices(a.get('prices', []), [a.get('close', 0)] if n(a.get('close')) else [])
    close = n(a.get('close')) or (prices[-1] if prices else 0)
    # sma/mom을 0으로 반환하면 "0은 falsy"라 'sma and close > sma' 같은 검사가 늘 False가 되어
    # 데이터 부족 상황이 "SMA 하회"로 둔갑하는 버그가 생긴다. 계산 불가 시 None을 반환해 명확히 구분한다.
    sma = sum(prices[-10:]) / 10 if len(prices) >= 10 else None
    mom = (prices[-1] / prices[-13] - 1) if len(prices) >= 13 and prices[-13] else None
    return close, sma, mom

def asset_value(a, fx_rate=None):
    shares=n(a.get('shares'))
    if str(a.get('ticker'))=='CASH': return shares
    value=shares*n(a.get('close'))
    if a.get('market')=='US':
        fx=fx_rate if fx_rate is not None else get_usd_krw_rate()
        return value*fx if fx else 0.0
    return value

def usd_krw_rate_missing(assets_df, day=None):
    has_us=(assets_df['market']=='US').any() if not assets_df.empty else False
    return has_us and not get_usd_krw_rate(day)

def portfolio_perf(rows):
    """포트폴리오 시계열에서 CAGR·MDD·연환산 변동성·샤프를 계산한다.
    과거 반환형 (cagr, mdd)과 호환되도록 튜플 앞 2개는 유지한다. 계산 불가 항목은 None."""
    x = sorted([{'date': str(r['date']), 'value': n(r['value'])} for r in rows if n(r.get('value')) > 0], key=lambda z: z['date'])
    if len(x) < 2: return None
    if n(x[0]['value']) <= 0: return None  # 0원 시작이면 CAGR이 무한대/NaN이 되는 것 방지
    days = max(1, (pd.Timestamp(x[-1]['date']) - pd.Timestamp(x[0]['date'])).days)
    years = max(days / 365.0, 1e-9)
    cagr = (n(x[-1]['value']) / n(x[0]['value'])) ** (1 / years) - 1
    peak = 0.0; mdd = 0.0
    for r in x:
        peak = max(peak, n(r['value'])); mdd = min(mdd, n(r['value']) / peak - 1 if peak > 0 else 0.0)
    rets = []
    for a, b in zip(x[:-1], x[1:]):
        pa, pb = n(a['value']), n(b['value'])
        if pa > 0:
            rets.append(pb / pa - 1)
    vol = None; sharpe = None
    if len(rets) >= 2:
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
        sd = var ** 0.5
        if sd > 0:
            vol = sd * (len(rets) / years) ** 0.5
            sharpe = (mean_r * len(rets) / years - 0.0) / vol if vol else None
    return cagr, mdd, vol, sharpe

def calc_xirr(equity, cashflows):
    """XIRR(금액가중 수익률). 입출금 시점과 최종 평가액으로 내부수익률을 구한다.
    해가 여러 개일 수 있는 NPV 함수 특성을 고려해 구간을 넓혀가며 탐색하고,
    해가 없으면(전부 출금·극단적 수익) 의미 없는 값 대신 None을 반환한다."""
    if not equity or not cashflows: return None
    last = sorted(equity, key=lambda x: x['date'])[-1]
    last_d = last['date']
    # 마지막 저장일과 같은 날짜의 입출금은 XIRR 계산에서 제외한다.
    # 평가액(마지막 저장일 종가 기준)에 이미 반영된 것으로 간주해 이중계상을 막는다.
    flows = [{'date': x['date'], 'amount': -n(x['amount'])} for x in cashflows if n(x.get('amount')) != 0 and x['date'] < last_d] + [{'date': last_d, 'amount': n(last['value'])}]
    flows.sort(key=lambda x: x['date']); d0 = pd.Timestamp(flows[0]['date'])
    if not flows or len(flows) < 2: return None
    def npv(r): return sum(x['amount'] / (1 + r) ** ((pd.Timestamp(x['date']) - d0).days / 365) for x in flows)
    lo, hi = -0.9999, 10
    flo, fhi = npv(lo), npv(hi)
    if (flo > 0) == (fhi > 0) and flo != 0 and fhi != 0:
        # 고정 브래킷에 해가 없으면 아래 구간을 늘려 다시 시도
        lo2, hi2 = -0.999999, 100
        flo2, fhi2 = npv(lo2), npv(hi2)
        if (flo2 > 0) == (fhi2 > 0) and flo2 != 0 and fhi2 != 0:
            return None
        lo, hi, flo, fhi = lo2, hi2, flo2, fhi2
    for _ in range(160):
        mid = (lo + hi) / 2
        try:
            v = npv(mid)
        except (OverflowError, ZeroDivisionError):
            break
        if v > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def calc_twr(equity, cashflows):
    """TWR(시간가중 수익률) — Modified Dietz 방식으로 입출금(외부자금) 영향을 제거한 '투자 실력' 지표.
    입출금 시점에 계좌를 나눠 각 구간 수익률을 기하연결한다. 데이터가 부족하면 None."""
    equity = sorted([{'date': str(r['date']), 'value': n(r['value'])} for r in equity if n(r.get('value')) > 0], key=lambda z: z['date'])
    if len(equity) < 2: return None
    cf = sorted([{'date': str(x['date']), 'amount': n(x.get('amount'))} for x in cashflows], key=lambda z: z['date'])
    seg_rets = []
    for i in range(len(equity) - 1):
        d0, d1 = pd.Timestamp(equity[i]['date']), pd.Timestamp(equity[i + 1]['date'])
        v0, v1 = n(equity[i]['value']), n(equity[i + 1]['value'])
        flows_in = [(d0, n(f['amount'])) for f in cf if d0 < pd.Timestamp(f['date']) <= d1]
        if v0 <= 0: continue
        try:
            fv = sum(a * max(0.0, 1 - (d1 - d).days / max(1, (d1 - d0).days)) for d, a in flows_in)
        except ZeroDivisionError:
            fv = 0.0
        ret = (v1 - v0 - sum(a for _, a in flows_in)) / (v0 + fv) if (v0 + fv) != 0 else None
        if ret is not None: seg_rets.append(ret)
    if not seg_rets: return None
    prod = 1.0
    for r in seg_rets: prod *= (1 + r)
    return prod - 1

def xirr_attr_label():
    return '동일 입출금을 벤치마크에 넣었다면? (공정 비교용 XIRR)'

def mdd_details(rows):
    """시계열에서 (최대낙폭, 최대낙폭 기간(일), 회복 기간(일))을 반환한다. 데이터 부족 시 (None,None,None)."""
    x = sorted([{'date': str(r['date']), 'value': n(r['value'])} for r in rows if n(r.get('value')) > 0], key=lambda z: z['date'])
    if len(x) < 2:
        return None, None, None
    peak = 0.0; peak_date = None; max_dd = 0.0; trough = None
    for r in x:
        v = n(r['value']); d = str(r['date'])
        if v > peak:
            peak = v; peak_date = d
        dd = v / peak - 1 if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd; trough = d
    dd_len = None
    if max_dd < 0 and peak_date and trough:
        dd_len = max(0, (pd.Timestamp(trough) - pd.Timestamp(peak_date)).days)
    rec_len = None
    if max_dd < 0 and trough:
        t = pd.Timestamp(trough)
        for r in sorted(x, key=lambda z: z['date']):
            if str(r['date']) <= trough:
                continue
            if n(r['value']) >= peak:
                rec_len = max(0, (pd.Timestamp(r['date']) - t).days)
                break
    return max_dd, dd_len, rec_len

def sortino_ratio(rows):
    """하방편차 기준 연환산 소르티노 비율(무위험 0 가정). 데이터 부족 시 None."""
    x = sorted([{'date': str(r['date']), 'value': n(r['value'])} for r in rows if n(r.get('value')) > 0], key=lambda z: z['date'])
    if len(x) < 2:
        return None
    rets = []
    for a, b in zip(x[:-1], x[1:]):
        pa = n(a['value'])
        if pa > 0:
            rets.append(n(b['value']) / pa - 1)
    if len(rets) < 2:
        return None
    years = max(1, (pd.Timestamp(x[-1]['date']) - pd.Timestamp(x[0]['date'])).days) / 365.0
    mean = sum(rets) / len(rets)
    down = [r for r in rets if r < 0] or [0.0]
    dd = (sum((r - mean) ** 2 for r in down) / len(down)) ** 0.5
    if dd == 0:
        return None
    return (mean * len(rets) / years) / dd

def beta_alpha(series_a, series_b):
    """같은 날짜 쌍의 수익률 회귀로 (베타, 구간 알파)를 계산한다. 데이터 부족 시 (None,None)."""
    pairs = {}
    for r in series_a:
        pairs.setdefault(str(r['date']), {})['a'] = n(r['value'])
    for r in series_b:
        pairs.setdefault(str(r['date']), {})['b'] = n(r['value'])
    dates = sorted(k for k, v in pairs.items() if 'a' in v and 'b' in v and n(v['a']) > 0 and n(v['b']) > 0)
    if len(dates) < 3:
        return None, None
    ra = []; rb = []
    for i in range(1, len(dates)):
        pa = n(pairs[dates[i-1]]['a']); pb = n(pairs[dates[i]]['a'])
        mb = n(pairs[dates[i-1]]['b']); nb = n(pairs[dates[i]]['b'])
        if pa > 0 and mb > 0:
            ra.append(pb / pa - 1); rb.append(nb / mb - 1)
    if len(ra) < 3:
        return None, None
    mra = sum(ra) / len(ra); mrb = sum(rb) / len(rb)
    cov = sum((ra[i] - mra) * (rb[i] - mrb) for i in range(len(ra))) / len(ra)
    var = sum((r - mrb) ** 2 for r in rb) / len(rb)
    if var == 0:
        return None, None
    beta = cov / var
    alpha = (mra - beta * mrb) * len(ra)
    return beta, alpha

# ---------- 벤치마크 ----------
BENCH_SYMBOLS = {'QQQ': 'QQQ', 'SPY': 'SPY', 'KOSPI200': '^KS200'}

def get_bench_symbols():
    """기본 벤치마크 + 사용자 정의 벤치마크(설정에서 추가) 병합."""
    merged = dict(BENCH_SYMBOLS)
    try:
        c = get_state('custom_benchmarks')
        if isinstance(c, dict):
            for k, v in c.items():
                k = str(k).strip(); v = str(v).strip()
                if k and v:
                    merged[k] = v
    except Exception:
        pass
    return merged

def bench_value_before(bench, dt):
    """벤치마크 시계열에서 날짜 dt 이전(<=) 가장 가까운 값을 반환."""
    dt = pd.Timestamp(dt)
    best = None
    for dd, vv in bench:
        if pd.Timestamp(dd) <= dt:
            best = vv
        else:
            break
    return best

def benchmark_attributed_xirr(bench_recs, cashflows, anchor_day):
    """'이 돈을 벤치마크에 넣었다면' 시나리오의 XIRR.
    입출금 스트림을 벤치마크 가격으로 환산한 최종 평가액을 만들고,
    원본 입출금과 함께 XIRR을 계산한다(공정 비교용). 데이터 부족 시 None."""
    if not bench_recs or not cashflows:
        return None
    bench = sorted(bench_recs, key=lambda x: x[0])
    if not bench:
        return None
    b_end = n(bench[-1][1])
    b_start = n(bench[0][1])
    if b_end <= 0 or b_start <= 0:
        return None
    total = 0.0
    flow_dates = []
    for f in sorted(cashflows, key=lambda x: x['date']):
        amt = n(f.get('amount'))
        if amt == 0:
            continue
        flow_dates.append(f['date'])
        bv = bench_value_before(bench, f['date'])
        if bv and n(bv) > 0:
            total += amt * (b_end / n(bv))
        else:
            total += amt * (b_end / b_start)
    if not flow_dates or total <= 0:
        return None
    end_day = max(flow_dates + [anchor_day, bench[-1][0]])
    eq = [{'date': min(flow_dates), 'value': 1.0}, {'date': end_day, 'value': total}]
    return calc_xirr(eq, cashflows)

def w(x): return f'{n(x):,.0f}원'
def p(x): return f'{x * 100:.2f}%'
def num0(x): return f'{n(x):,.0f}'

def toast(msg):
    """구버전 Streamlit에는 없는 st.toast를 안전하게 감싼다."""
    try:
        st.toast(msg)
    except Exception:
        pass

# ---------- 전략 레지스트리 ----------
def get_strategies():
    try:
        s = get_state('strategies')
        s = s if s else DEFAULT_STRATEGIES
    except Exception:
        s = DEFAULT_STRATEGIES
    for c in s:
        if 'active' not in c: c['active'] = True  # 구버전 데이터 호환
        if 'annual_limit' not in c: c['annual_limit'] = 0.0
    return s

def strategy_codes(active_only=False):
    cfgs = get_strategies()
    if active_only: cfgs = [c for c in cfgs if c.get('active', True)]
    return [c['code'] for c in cfgs]

def ordered_strategy_codes(cfgs=None, active_only=True):
    """Action Plan/대시보드에 LAA→GSM→ISA→SSO→EM 우선순위, 그 다음 사용자 추가 전략 순으로."""
    cfgs = cfgs if cfgs is not None else get_strategies()
    if active_only: cfgs = [c for c in cfgs if c.get('active', True)]
    codes = [c['code'] for c in cfgs]
    known = [c for c in STRATEGY_DISPLAY_ORDER if c in codes]
    rest = [c for c in codes if c not in STRATEGY_DISPLAY_ORDER]
    return known + rest

def delete_strategy(code, assets_df):
    cfgs = [c for c in get_strategies() if c['code'] != code]
    put_state('strategies', cfgs)
    assets2 = assets_df[~assets_df['strategy'].eq(code)].copy()
    put_state('assets', assets2.to_dict('records'))
    return assets2

def rename_strategy(old_code, new_code, assets_df):
    new_code = new_code.strip().upper()
    if not new_code or new_code == old_code: return assets_df, False, '변경할 이름을 입력하세요.'
    if old_code in KNOWN_STRATEGIES:
        return assets_df, False, f'{old_code}는 전용 리밸런싱 규칙에 코드가 고정되어 있어 이름을 바꿀 수 없습니다. 계좌 별명만 바꿔주세요.'
    codes = strategy_codes()
    if new_code in codes: return assets_df, False, '이미 존재하는 전략 코드입니다.'
    cfgs = get_strategies()
    for c in cfgs:
        if c['code'] == old_code: c['code'] = new_code
    put_state('strategies', cfgs)
    assets2 = assets_df.copy()
    assets2.loc[assets2['strategy'].eq(old_code), 'strategy'] = new_code
    put_state('assets', assets2.to_dict('records'))
    return assets2, True, ''

def compute_portfolio_snapshot(assets_df, active_only=True):
    """전략별 현재 보유금액(자산+현금 행 포함)을 합산한 스냅샷. 현금도 그냥 category='현금'인 자산 행이라 별도 처리 불필요."""
    cfgs = get_strategies()
    if active_only: cfgs = [c for c in cfgs if c.get('active', True)]
    rows = []; grand = 0.0
    for cfg in cfgs:
        code = cfg['code']; sub = assets_df[assets_df['strategy'].eq(code)]
        total = sub.apply(asset_value, axis=1).sum() if not sub.empty else 0.0
        grand += total
        for _, r in sub.iterrows():
            val = asset_value(r)
            rows.append({
                '전략': code, '계좌': cfg.get('account', code), '티커': r['ticker'], 'ETF': r['name'] or r['ticker'] or '-',
                '분류': r.get('category') or '기타', '현재금액': val,
                '현재비중': (val / total * 100 if total > 0 else 0.0), '목표비중': n(r['target_pct']),
                '종가': n(r['close']), '보유수량': n(r['shares']),
            })
    return grand, pd.DataFrame(rows), cfgs

def compute_category_breakdown(assets_df, active_only=True):
    if assets_df.empty: return pd.DataFrame(columns=['분류', '금액', '비중'])
    if active_only:
        active_codes = [c['code'] for c in get_strategies() if c.get('active', True)]
        assets_df = assets_df[assets_df['strategy'].isin(active_codes)]
    if assets_df.empty: return pd.DataFrame(columns=['분류', '금액', '비중'])
    tmp = pd.DataFrame({'분류': assets_df['category'].apply(lambda c: c or '기타'), '금액': assets_df.apply(asset_value, axis=1)})
    out = tmp.groupby('분류')['금액'].sum().reset_index().sort_values('금액', ascending=False)
    total = out['금액'].sum()
    out['비중'] = out['금액'] / total * 100 if total > 0 else 0.0
    return out

# 백업/복원에 포함해야 하는 모든 kv 키. 새 상태를 추가할 때마다 여기 한 곳만 늘리면
# 백업 JSON이 저절로 최신 스키마를 따라가서, "백업엔 있는데 복원엔 빠졌다" 같은 실수를 막는다.
ALL_KV_KEYS = ['assets', 'history', 'equity', 'cashflows', 'benchmarks', 'strategies', 'category_targets', 'executions', 'price_policy', 'price_mode', 'custom_benchmarks']
BACKUP_SCHEMA_VERSION = 3
PRICE_FIELDS_EXCLUDED_FROM_BACKUP = {'close', 'prices', 'last_fetch_date', 'price_source'}

def strip_asset_price_data(records):
    """JSON 백업/복원에서는 일자별 시장가격을 완전히 분리한다.
    보유수량·전략·종목 구성·목표비중 등 포트폴리오 설정은 그대로 보존한다.
    """
    if not isinstance(records, list):
        return records
    clean=[]
    for row in records:
        if not isinstance(row, dict):
            continue
        clean.append({k:v for k,v in row.items() if k not in PRICE_FIELDS_EXCLUDED_FROM_BACKUP})
    return clean

def export_backup_dict():
    data = {k: get_state(k) for k in ALL_KV_KEYS}
    data['assets'] = strip_asset_price_data(data.get('assets', []))
    data['_backup_meta'] = {
        'schema_version': BACKUP_SCHEMA_VERSION,
        'asset_price_data_included': False,
        'excluded_asset_fields': sorted(PRICE_FIELDS_EXCLUDED_FROM_BACKUP),
    }
    return data

def write_auto_backup():
    """로컬 실행 중 DB 파일이 손상되거나 실수로 초기화됐을 때를 대비한 보조 안전망.
    매달 스냅샷을 저장할 때마다 타임스탬프가 찍힌 백업 파일을 별도로 남긴다.
    (단, 클라우드 배포처럼 컨테이너 자체가 재배포마다 초기화되는 환경에서는 이 파일도 함께
    사라지므로 근본적인 해결책은 아니고, '코드 업데이트 전 백업 다운로드 → 이후 복원' 절차가 필수다.)"""
    try:
        backup_dir = Path.home() / '.asset_allocation_app' / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        data = export_backup_dict()
        path = backup_dir / f'backup-{date.today().isoformat()}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        files = sorted(backup_dir.glob('backup-*.json'))
        for old in files[:-30]:
            try: old.unlink()
            except Exception: pass
    except Exception:
        pass

def save_history_snapshot(assets_df, run_date, plan_text=None):
    """전체 전략의 구성·총액·분류별 총액을 한 번에 히스토리+총자산 시계열에 저장한다."""
    grand, snap_df, _ = compute_portfolio_snapshot(assets_df)
    cat_df = compute_category_breakdown(assets_df)
    ds = run_date.isoformat()
    prev_rec = next((x for x in get_state('history') if x.get('date') == ds), None)
    saved_plan = plan_text if plan_text is not None else (prev_rec.get('plan') if prev_rec else None)
    h = [x for x in get_state('history') if x.get('date') != ds]  # 같은 날짜 재저장 시 덮어쓰기
    h.insert(0, {
        'date': ds,
        'total': grand,
        'by_strategy': snap_df.groupby('전략')['현재금액'].sum().to_dict() if not snap_df.empty else {},
        'by_category': cat_df.set_index('분류')['금액'].to_dict() if not cat_df.empty else {},
        'composition': snap_df.to_dict('records') if not snap_df.empty else [],
        'plan': saved_plan,
        'saved_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'),
    })
    put_state('history', h)
    e = [x for x in get_state('equity') if x['date'] != ds]; e.append({'date': ds, 'value': grand})
    put_state('equity', e)
    try:
        _backfill_benchmarks([ds])
    except Exception:
        pass  # 벤치마크 백필 실패는 스냅샷 저장을 막지 않는다
    write_auto_backup()
    return grand

def _backfill_benchmarks(dates):
    """히스토리에 없는 날짜의 벤치마크만 자동으로 채운다(캐시 우선, 실패는 조용히)."""
    existing = get_state('benchmarks')
    added = 0
    for dt in dates:
        for name, sym in get_bench_symbols().items():
            if any(x['name'] == name and x['date'] == dt for x in existing):
                continue
            try:
                row = fetch_yahoo_day(sym, dt)
                rec = {'name': name, 'date': dt, 'value': float(row.iloc[-1]['close'])}
                if 'adjclose' in row.columns and n(row.iloc[-1].get('adjclose')) > 0:
                    rec['adjclose'] = float(n(row.iloc[-1]['adjclose']))
                existing.append(rec); added += 1
            except Exception:
                continue
    if added:
        put_state('benchmarks', existing)

# 구글 스프레드시트에 매달 정리해 두는 순서. 한 줄(row)로 복사-붙여넣기 하기 위한 순서라
# 실제로 없는 분류(예: '기타')는 만들지 않는 한 나타나지 않는다.
CATEGORY_ROW_ORDER = ['현금', '금', '선진국 주식', '신흥국 주식', '선진국 채권', '신흥국 채권']

def build_category_row(date_str, by_category):
    values = [date_str] + [f'{n(by_category.get(c, 0)):.0f}' for c in CATEGORY_ROW_ORDER]
    leftover = {k: v for k, v in (by_category or {}).items() if k not in CATEGORY_ROW_ORDER and n(v) != 0}
    return '\t'.join(values), leftover

def get_category_targets():
    try:
        t = get_state('category_targets')
        return {**{c: 0.0 for c in CATEGORY_OPTIONS}, **t}
    except Exception:
        return {c: 0.0 for c in CATEGORY_OPTIONS}

def last_snapshot_info():
    """가장 최근 저장된 히스토리 날짜와 오늘까지 경과일수."""
    h = get_state('history')
    if not h: return None
    last_date = sorted(h, key=lambda x: x['date'])[-1]['date']
    days = (date.today() - pd.Timestamp(last_date).date()).days
    return last_date, days

def ytd_contribution(strategy_code, year=None):
    """올해(또는 지정 연도) 해당 전략에 태그된 입금 합계 (출금은 차감)."""
    year = year or date.today().year
    cf = get_state('cashflows')
    total = 0.0
    for c in cf:
        if c.get('strategy') != strategy_code: continue
        try:
            if pd.Timestamp(c['date']).year != year: continue
        except Exception:
            continue
        total += n(c.get('amount'))
    return total

def compute_mom_delta():
    """가장 최근 두 번의 히스토리 저장을 비교해 총자산/전략별/분류별 증감을 계산."""
    h = get_state('history')
    if len(h) < 2: return None
    hs = sorted(h, key=lambda x: x['date'])
    cur, prev = hs[-1], hs[-2]
    def diff_rows(a, b):
        keys = sorted(set(a.keys()) | set(b.keys()))
        return [{'항목': k, '이번': n(a.get(k, 0)), '저번': n(b.get(k, 0)), '증감': n(a.get(k, 0)) - n(b.get(k, 0))} for k in keys]
    return {
        'cur_date': cur['date'], 'prev_date': prev['date'],
        'total_cur': n(cur.get('total')), 'total_prev': n(prev.get('total')),
        'total_delta': n(cur.get('total')) - n(prev.get('total')),
        'by_strategy': diff_rows(cur.get('by_strategy') or {}, prev.get('by_strategy') or {}),
        'by_category': diff_rows(cur.get('by_category') or {}, prev.get('by_category') or {}),
    }

def render_diff_table(rows):
    if not rows: return
    df = pd.DataFrame(rows)
    show = df.copy()
    for c in ['이번', '저번', '증감']: show[c] = show[c].map(w)
    st.dataframe(show, use_container_width=True, hide_index=True)

def ensure_cash_rows(assets_df):
    """구버전 DB(계좌별 현금을 별도 kv로 관리하던 시절) 호환: 전략에 CASH 행이 없으면 만들어준다."""
    cfgs = get_strategies()
    try: legacy_cash = get_state('account_cash')
    except Exception: legacy_cash = {}
    changed = False
    for cfg in cfgs:
        code = cfg['code']; sub = assets_df[assets_df['strategy'].eq(code)]
        if not sub.empty and (sub['ticker'] == 'CASH').any(): continue
        remain = max(0.0, 100.0 - pd.to_numeric(sub['target_pct'], errors='coerce').fillna(0).sum()) if not sub.empty else 100.0
        new_row = {'id': str(len(assets_df) + 1), 'strategy': code, 'ticker': 'CASH', 'name': '현금', 'market': 'KR',
                   'role': '대기현금', 'target_pct': remain, 'shares': n(legacy_cash.get(code, 0)), 'close': 1.0,
                   'prices': [], 'signal_ticker': 'CASH', 'category': '현금'}
        assets_df = pd.concat([assets_df, pd.DataFrame([new_row])], ignore_index=True); changed = True
    if changed:
        assets_df = clean_records(assets_df)
        st.session_state.assets = assets_df; put_state('assets', assets_df.to_dict('records'))
    return assets_df

# ---------- app ----------
if 'assets' not in st.session_state: st.session_state.assets = clean_records(pd.DataFrame(get_state('assets')))
assets = ensure_cash_rows(clean_records(st.session_state.assets))

with st.sidebar:
    st.markdown('## 📊 자산배분 도우미')
    page = st.radio('메뉴', ['🏠 대시보드', '🔄 리밸런싱 실행', '📈 히스토리', '⚖️ 전략 비교', '⚙️ 설정'])
    st.divider()
    device_mode = st.radio('화면 모드', ['자동(반응형)', '💻 PC', '📱 모바일'], index=0, key='device_mode', horizontal=True)
    dark_mode = st.toggle('🌙 다크모드', value=False, key='dark_mode', help='눈이 편한 어두운 테마로 전환합니다.')
    st.caption('자동주문 없음 · 지정일 실행만 저장')

# '자동' 모드도 CSS 미디어쿼리로 실제 폰 브라우저 폭에서는 반응형으로 줄어든다.
# '📱 모바일'을 명시적으로 고르면 PC 화면에서도 강제로 모바일 레이아웃(카드형 목록 등)을 미리 볼 수 있다.
MOBILE = device_mode == '📱 모바일'
st.markdown("""
<style>
:root{
  --bg:#f6f7f9; --surface:#ffffff; --surface-2:#f0f2f5; --border:#e5e7eb;
  --text:#111827; --muted:#6b7280; --primary:#2563eb; --primary-soft:#eff6ff;
  --success:#16a34a; --success-soft:#f0fdf4; --danger:#dc2626; --danger-soft:#fef2f2;
  --warning:#d97706; --warning-soft:#fffbeb; --radius:16px;
}
.stApp{background:var(--bg); color:var(--text);}
.block-container{max-width:1220px !important; padding-top:1.2rem !important; padding-bottom:3rem !important;}
section[data-testid="stSidebar"]{background:#111827 !important; border-right:1px solid #1f2937;}
section[data-testid="stSidebar"] *{color:#e5e7eb !important;}
section[data-testid="stSidebar"] .stRadio label{padding:.28rem 0;}
h1,h2,h3,h4{color:var(--text) !important; letter-spacing:-.025em;}
h1{font-size:2rem !important; font-weight:800 !important;}
h2{font-size:1.45rem !important; font-weight:750 !important;}
h3{font-size:1.12rem !important; font-weight:700 !important;}
[data-testid="stMetric"]{background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:1rem 1.1rem; box-shadow:0 1px 2px rgba(0,0,0,.03);}
[data-testid="stMetricLabel"]{color:var(--muted) !important; font-size:.82rem !important;}
[data-testid="stMetricValue"]{color:var(--text) !important; font-weight:800 !important;}
.stButton>button,.stDownloadButton>button{border-radius:10px !important; min-height:2.65rem; font-weight:650; border:1px solid var(--border); background:var(--surface); color:var(--text); transition:.15s ease;}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:#cbd5e1; box-shadow:0 3px 10px rgba(15,23,42,.08);}
.stButton button[kind="primary"]{background:var(--primary) !important; border-color:var(--primary) !important; color:white !important;}
.stTabs [aria-selected="true"]{color:var(--primary) !important; border-bottom-color:var(--primary) !important;}
div[data-testid="stExpander"]{background:var(--surface); border:1px solid var(--border); border-radius:14px; overflow:hidden;}
div[data-testid="stDataFrame"], div[data-testid="stTable"]{border:1px solid var(--border); border-radius:12px; overflow:hidden;}
div[data-baseweb="select"]>div, div[data-baseweb="input"]>div, textarea{border-radius:10px !important; border-color:var(--border) !important; background:var(--surface) !important;}
hr{border-color:var(--border) !important;}
.app-hero{background:linear-gradient(135deg,#111827 0%,#1f2937 55%,#2563eb 140%); color:white; border-radius:22px; padding:24px 26px; margin:0 0 20px 0; box-shadow:0 10px 30px rgba(15,23,42,.10);}
.app-hero .eyebrow{font-size:.75rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; opacity:.68;}
.app-hero .title{font-size:1.85rem; font-weight:800; letter-spacing:-.035em; margin:.25rem 0 .35rem;}
.app-hero .sub{font-size:.9rem; color:#cbd5e1;}
.ui-card{background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:16px 18px; box-shadow:0 1px 2px rgba(0,0,0,.03);}
.status-ok{background:var(--success-soft); border-color:#bbf7d0;}
.status-warn{background:var(--warning-soft); border-color:#fde68a;}
.status-bad{background:var(--danger-soft); border-color:#fecaca;}
@media(max-width:640px){
 .block-container{padding:.7rem .65rem 2.5rem !important;}
 h1{font-size:1.5rem !important;} h2{font-size:1.28rem !important;}
 [data-testid="stMetric"]{padding:.72rem .75rem;}
 [data-testid="stMetricValue"]{font-size:1.2rem !important;}
 .app-hero{padding:18px 17px; border-radius:16px;}
 .app-hero .title{font-size:1.35rem;}
 .stButton>button,.stDownloadButton>button{width:100%;}
}
</style>
""", unsafe_allow_html=True)
if MOBILE:
    st.markdown("""
    <style>
    div[data-testid="stMetricValue"]{font-size:1.3rem !important;}
    .stButton button{font-size:1rem !important;padding:0.55rem 0.9rem !important;width:100%;}
    </style>
    """, unsafe_allow_html=True)

DARK = dark_mode
if DARK:
    st.markdown("""<style>
    :root{--sage:#A9C08F;--sage-dark:#B7CF9E;--sage-tint:rgba(169,192,143,0.16);--terracotta:#D99A7C;--terracotta-dark:#E0A88C;--terracotta-tint:rgba(217,154,124,0.16);--olive:#C9C9A8;--olive-dark:#D6D6B8;--beige:#1F2023;--beige-deep:#2A2B30;--ink:#E8E6DF;}
    .stApp{background-color:var(--beige);}
    div[data-testid="stSidebar"]{background-color:#26272B !important;}
    div[data-testid="stMetric"],div[data-testid="stMetricLabel"],div[data-testid="stMetricValue"]{background-color:var(--beige-deep) !important;color:var(--ink) !important;}
    div[data-testid="stMetricValue"]{color:var(--olive-dark) !important;}
    div[data-testid="stExpander"],div[data-testid="stVerticalBlockBorderWrapper"]{background-color:var(--beige-deep) !important;border-color:#3A3B41 !important;}
    .stButton button:not([kind="primary"]){background-color:var(--beige-deep) !important;color:var(--ink) !important;border-color:#3A3B41 !important;}
    div[data-testid="stHeader"]{background:transparent !important;}
    input,textarea,div[data-baseweb="select"]>div{background-color:var(--beige-deep) !important;color:var(--ink) !important;}
    .stMarkdown p, .stMarkdown li{color:var(--ink) !important;}
    </style>""", unsafe_allow_html=True)

def mobile_card(title, lines, tone=None):
    """넓은 표 대신 쓰는 세로 카드 한 장. tone에 따라 세이지그린(양호)/테라코타(주의) 테두리."""
    border = {'pos': 'var(--sage-dark)', 'neg': 'var(--terracotta-dark)'}.get(tone, 'var(--beige-deep)')
    tint = {'pos': 'var(--sage-tint)', 'neg': 'var(--terracotta-tint)'}.get(tone, 'rgba(122,110,80,0.05)')
    body = '<br>'.join(lines)
    st.markdown(
        f'<div style="border-left:4px solid {border};background:{tint};'
        f'border-radius:6px;padding:10px 12px;margin-bottom:8px;">'
        f'<div style="font-weight:700;margin-bottom:4px;color:var(--olive-dark);">{title}</div>'
        f'<div style="font-size:0.88rem;line-height:1.6;color:var(--ink);">{body}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown(f'''<div class="app-hero"><div class="eyebrow">PORTFOLIO REBALANCING</div><div class="title">자산배분 리밸런싱</div><div class="sub">지정일 종가 · 10개월 SMA · 12개월 모멘텀 · CAGR / MDD / IRR · v{APP_VERSION}</div></div>''', unsafe_allow_html=True)


def strategy_rebalance_status(plan_group):
    """전략별 리밸런싱 필요도를 계산한다. 구버전/빈 계획표에도 안전하게 동작한다."""
    if plan_group is None or plan_group.empty:
        return '⚪ 데이터 없음', '계획 데이터가 없습니다.'
    required = {'매매액(+매수/-매도)', '현재금액', '비고'}
    missing = required - set(plan_group.columns)
    if missing:
        return '⚠️ 데이터 확인', f"계획표에 필요한 열이 없습니다: {', '.join(sorted(missing))}"
    trades = pd.to_numeric(plan_group['매매액(+매수/-매도)'], errors='coerce').fillna(0)
    current = pd.to_numeric(plan_group['현재금액'], errors='coerce').fillna(0)
    if not trades.notna().any() or not current.notna().any():
        return '⚠️ 데이터 확인', '계획 금액을 계산할 수 없습니다.'
    total_cur = float(current.sum())
    max_trade = float(trades.abs().max()) if len(trades) else 0.0
    ratio = max_trade / float(total_cur) if total_cur > 0 else 0.0
    notes = ' '.join(plan_group['비고'].fillna('').astype(str).tolist())
    if '데이터부족' in notes or '데이터 없음' in notes:
        return '⚠️ 데이터 확인', '가격/SMA 데이터가 부족합니다.'
    if ratio >= 0.10:
        return '🔴 리밸런싱 필요', f'최대 조정액이 현재 자산의 {ratio:.1%}입니다.'
    if ratio >= 0.03:
        return '🟡 점검 권장', f'최대 조정액이 현재 자산의 {ratio:.1%}입니다.'
    return '🟢 정상', '목표비중과의 괴리가 크지 않습니다.'


def render_target_weight_bar(current_pct, target_pct, height=22):
    """목표까지는 초록, 목표 미달분은 파랑, 초과분은 빨강으로 표시하는 비중 막대."""
    cur = max(0.0, float(current_pct or 0))
    tgt = max(0.0, float(target_pct or 0))
    scale = max(100.0, cur, tgt, 1.0)
    if cur <= tgt:
        green = cur / scale * 100
        blue = (tgt - cur) / scale * 100
        red = 0.0
    else:
        green = tgt / scale * 100
        blue = 0.0
        red = (cur - tgt) / scale * 100
    parts = []
    if green > 0: parts.append(f'<div style="width:{green:.4f}%;background:#6f8f72"></div>')
    if blue > 0: parts.append(f'<div style="width:{blue:.4f}%;background:#6b8fc4"></div>')
    if red > 0: parts.append(f'<div style="width:{red:.4f}%;background:#c96b5b"></div>')
    bar = ''.join(parts) or '<div style="width:100%;background:#e5e0d5"></div>'
    st.markdown(
        f'<div style="height:{height}px;display:flex;overflow:hidden;border-radius:6px;background:#eee9df;">{bar}</div>'
        f'<div style="font-size:.78rem;color:#6b665b;margin-top:4px;">현재 {cur:.1f}% · 목표 {tgt:.1f}% · '
        f'<span style="color:#6f8f72;font-weight:700">초록=목표 충족</span> · '
        f'<span style="color:#c96b5b;font-weight:700">빨강=초과</span> · '
        f'<span style="color:#6b8fc4;font-weight:700">파랑=미달</span></div>', unsafe_allow_html=True)

def render_mobile_target_weight_card(name, current_pct, target_pct, amount):
    cur=max(0.0,float(current_pct or 0)); tgt=max(0.0,float(target_pct or 0)); scale=max(100.0,cur,tgt,1.0)
    green=min(cur,tgt)/scale*100; blue=max(tgt-cur,0)/scale*100; red=max(cur-tgt,0)/scale*100
    seg=[]
    if green: seg.append(f'<div style="width:{green:.4f}%;background:#16a34a"></div>')
    if blue: seg.append(f'<div style="width:{blue:.4f}%;background:#3b82f6"></div>')
    if red: seg.append(f'<div style="width:{red:.4f}%;background:#ef4444"></div>')
    st.markdown(f'<div class="weight-card"><div class="weight-head"><span>{name}</span><span>{cur:.1f}%</span></div><div class="weight-meta">{w(amount)} · 목표 {tgt:.1f}% · 괴리 {cur-tgt:+.1f}%p</div><div class="weight-bar">{"".join(seg)}</div><div class="weight-legend"><span><i class="weight-dot" style="background:#16a34a"></i>목표 충족</span><span><i class="weight-dot" style="background:#3b82f6"></i>목표 미달</span><span><i class="weight-dot" style="background:#ef4444"></i>목표 초과</span></div></div>', unsafe_allow_html=True)

if page == '🔄 리밸런싱 실행':
    info = last_snapshot_info()
    if info:
        last_date, days = info
        if days >= 25:
            st.warning(f'마지막 히스토리 저장: {last_date} ({days}일 전) — 이번 달 리밸런싱을 아직 안 하신 것 같아요.')
        else:
            st.caption(f'마지막 히스토리 저장: {last_date} ({days}일 전)')
    else:
        st.caption('아직 저장된 히스토리가 없습니다. 이번 리밸런싱 후 아래에서 저장해보세요.')
    cfgs = [c for c in get_strategies() if c.get('active', True)]
    active_codes = [c['code'] for c in cfgs]
    ap_assets = assets[assets['strategy'].isin(active_codes)]
    c1, c2 = st.columns(2)
    run_date = c1.date_input('리밸런싱 기준일', date.today())
    source = 'krx'  # 한국은 KRX 우선 → 공공데이터 자동 폴백. 사용자가 소스를 고를 필요가 없도록 통일.
    # 기준일이 바뀌면 이전 기준일의 조회 결과(실패 목록·트리거 판정)는 무효 → 자동 정리
    if st.session_state.get('last_run_date') != run_date.isoformat():
        st.session_state.pop('failed_tickers', None)
        st.session_state.pop('trigger_dd', None)
        st.session_state.last_run_date = run_date.isoformat()
        st.session_state.pop('run_fx_rate', None)
        st.session_state.pop('price_fetch_attempted', None)
    # 요약 카드: 활성 전략 총자산 · 마지막 저장 · 이번 달 말까지 남은 일수(월말 리밸런싱 워크플로우용)
    _g, _, _ = compute_portfolio_snapshot(assets, active_only=True)
    _sc1, _sc2, _sc3 = st.columns(3)
    _sc1.metric('활성 전략 총자산', w(_g))
    _sc2.metric('마지막 히스토리 저장', info[0] if info else '없음')
    _sc3.metric('이번 달 말까지', f'{calendar.monthrange(date.today().year, date.today().month)[1] - date.today().day}일')
    st.info('종가를 불러온 뒤 저장 버튼을 눌러야 히스토리(모든 전략 구성 스냅샷)가 저장됩니다. 미국 상장 종목은 선택한 조회일자의 Yahoo 종가와 같은 날짜의 USD/KRW 환율로 원화 환산합니다.')
    if st.session_state.get('price_fetch_attempted') and usd_krw_rate_missing(ap_assets, run_date):
        st.warning('미국 상장 종목의 선택 조회일자 USD/KRW 환율을 가져오지 못했습니다. 해당 종목 평가액이 0으로 계산될 수 있습니다.')

    pc1, pc2 = st.columns(2)
    fetch_mode = pc1.radio('가격 조회 방식', ['빠른 조회(캐시 우선)', '강제 새로고침(캐시 무시)'], horizontal=False)
    force_refresh_prices = fetch_mode.startswith('강제')
    fetch_clicked = pc2.button('🔄 가격 조회 실행', type='primary', use_container_width=True)

    if fetch_clicked:
        st.session_state.price_fetch_attempted = True
        ok = 0; errors = []; failed = []
        run_fx_rate = None
        if (ap_assets['market'] == 'US').any():
            run_fx_rate = get_usd_krw_rate(run_date.isoformat(), force_refresh=force_refresh_prices)
            st.session_state.run_fx_rate = run_fx_rate
            if run_fx_rate is None:
                errors.append(f'{run_date}: USD/KRW 환율 데이터 없음')
        _todo = [(i, a) for i, a in ap_assets.iterrows() if str(a['ticker']).strip() and str(a['ticker']).strip() != 'CASH']
        _prog = st.progress(0.0, text='가격 조회 준비 중...')
        for _n, (i, a) in enumerate(_todo, 1):
            t = str(a['ticker']).strip()
            mkt = a['market'] or 'KR'
            _prog.progress(min(1.0, (_n - 1) / max(1, len(_todo))), text=f'가격 조회 중... ({_n}/{len(_todo)}) · {t}')
            try:
                daydf = fetch_price_day(mkt, source, t, run_date.isoformat(), force_refresh=force_refresh_prices); row = daydf.iloc[-1]; assets.at[i, 'close'] = row['close']
                hist = fetch_price_monthly(mkt, source, t, run_date.isoformat(), force_refresh=force_refresh_prices)
                sig_col = price_col(hist)
                prices = hist.sort_values('date')[sig_col].tolist() if not hist.empty else [row['close']]
                if len(prices) < 2 and not hist.empty:
                    prices = hist.sort_values('date')['close'].tolist()
                assets.at[i, 'prices'] = prices
                # 신선도·출처 기록: 사용된 실제 거래일과 캐시 출처(휴장일 대체 시 'YYYY-MM-DD(대체)' 표시)
                used_day = str(row['date'])
                used_fmt = f'{used_day[:4]}-{used_day[4:6]}-{used_day[6:]}'
                if used_fmt != run_date.isoformat():
                    used_fmt += ' (대체)'
                assets.at[i, 'last_fetch_date'] = used_fmt
                latest_d, latest_src = cache_latest_info(t, mkt)
                assets.at[i, 'price_source'] = latest_src or ''
                ok += 1
                flagged, chg = fetch_price_anomaly(prices)
                if flagged:
                    errors.append(f'{t}: 최근 월간 변동률 {p(chg)} (분할/배당락/입력 오류 가능성, 값 확인 필요)')
                if len(prices) < 10:
                    errors.append(f"{t}: 월별 데이터가 {len(prices)}개뿐이라 SMA10 계산 불가"); failed.append(i)
            except Exception as e:
                errors.append(f'{t}: {e}'); failed.append(i)
            _prog.progress(min(1.0, _n / max(1, len(_todo))), text=f'가격 조회 중... ({_n}/{len(_todo)})')
        _prog.empty()
        # ISA(-10%)·SSO(-15% 이상) 트리거 판정용 최근 영업일 고점대비 하락률 (월말 데이터만으론 월중 고점을 놓침)
        trigger_dd = {}
        signal_rows = ap_assets[(ap_assets['strategy'].eq('ISA')) | ((ap_assets['strategy'].eq('SSO')) & (ap_assets['role'].eq('S&P500 기준')))]
        for strat, st_ticker, mkt in zip(signal_rows['strategy'], signal_rows['signal_ticker'], signal_rows['market']):
            if strat == 'ISA':
                # ISA 트리거는 실제 매매 ETF가 아니라 미국 상장 QQQ의 고점 대비 하락률을 사용한다.
                st_ticker, signal_market = 'QQQ', 'US'
            else:
                signal_market = mkt
            if not st_ticker or st_ticker == 'CASH':
                continue
            try:
                # 트리거는 실제 매매 종목의 스냅샷 가격과 분리해서 계산한다.
                # ISA는 QQQ, 최근 120거래일 고점 대비 기준일 이전 마지막 거래일 하락률이다.
                if signal_market == 'US':
                    trigger_dd[strat] = fetch_yahoo_signal_drawdown(st_ticker, run_date.isoformat(), 120, force_refresh=force_refresh_prices)
                else:
                    d = fetch_price_daily_recent(signal_market, source, st_ticker, run_date.isoformat(), 120, force_refresh=force_refresh_prices)
                    trigger_dd[strat] = drawdown_from_peak(d.sort_values('date')['close'].tolist()) if not d.empty else None
            except Exception as e:
                errors.append(f'{st_ticker}(트리거): {e}'); trigger_dd[strat] = None
        st.session_state.trigger_dd = trigger_dd
        st.session_state.failed_tickers = failed
        st.session_state.assets = assets; put_state('assets', assets.to_dict('records'))
        st.success(f'{ok}개 종목 반영')
        if errors: st.warning(' / '.join(errors[:8]))
        if ok:
            _fr_rows = []
            for _, _a in ap_assets.iterrows():
                if str(_a['ticker']).strip() and str(_a['ticker']).strip() != 'CASH':
                    _fr_rows.append({'전략': _a['strategy'], '티커': _a['ticker'], 'ETF': _a['name'],
                                     '종가 기준일': _a.get('last_fetch_date') or '조회 안 됨', '출처': _a.get('price_source') or '—',
                                     '종가': num0(n(_a['close']))})
            if _fr_rows:
                with st.expander(f'ℹ️ 가격 신선도·출처 ({len(_fr_rows)}종목)', expanded=False):
                    st.dataframe(pd.DataFrame(_fr_rows), use_container_width=True, hide_index=True)
                    _fxd, _fxr, _fxs = cache_fx_latest()
                    if _fxd:
                        st.caption(f'USD/KRW 가장 최근 캐시: {_fxd} · {num0(_fxr)}원 · {_fxs or "—"}')

    failed_idx = st.session_state.get('failed_tickers', [])
    failed_idx = [i for i in failed_idx if i in assets.index]
    if failed_idx:
        with st.expander(f'⚠️ 종가 조회 실패/데이터 부족 {len(failed_idx)}건', expanded=False):
            st.caption('상세 오류와 원인을 확인할 수 있습니다. 수동 종가 입력은 자동 조회가 끝내 실패할 때의 비상 수단입니다.')
            for i in failed_idx:
                a = assets.loc[i]
                cc1, cc2 = st.columns([2, 1])
                with cc1:
                    new_close = st.number_input(f"{a['name']} ({a['ticker']}) 종가", min_value=0.0, step=1.0,
                                                 value=n(a['close']), key=f'manual_close_{i}')
                    if st.button(f"{a['ticker']} 종가 적용", key=f'manual_close_btn_{i}'):
                        assets.at[i, 'close'] = new_close
                        st.session_state.assets = assets; put_state('assets', assets.to_dict('records'))
                        st.session_state.failed_tickers = [x for x in failed_idx if x != i]
                        st.success('반영했습니다.'); st.rerun()
                with cc2:
                    st.write('')
                    if st.button('캐시 지우고 재조회', key=f'retry_cache_{i}'):
                        mkt = a['market'] or 'KR'
                        cache_clear_prices_for(a['ticker'], mkt)
                        if mkt == 'US':
                            cache_clear_fx()
                        try:
                            if mkt == 'US':
                                st.session_state.run_fx_rate = get_usd_krw_rate(run_date.isoformat(), force_refresh=True)
                            daydf = fetch_price_day(mkt, source, a['ticker'], run_date.isoformat(), force_refresh=True); row2 = daydf.iloc[-1]
                            assets.at[i, 'close'] = row2['close']
                            hist2 = fetch_price_monthly(mkt, source, a['ticker'], run_date.isoformat(), force_refresh=True)
                            prices2 = hist2.sort_values('date')['close'].tolist() if not hist2.empty else [row2['close']]
                            assets.at[i, 'prices'] = prices2
                            st.session_state.assets = assets; put_state('assets', assets.to_dict('records'))
                            if len(prices2) >= 10:
                                st.session_state.failed_tickers = [x for x in failed_idx if x != i]
                                st.success(f"재조회 성공 ({len(prices2)}개월 확보)")
                            else:
                                st.warning(f"재조회는 됐지만 여전히 {len(prices2)}개월뿐입니다.")
                            st.rerun()
                        except Exception as e:
                            st.error(f'재조회 실패: {e}')

    trigger_dd = st.session_state.get('trigger_dd', {})
    rows = []
    for i, a in ap_assets.iterrows():
        if a['ticker'] == 'CASH':
            rows.append({'idx': i, '전략': a['strategy'], '티커': 'CASH', 'ETF': '현금', 'role': a['role'], '종가': 1.0,
                         'SMA10': None, 'SMA 위': '—', '12M': None, '현재금액': asset_value(a, st.session_state.get('run_fx_rate')), '목표%': a['target_pct']})
            continue
        close, sma, mom = calc_prices(a)
        sma_flag = ('YES' if close > sma else 'NO') if sma is not None else '데이터부족'
        rows.append({'idx': i, '전략': a['strategy'], '티커': a['ticker'], 'ETF': a['name'], 'role': a['role'], '종가': close,
                     'SMA10': sma, 'SMA 위': sma_flag, '12M': mom,
                     '현재금액': asset_value(a, st.session_state.get('run_fx_rate')), '목표%': a['target_pct']})
    vdf = pd.DataFrame(rows)

    QUARTER_END = run_date.month in (3, 6, 9, 12)
    plan_rows = []

    # ---- LAA: 나스닥/유로스탁스만 SMA 필터, 필터 이탈분은 현금. 목표비중 복원은 분기말에만 ----
    laa_all = vdf[vdf['전략'] == 'LAA'] if not vdf.empty else vdf
    if not laa_all.empty:
        laa = laa_all[laa_all['티커'] != 'CASH']; cash_row = laa_all[laa_all['티커'] == 'CASH']
        cash_cur = n(cash_row['현재금액'].sum()); total = laa['현재금액'].sum() + cash_cur
        cash_pct = n(cash_row['목표%'].sum())
        for _, r in laa.iterrows():
            filtered = r['티커'] in ('133690', '245350'); breached = filtered and r['SMA 위'] == 'NO'
            if breached: cash_pct += r['목표%']
            if QUARTER_END or breached:
                tgt = 0.0 if breached else total * r['목표%'] / 100
                note = 'SMA 이탈 → 현금화' if breached else ('목표비중 복원(분기말)' if QUARTER_END else '유지')
                plan_rows.append({'전략': 'LAA', '티커': r['티커'], 'ETF': r['ETF'], '현재금액': r['현재금액'], '목표금액': tgt, '매매액(+매수/-매도)': tgt - r['현재금액'], '비고': note})
            else:
                plan_rows.append({'전략': 'LAA', '티커': r['티커'], 'ETF': r['ETF'], '현재금액': r['현재금액'], '목표금액': r['현재금액'], '매매액(+매수/-매도)': 0.0, '비고': '유지(분기중)'})
        cash_tgt = total * cash_pct / 100
        plan_rows.append({'전략': 'LAA', '티커': 'CASH', 'ETF': '현금', '현재금액': cash_cur, '목표금액': cash_tgt, '매매액(+매수/-매도)': cash_tgt - cash_cur, '비고': '필터 이탈 자산 보관'})

    # ---- GSM: SMA 통과 후보 중 12M 1위 80%, 현금 20% (없으면 100% 현금) ----
    gsm_all = vdf[vdf['전략'] == 'GSM'] if not vdf.empty else vdf
    if not gsm_all.empty:
        gsm = gsm_all[gsm_all['티커'] != 'CASH']; cash_row = gsm_all[gsm_all['티커'] == 'CASH']
        cash_cur = n(cash_row['현재금액'].sum()); total = gsm['현재금액'].sum() + cash_cur
        passing = gsm[gsm['SMA 위'] == 'YES'].sort_values('12M', ascending=False)
        winner = passing.iloc[0] if not passing.empty else None
        for _, r in gsm.iterrows():
            is_winner = winner is not None and r['티커'] == winner['티커']
            tgt = total * 0.8 if is_winner else 0.0
            note = '선정(80%)' if is_winner else ('SMA 이탈' if r['SMA 위'] == 'NO' else ('데이터부족' if r['SMA 위'] == '데이터부족' else '미선정(순위 밀림)'))
            plan_rows.append({'전략': 'GSM', '티커': r['티커'], 'ETF': r['ETF'], '현재금액': r['현재금액'], '목표금액': tgt, '매매액(+매수/-매도)': tgt - r['현재금액'], '비고': note})
        cash_tgt = total * (0.2 if winner is not None else 1.0)
        plan_rows.append({'전략': 'GSM', '티커': 'CASH', 'ETF': '현금', '현재금액': cash_cur, '목표금액': cash_tgt, '매매액(+매수/-매도)': cash_tgt - cash_cur, '비고': '전략 대기현금' if winner is not None else '전 후보 SMA 이탈'})

    # ---- ISA: QQQ 고점대비 -10% → 레버리지(418660) 분할매수 ----
    isa_all = vdf[vdf['전략'] == 'ISA'] if not vdf.empty else vdf
    if not isa_all.empty:
        isa = isa_all[isa_all['티커'] != 'CASH']; cash_row = isa_all[isa_all['티커'] == 'CASH']
        if not isa.empty:
            r = isa.iloc[0]; dd = trigger_dd.get('ISA'); triggered = dd is not None and dd <= -0.10
            cash = n(cash_row['현재금액'].sum()); buy = cash / 2 if triggered else 0.0
            note = f'트리거 발동(QQQ 고점대비 {p(dd)}) → 현금 절반 분할매수' if triggered else f'대기(QQQ 고점대비 {p(dd) if dd is not None else "데이터 없음"})'
            plan_rows.append({'전략': 'ISA', '티커': r['티커'], 'ETF': r['ETF'], '현재금액': r['현재금액'], '목표금액': r['현재금액'] + buy, '매매액(+매수/-매도)': buy, '비고': note})
            plan_rows.append({'전략': 'ISA', '티커': 'CASH', 'ETF': '현금', '현재금액': cash, '목표금액': cash - buy, '매매액(+매수/-매도)': -buy, '비고': '매수 재원'})

    # ---- SSO: S&P500(360750) 자체 고점대비 -15%↓ → 현금성 자산(153130) 절반을 주식으로 ----
    sso = vdf[vdf['전략'] == 'SSO'] if not vdf.empty else vdf
    if not sso.empty:
        total = sso['현재금액'].sum(); dd = trigger_dd.get('SSO'); triggered = dd is not None and dd <= -0.15
        stock_pct = 85.0 if triggered else 70.0
        for _, r in sso.iterrows():
            is_stock = r['티커'] == '360750'; tgt = total * (stock_pct if is_stock else 100 - stock_pct) / 100
            note = (f'트리거 발동(고점대비 {p(dd)}) → 현금 절반 투입' if triggered else f'평시 유지(고점대비 {p(dd) if dd is not None else "데이터 없음"})') if is_stock else ('트리거 발동 → 현금 축소' if triggered else '평시 유지')
            plan_rows.append({'전략': 'SSO', '티커': r['티커'], 'ETF': r['ETF'], '현재금액': r['현재금액'], '목표금액': tgt, '매매액(+매수/-매도)': tgt - r['현재금액'], '비고': note})

    # ---- EM/금/별도현금: 리밸런싱 대상 아님 ----
    em = vdf[vdf['전략'] == 'EM'] if not vdf.empty else vdf
    if not em.empty:
        for _, r in em.iterrows():
            plan_rows.append({'전략': 'EM', '티커': r['티커'] or '-', 'ETF': r['ETF'], '현재금액': r['현재금액'], '목표금액': r['현재금액'], '매매액(+매수/-매도)': 0.0, '비고': '매매 없음(연 1회만 허용)'})

    # ---- 사용자 추가 전략: 전용 규칙이 없으므로 목표비중(자산+현금 포함) 그대로 복원하는 정적 리밸런싱 적용 ----
    for cfg in cfgs:
        code = cfg['code']
        if code in KNOWN_STRATEGIES or vdf.empty: continue
        sub_all = vdf[vdf['전략'] == code]
        if sub_all.empty: continue
        sub = sub_all[sub_all['티커'] != 'CASH']; cash_row = sub_all[sub_all['티커'] == 'CASH']
        cash = n(cash_row['현재금액'].sum()); total = sub['현재금액'].sum() + cash
        for _, r in sub.iterrows():
            tgt = total * n(r['목표%']) / 100
            plan_rows.append({'전략': code, '티커': r['티커'], 'ETF': r['ETF'], '현재금액': r['현재금액'], '목표금액': tgt, '매매액(+매수/-매도)': tgt - r['현재금액'], '비고': '목표비중 리밸런싱'})
        if not cash_row.empty:
            cash_tgt = total * n(cash_row['목표%'].sum()) / 100
            plan_rows.append({'전략': code, '티커': 'CASH', 'ETF': '현금', '현재금액': cash, '목표금액': cash_tgt, '매매액(+매수/-매도)': cash_tgt - cash, '비고': '현금 목표비중'})

    plan_df = pd.DataFrame(plan_rows)
    st.subheader('이번 달 상태 & 액션플랜')
    st.caption('전략 우선순위(LAA→GSM→ISA→SSO→EM) 순으로 전략별 표를 보여줍니다. 매수는 빨간 볼드, 매도는 파란 볼드로 표시됩니다.')
    if plan_df.empty or vdf.empty:
        st.warning('종목 데이터를 먼저 불러오세요.')
    else:
        sig_lookup = {(r['전략'], r['티커']): r for _, r in vdf.iterrows()}
        merged_rows = []
        for _, pr in plan_df.iterrows():
            sig = sig_lookup.get((pr['전략'], pr['티커']), {})
            merged_rows.append({
                '전략': pr['전략'], '티커': pr['티커'], 'ETF': pr['ETF'],
                '종가': sig.get('종가'), 'SMA10': sig.get('SMA10'), 'SMA 위': sig.get('SMA 위'), '12M': sig.get('12M'),
                '현재금액': pr['현재금액'], '목표금액': pr['목표금액'],
                '매매액': pr['매매액(+매수/-매도)'], '비고': pr['비고'],
            })
        merged_df = pd.DataFrame(merged_rows)
        order = ordered_strategy_codes(cfgs)
        for strat in order:
            g = merged_df[merged_df['전략'] == strat]
            if g.empty: continue
            cfg = next((c for c in cfgs if c['code'] == strat), {})
            account_name = cfg.get('account', strat)
            status_label, status_help = strategy_rebalance_status(g)
            st.markdown(f'#### {strat} · {account_name}')
            st.caption(f'{status_label}  ·  {status_help}')

            if MOBILE:
                total_cur = g['현재금액'].sum()
                total_tgt = g['목표금액'].sum()
                total_trade = g['매매액'].sum()
                buys = g[g['매매액'] > 1000]
                sells = g[g['매매액'] < -1000]

                sc1, sc2, sc3 = st.columns(3)
                sc1.metric('현재', w(total_cur))
                sc2.metric('목표', w(total_tgt))
                sc3.metric('순매매', w(total_trade))

                for _, r in g.iterrows():
                    trade = float(r['매매액'])
                    if trade > 1000:
                        action = f'🛒 매수 +{w(trade)}'
                        tone = 'pos'
                    elif trade < -1000:
                        action = f'💰 매도 {w(-trade)}'
                        tone = 'neg'
                    else:
                        action = '⏸ 유지'
                        tone = None

                    cur = float(r['현재금액'])
                    tgt = float(r['목표금액'])
                    gap = float(r['목표금액'] - r['현재금액'])
                    pct = (cur / total_cur * 100) if total_cur > 0 else 0
                    target_pct = (tgt / total_tgt * 100) if total_tgt > 0 else 0

                    mobile_card(
                        f"{r['ETF']} · {r['티커']}",
                        [
                            f"<b>{action}</b> · {r['비고']}",
                            f"현재 {w(cur)} ({pct:.1f}%) → 목표 {w(tgt)} ({target_pct:.1f}%)",
                            f"필요 조정 {w(gap) if gap >= 0 else '-' + w(-gap)} · 종가 {num0(r['종가'])}",
                            f"SMA10 {num0(r['SMA10']) if r['SMA10'] != '데이터부족' else '데이터 부족'} · 12M {r['12M']}",
                        ],
                        tone=tone
                    )

                if not buys.empty or not sells.empty:
                    parts = []
                    if not buys.empty:
                        parts.append('매수 ' + ', '.join(f"{x['ETF']} {w(x['매매액'])}" for _, x in buys.iterrows()))
                    if not sells.empty:
                        parts.append('매도 ' + ', '.join(f"{x['ETF']} {w(-x['매매액'])}" for _, x in sells.iterrows()))
                    st.info(' · '.join(parts))
                st.divider()
                continue

            show = g.copy()
            show['SMA10'] = show['SMA10'].apply(lambda x: num0(x) if x is not None else '데이터부족')
            show['SMA 위'] = show['SMA 위'].fillna('—')
            show['12M'] = show['12M'].apply(lambda x: p(x) if x is not None else '—')
            for c in ['종가', '현재금액', '목표금액']:
                show[c] = show[c].apply(num0)
            show['매매액'] = g['매매액'].apply(lambda x: f'+{num0(x)}' if x > 1000 else (num0(x) if x < -1000 else '0'))
            show = show[['티커', 'ETF', '종가', 'SMA10', 'SMA 위', '12M', '현재금액', '목표금액', '매매액', '비고']]

            def color_action(row):
                styles = [''] * len(row); idx = list(row.index).index('매매액'); v = row['매매액']
                if v.startswith('+'): styles[idx] = 'color:#B23B2E; font-weight:700;'
                elif v.startswith('-'): styles[idx] = 'color:#2E5F8A; font-weight:700;'
                return styles

            st.dataframe(show.style.apply(color_action, axis=1), use_container_width=True, hide_index=True)

            buys = g[g['매매액'] > 1000]; sells = g[g['매매액'] < -1000]
            parts = []
            if not buys.empty: parts.append('매수: ' + ', '.join(f"{x.ETF} {w(x['매매액'])}" for _, x in buys.iterrows()))
            if not sells.empty: parts.append('매도: ' + ', '.join(f"{x.ETF} {w(-x['매매액'])}" for _, x in sells.iterrows()))
            st.markdown(('**' + ' · '.join(parts) + '**') if parts else '_거래 없음_')
            st.divider()

        action_rows = merged_df[merged_df['매매액'].abs() > 1000]
        if not action_rows.empty:
            st.markdown('### ✅ 실행 체크리스트 (계획 대비 실제)')
            st.caption('실제로 주문을 넣었으면 체크하고, 체결금액이 계획과 다르면 직접 입력하세요. 저장하면 히스토리 세부내역에서 계획 대비 실제를 비교할 수 있습니다.')
            existing_exec = {(x.get('date'), x.get('strategy'), x.get('ticker')): x for x in get_state('executions') if x.get('date') == run_date.isoformat()}
            with st.form('exec_checklist_form'):
                exec_inputs = {}
                for strat in order:
                    g2 = action_rows[action_rows['전략'] == strat]
                    if g2.empty: continue
                    st.markdown(f'**{strat}**')
                    for _, r in g2.iterrows():
                        key = (run_date.isoformat(), r['전략'], r['티커'])
                        prev = existing_exec.get(key, {})
                        ec1, ec2 = st.columns([1, 2])
                        with ec1:
                            done = st.checkbox(f"{r['ETF']} 실행완료", value=bool(prev.get('done', False)), key=f"exec_done_{r['전략']}_{r['티커']}")
                        with ec2:
                            actual = st.number_input(
                            f"{r['ETF']} 실제 체결금액",
                            value=n(prev.get('actual', r['매매액'])),
                            step=1000.0,
                            key=f"exec_actual_{r['전략']}_{r['티커']}"
                        )
                        planned_shares = n(prev.get('planned_shares', 0))
                        actual_shares = st.number_input(
                            f"{r['ETF']} 실제 체결 주수",
                            value=planned_shares if prev.get('actual_shares') is None else n(prev.get('actual_shares', 0)),
                            min_value=0.0,
                            step=1.0,
                            key=f"exec_shares_{r['전략']}_{r['티커']}",
                            help="실제 주문 체결 수량을 입력합니다. 소수점 거래가 가능한 상품은 0.1주 단위 등으로 직접 입력할 수 있습니다."
                        )
                        exec_inputs[key] = {
                            'ETF': r['ETF'],
                            'planned': float(r['매매액']),
                            'done': done,
                            'actual': actual,
                            'planned_shares': planned_shares,
                            'actual_shares': actual_shares
                        }
                if st.form_submit_button('체크리스트 저장'):
                    all_exec = [x for x in get_state('executions') if (x.get('date'), x.get('strategy'), x.get('ticker')) not in exec_inputs]
                    for (d, strat, t), v in exec_inputs.items():
                        all_exec.append({
                            'date': d,
                            'strategy': strat,
                            'ticker': t,
                            'ETF': v['ETF'],
                            'planned': v['planned'],
                            'done': v['done'],
                            'actual': v['actual'],
                            'planned_shares': v.get('planned_shares', 0),
                            'actual_shares': v.get('actual_shares', 0),
                        })
                    put_state('executions', all_exec)
                    st.success('체크리스트를 저장했습니다.')

    # ───────────────────────────────────────────────────────────────────────
    # 리밸런싱 실행 전 최종 점검
    # ───────────────────────────────────────────────────────────────────────
    with st.expander('🛡️ 리밸런싱 실행 전 최종 점검', expanded=False):
        review_errors = []
        review_warnings = []

        if plan_df.empty:
            review_errors.append('리밸런싱 계획이 없습니다.')
        else:
            for strat in order:
                sg = plan_df[plan_df['전략'] == strat]
                if sg.empty:
                    continue
                status, _ = strategy_rebalance_status(sg)
                if status == '⚠️ 데이터 확인':
                    review_warnings.append(f'{strat}: 가격/SMA 데이터 확인 필요')

            # 목표비중 합계 점검
            for strat in order:
                sg = plan_df[(plan_df['전략'] == strat) & (plan_df['티커'] != 'CASH')]
                if sg.empty:
                    continue
                # 현재/목표 금액이 존재하는지 확인
                if sg['목표금액'].isna().any():
                    review_errors.append(f'{strat}: 목표금액 계산 오류')

        exec_map = {(x.get('date'), x.get('strategy'), x.get('ticker')): x
                    for x in get_state('executions')
                    if x.get('date') == run_date.isoformat()}
        pending = 0
        for _, r in action_rows.iterrows():
            key = (run_date.isoformat(), r['전략'], r['티커'])
            rec = exec_map.get(key, {})
            if not rec.get('done', False):
                pending += 1

        if review_errors:
            for msg in review_errors:
                st.error(msg)
        else:
            st.success('계산 및 계획 데이터 점검 완료')

        if review_warnings:
            for msg in review_warnings:
                st.warning(msg)

        if pending:
            st.info(f'실행 체크리스트 미완료 항목: {pending}건')
        else:
            st.success('실행 체크리스트가 모두 완료되었습니다.')

        st.caption('이 점검은 주문을 실행하지 않습니다. 실제 체결 후에는 아래 실행 체크리스트에 체결 금액과 체결 주수를 기록하세요.')

    _no_price = [f"{a['name']}({a['ticker']})" for _, a in ap_assets.iterrows() if str(a['ticker']).strip() and str(a['ticker']).strip() != 'CASH' and n(a['close']) <= 0]
    if _no_price:
        st.warning(f'아직 종가를 조회하지 못한 종목이 있습니다: {", ".join(_no_price[:8])}{" 외 n건" if len(_no_price) > 8 else ""} — 지금 저장하면 해당 종목 평가액이 0으로 기록됩니다.')
    else:
        st.caption('모든 종목의 종가가 조회되어 있어 저장하면 정확한 평가액으로 기록됩니다.')
    if st.button('Action Plan + 전체 스냅샷을 히스토리에 저장'):
        plan_text = ' | '.join(f"{r['전략']} {r['ETF']}: {w(r['매매액(+매수/-매도)'])} ({r['비고']})" for _, r in plan_df.iterrows() if abs(r['매매액(+매수/-매도)']) > 1000) if not plan_df.empty else ''
        save_history_snapshot(assets, run_date, plan_text=plan_text)
        st.success('저장했습니다.'); toast('히스토리에 저장했습니다.')

elif page == '🏠 대시보드':
    st.subheader('포트폴리오 대시보드'); st.caption('전략(계좌)별 목표비중 대비 현재비중과, 전체 전략의 자산분류별 분포를 한눈에 봅니다 · Snowball72 스타일 참고')
    grand_total, snap_df, cfgs = compute_portfolio_snapshot(assets)
    st.metric('전체 총자산 (모든 전략 합계)', w(grand_total))
    if snap_df.empty:
        st.info('전략과 종목을 먼저 구성하세요.')
    else:
        for cfg in cfgs:
            code = cfg['code']; g = snap_df[snap_df['전략'] == code]
            if g.empty: continue
            strat_total = g['현재금액'].sum(); badge = ' · 동적(모멘텀)' if cfg.get('dynamic') else ''
            st.markdown(f"#### {code} · {cfg.get('account', code)}{badge} — {w(strat_total)}")
            if MOBILE:
                for _, r in g.iterrows():
                    render_mobile_target_weight_card(r['ETF'], r['현재비중'], r['목표비중'], r['현재금액'])
            else:
                for _, r in g.iterrows():
                    dc1, dc2 = st.columns([1.0, 3.2])
                    with dc1:
                        st.markdown(f"**{r['ETF']}**<br>{w(r['현재금액'])}", unsafe_allow_html=True)
                    with dc2:
                        render_target_weight_bar(r['현재비중'], r['목표비중'])
        st.divider(); st.markdown('#### 전략별 비중 (전체 자산 대비)')
        by_strategy = snap_df.groupby('전략')['현재금액'].sum()
        if grand_total > 0: st.bar_chart((by_strategy / grand_total * 100).rename('비중(%)'))

        st.divider(); st.markdown('#### 전체 전략 합산 · 자산분류별 분포')
        cat_df = compute_category_breakdown(assets)
        targets = get_category_targets()
        with st.expander('자산군 목표비중 설정', expanded=False):
            st.caption('전체 포트폴리오 기준 목표비중입니다. 합계가 100%가 아니어도 저장은 되지만, 아래 괴리는 100% 기준으로 계산됩니다.')
            new_targets = {}
            tcols = st.columns(3)
            for i, cat in enumerate(CATEGORY_OPTIONS):
                with tcols[i % 3]:
                    new_targets[cat] = st.number_input(cat, min_value=0.0, max_value=100.0, step=1.0, value=n(targets.get(cat, 0)), key=f'cat_tgt_{cat}')
            tgt_sum = sum(new_targets.values())
            st.caption(f'목표비중 합계: {tgt_sum:.1f}%' + ('' if abs(tgt_sum - 100) < 0.5 else ' — 100%가 되도록 맞춰보세요.'))
            if st.button('자산군 목표비중 저장'):
                put_state('category_targets', new_targets); st.success('저장했습니다.'); st.rerun()
        if not cat_df.empty:
            show = cat_df.copy()
            show['목표비중'] = show['분류'].map(lambda c: n(targets.get(c, 0)))
            show['괴리(%p)'] = show['비중'] - show['목표비중']
            disp_cat = show.copy()
            disp_cat['금액'] = disp_cat['금액'].map(w)
            disp_cat['비중'] = disp_cat['비중'].map(lambda x: f'{x:.1f}%')
            disp_cat['목표비중'] = disp_cat['목표비중'].map(lambda x: f'{x:.1f}%')
            disp_cat['괴리(%p)'] = disp_cat['괴리(%p)'].map(lambda x: f'{x:+.1f}')
            st.dataframe(disp_cat, use_container_width=True, hide_index=True)
            st.bar_chart(cat_df.set_index('분류')['비중'])
            worst = show.reindex(show['괴리(%p)'].abs().sort_values(ascending=False).index).head(3)
            flagged = worst[worst['괴리(%p)'].abs() >= 3]
            if not flagged.empty:
                st.warning('목표비중과 3%p 이상 벌어진 자산군: ' + ', '.join(f"{r['분류']} ({r['괴리(%p)']:+.1f}%p)" for _, r in flagged.iterrows()))

elif page == '⚙️ 설정':
    st.subheader('전략 구성'); st.caption('전략별 계좌 정보와 후보 자산(현금 포함)을 관리합니다.')
    cfgs = get_strategies(); codes = [c['code'] for c in cfgs]

    with st.expander('🎚️ 가격 조회 정책 (모든 전략 공통)', expanded=False):
        st.caption('기준일이 휴장일일 때의 종가·환율 처리 방식과, SMA/모멘텀/트리거 신호에 쓸 가격 기준을 선택합니다. 평가액(원화)은 항상 실제 거래 종가로 계산됩니다.')
        pol = price_policy()
        new_pol = st.radio('휴장일 정책', ['strict', 'prev'], index=0 if pol == 'strict' else 1, format_func=lambda x: '해당 날짜만 사용(휴장일이면 실패 처리)' if x == 'strict' else '직전 거래일로 대체(트리거 제외)', key='price_policy_radio')
        if new_pol != pol:
            put_state('price_policy', new_pol); st.rerun()
        mode = 'adjclose' if use_adjclose() else 'close'
        new_mode = st.radio('신호(SMA/모멘텀/트리거) 가격 기준', ['close', 'adjclose'], index=0 if mode == 'close' else 1, format_func=lambda x: '원시 종가(현재 동작)' if x == 'close' else '배당재투자 기준(미국 종목, 배당락 왜곡 방지)', key='price_mode_radio')
        if new_mode != mode:
            put_state('price_mode', new_mode); st.rerun()
        st.caption('배당재투자 기준을 선택하면 미국 상장 종목의 SMA·모멘텀·트리거 판정에 배당이 재투자된 수정주가(adjclose)를 사용합니다. 한국 상장 ETF는 분배금이 종가에 이미 반영되지 않아 원시 종가를 사용합니다.')

    with st.expander('➕ 새 전략 추가'):
        nc1, nc2 = st.columns(2)
        new_code = nc1.text_input('전략 코드', placeholder='예: CORE2')
        new_account = nc2.text_input('계좌 별명', placeholder='예: 개인연금')
        new_desc = st.text_area('전략 설명', placeholder='이 전략의 규칙을 간단히 적어두세요', height=70)
        new_dynamic = st.checkbox('동적(모멘텀 선택형)', value=False, help='GSM처럼 매달 후보 중 하나만 골라 투자하는 방식이면 체크 — 목표비중 100% 합계 검사를 하지 않습니다.')
        if st.button('전략 추가'):
            code_clean = new_code.strip().upper()
            if not code_clean:
                st.error('전략 코드를 입력하세요.')
            elif code_clean in codes:
                st.error('이미 존재하는 전략 코드입니다.')
            else:
                cfgs.append({'code': code_clean, 'account': new_account.strip() or code_clean, 'description': new_desc.strip(), 'dynamic': new_dynamic, 'active': True, 'annual_limit': 0.0})
                put_state('strategies', cfgs)
                assets.loc[len(assets)] = {'id': str(len(assets) + 1), 'strategy': code_clean, 'ticker': 'CASH', 'name': '현금',
                                            'market': 'KR', 'role': '대기현금', 'target_pct': 100.0, 'shares': 0.0, 'close': 1.0,
                                            'prices': [], 'signal_ticker': 'CASH', 'category': '현금'}
                st.session_state.assets = assets; put_state('assets', assets.to_dict('records'))
                st.success(f'{code_clean} 전략을 추가했습니다.'); st.rerun()

    chosen = st.selectbox('전략 선택', codes)
    chosen_cfg = next((c for c in cfgs if c['code'] == chosen), {'code': chosen, 'account': chosen, 'description': '', 'dynamic': False, 'active': True})

    mgmt1, mgmt2, mgmt3 = st.columns(3)
    with mgmt1:
        is_active = chosen_cfg.get('active', True)
        new_active = st.checkbox('전략 활성화', value=is_active, key=f'active_{chosen}', help='비활성화하면 Action Plan·대시보드·총자산 합산에서 제외됩니다 (데이터는 남아있습니다).')
        if new_active != is_active:
            cfgs2 = get_strategies()
            for c in cfgs2:
                if c['code'] == chosen: c['active'] = new_active
            put_state('strategies', cfgs2); st.rerun()
    with mgmt2:
        if chosen in KNOWN_STRATEGIES:
            st.caption(f'{chosen}은(는) 전용 리밸런싱 규칙 코드라 이름 변경이 불가합니다.')
        else:
            new_name = st.text_input('전략명(코드) 변경', value='', placeholder=chosen, key=f'rename_{chosen}')
            if st.button('이름 변경', key=f'renamebtn_{chosen}') and new_name.strip():
                assets2, ok, msg = rename_strategy(chosen, new_name, assets)
                if ok:
                    st.session_state.assets = assets2; st.success('변경했습니다.'); st.rerun()
                else:
                    st.error(msg)
    with mgmt3:
        confirm_del = st.checkbox('삭제 확인', key=f'delconfirm_{chosen}', help='체크해야 삭제 버튼이 활성화됩니다.')
        if st.button('🗑 전략 삭제', key=f'delbtn_{chosen}', disabled=not confirm_del):
            assets2 = delete_strategy(chosen, assets)
            st.session_state.assets = assets2
            st.success(f'{chosen} 전략과 소속 종목을 모두 삭제했습니다.'); st.rerun()

    subset = assets[assets['strategy'].eq(chosen)].copy()
    strat_total = subset.apply(asset_value, axis=1).sum() if not subset.empty else 0.0

    cc1, cc2 = st.columns([1, 2])
    with cc1:
        edit_account = st.text_input('계좌 별명', value=chosen_cfg.get('account', chosen), key=f'acct_{chosen}')
        edit_dynamic = st.checkbox('동적(모멘텀 선택형)', value=chosen_cfg.get('dynamic', False), key=f'dyn_{chosen}')
        st.metric('전략 총액 (후보 자산 현재평가액 합)', w(strat_total))
    with cc2:
        edit_desc = st.text_area('전략 설명', value=chosen_cfg.get('description', ''), key=f'desc_{chosen}', height=100)

    with st.expander('💰 연간 납입한도 추적 (연금저축·ISA 등)', expanded=n(chosen_cfg.get('annual_limit', 0)) > 0):
        edit_limit = st.number_input('연간 납입한도(원, 0=추적 안 함)', min_value=0.0, step=100000.0,
                                      value=n(chosen_cfg.get('annual_limit', 0)), key=f'limit_{chosen}')
        if edit_limit > 0:
            ytd = ytd_contribution(chosen)
            remain = edit_limit - ytd
            lc1, lc2, lc3 = st.columns(3)
            lc1.metric(f'{date.today().year}년 납입액', w(ytd))
            lc2.metric('한도', w(edit_limit))
            lc3.metric('잔여한도', w(remain), delta=None if remain >= 0 else '한도 초과')
            st.progress(min(1.0, max(0.0, ytd / edit_limit)))
            st.caption('입출금 원장에서 이 전략으로 태그된 입금(성과 비교 페이지)만 합산됩니다.')

    disp = pd.DataFrame({
        '시장': subset['market'],
        '상품명': subset.apply(lambda r: f"{r['name']} ({r['ticker']})" if r['name'] else str(r['ticker']), axis=1),
        '보유수량': subset['shares'].round(0),
        '종가': subset['close'].round(0),
        '현재평가액': subset.apply(asset_value, axis=1).round(0),
        '마지막조회': subset['last_fetch_date'].fillna(''),
        '출처': subset['price_source'].fillna(''),
        '목표비중': pd.to_numeric(subset['target_pct'], errors='coerce').fillna(0.0),
        '현재비중': subset.apply(lambda r: (asset_value(r) / strat_total * 100 if strat_total > 0 else 0.0), axis=1),
        '분류': subset['category'],
    })
    disp['괴리(%)'] = disp['현재비중'] - disp['목표비중']
    disp = disp[['시장', '상품명', '보유수량', '종가', '현재평가액', '마지막조회', '출처', '목표비중', '현재비중', '괴리(%)', '분류']]

    st.caption('상품명 옆 괄호가 티커입니다. 티커를 바꾸려면 행을 삭제하고 아래 검색으로 다시 추가하세요. 현금 행은 "보유수량"에 원화 금액을 직접 입력하세요(종가=1). 현재평가액은 종가×보유수량으로 자동 계산됩니다.')

    if MOBILE:
        for _, r in subset.iterrows():
            val = asset_value(r); cur_pct = val / strat_total * 100 if strat_total > 0 else 0.0
            tgt_pct = n(r['target_pct']); gap = cur_pct - tgt_pct
            tone = 'pos' if gap > 3 else ('neg' if gap < -3 else None)
            mobile_card(f"{r['name']} ({r['market']})", [
                f"{r['ticker']} · {r['category']}",
                f"현재 {cur_pct:.1f}% / 목표 {tgt_pct:.1f}% (괴리 {gap:+.1f}%p)",
                f"평가액 {num0(val)}원 · 종가 {num0(r['close'])} · 보유수량 {num0(r['shares'])}",
            ], tone=tone)
        editor_ctx = st.expander('표로 편집하기 (보유수량·목표비중·분류 수정)', expanded=False)
    else:
        editor_ctx = st.container()

    with editor_ctx:
        edited = st.data_editor(
            disp, num_rows='dynamic', use_container_width=True, hide_index=True,
            disabled=['종가', '현재평가액', '마지막조회', '출처', '현재비중', '괴리(%)'],
            column_config={
                '보유수량': st.column_config.NumberColumn('보유수량', format='localized', step=1),
                '종가': st.column_config.NumberColumn('종가', format='localized'),
                '현재평가액': st.column_config.NumberColumn('현재평가액(원)', format='localized'),
                '목표비중': st.column_config.NumberColumn('목표비중(%)', min_value=0, max_value=100, step=0.1),
                '현재비중': st.column_config.ProgressColumn('현재비중', format='%.1f%%', min_value=0, max_value=100),
                '괴리(%)': st.column_config.NumberColumn('괴리(%)', format='%.1f'),
                '분류': st.column_config.SelectboxColumn('분류', options=CATEGORY_OPTIONS, required=True),
            },
        )

    asset_sum = pd.to_numeric(edited['목표비중'], errors='coerce').fillna(0.0).sum()
    if edit_dynamic:
        st.caption(f'동적 전략: 목표비중 합계 검사를 하지 않습니다 (현재 합계 {asset_sum:.1f}%).')
        weights_ok = True
    else:
        weights_ok = abs(asset_sum - 100) <= 0.05
        if weights_ok: st.success('목표비중 합계 100% ✓ (현금 행 포함)')
        else: st.error(f'목표비중 합계 {asset_sum:.1f}% — 현금 행을 포함해 정확히 100%가 되어야 저장됩니다.')
    if not subset.empty:
        st.download_button('현재 전략 구성 CSV 다운로드',
                           subset[['ticker', 'name', 'market', 'shares', 'close', 'target_pct', 'category']].to_csv(index=False),
                           file_name=f'{chosen}-assets.csv', mime='text/csv')

    st.markdown('### 종목 검색·추가 (ETF + 개별주식, 한국/미국)')
    mkt_choice = st.radio('시장', ['한국(KRX)', '미국(Yahoo)'], horizontal=True, key='mkt_choice')
    if mkt_choice == '한국(KRX)':
        q = st.text_input('티커 또는 종목명 일부 입력', key='kr_q')
        catalog = load_krx_universe(date.today().isoformat())
        if catalog.empty:
            err = catalog.attrs.get('error', '알 수 없는 이유로 목록을 가져오지 못했습니다.')
            st.warning(f'종목 목록을 가져오지 못했습니다.\n\n{err}\n\nETF는 secrets.toml의 KRX_BASE_URL/KRX_AUTH_KEY(가격 조회와 동일)를, 개별종목은 DATA_GO_SERVICE_KEY(data.go.kr "금융위원회_주식시세정보" 활용신청)를 확인해주세요.')
        if q:
            filtered = catalog[catalog['ticker'].str.contains(q, case=False, na=False, regex=False) | catalog['name'].str.contains(q, case=False, na=False, regex=False)]
            filtered = filtered.sort_values(['name', 'ticker'])
            shown = filtered.head(20)
            opts = [f"{r['name']} · {r['ticker']} ({r['type']})" for _, r in shown.iterrows()]
            if opts:
                picked = st.radio('검색 결과', opts, key='kr_pick')
                if len(filtered) > 20: st.caption(f'{len(filtered)}개 중 상위 20개만 표시했습니다. 검색어를 더 구체적으로 입력해보세요.')
                if st.button('선택 종목을 전략에 추가', key='kr_add'):
                    nm, rest = picked.split(' · ', 1); t = rest.rsplit(' (', 1)[0]
                    assets.loc[len(assets)] = {'id': str(len(assets) + 1), 'strategy': chosen, 'ticker': t, 'name': nm, 'market': 'KR',
                                                'role': '사용자 추가', 'target_pct': 0.0, 'shares': 0.0, 'close': 0.0, 'prices': [],
                                                'signal_ticker': t, 'category': '기타'}
                    st.session_state.assets = assets; put_state('assets', assets.to_dict('records'))
                    st.success(f'{t} {nm} 추가'); st.rerun()
            else:
                st.caption('검색 결과가 없습니다.')
        else:
            st.caption('티커 또는 종목명을 입력하면 후보가 바로 아래 나타납니다.')
        st.caption(f'KRX 목록 {len(catalog):,}개 (ETF는 이미 설정된 KRX_AUTH_KEY로 조회, 개별종목은 pykrx 보강 시도)')
    else:
        q = st.text_input('종목명 또는 티커 입력 (예: Apple, AAPL)', key='us_q')
        if st.button('검색', key='us_search') and q:
            st.session_state.us_results = search_us_symbols(q)
        results = st.session_state.get('us_results', pd.DataFrame(columns=['ticker', 'name', 'exchange']))
        if not results.empty:
            results = results.sort_values(['name', 'ticker'])
            opts = [f"{r['name']} · {r['ticker']} ({r['exchange']})" for _, r in results.iterrows()]
            picked = st.radio('검색 결과', opts, key='us_pick')
            if st.button('선택 종목을 전략에 추가', key='us_add'):
                nm, rest = picked.split(' · ', 1); t = rest.rsplit(' (', 1)[0]
                assets.loc[len(assets)] = {'id': str(len(assets) + 1), 'strategy': chosen, 'ticker': t, 'name': nm, 'market': 'US',
                                            'role': '사용자 추가', 'target_pct': 0.0, 'shares': 0.0, 'close': 0.0, 'prices': [],
                                            'signal_ticker': t, 'category': '기타'}
                st.session_state.assets = assets; put_state('assets', assets.to_dict('records'))
                st.success(f'{t} {nm} 추가'); st.rerun()
        st.caption('야후 파이낸스 검색 API 사용')

    if st.button('선택 전략 저장', type='primary'):
        if not weights_ok:
            st.error('목표비중 합계를 100%로 맞춘 뒤 저장하세요.')
        else:
            def parse_name_ticker(text):
                text = str(text).strip()
                m = re.match(r'^(.*)\s\(([^()]+)\)$', text)
                return (m.group(1).strip(), m.group(2).strip()) if m else (text, '')
            parsed = edited['상품명'].apply(parse_name_ticker)
            rebuilt = edited.rename(columns={'시장': 'market', '목표비중': 'target_pct', '보유수량': 'shares', '분류': 'category'})
            rebuilt['name'] = [x[0] for x in parsed]; rebuilt['ticker'] = [x[1] for x in parsed]
            rebuilt['ticker'] = rebuilt.apply(lambda r: kr6(r['ticker']) if r['market'] == 'KR' and r['ticker'] else r['ticker'], axis=1)
            rebuilt = rebuilt[['ticker', 'name', 'market', 'target_pct', 'shares', 'category']].copy()
            rebuilt = rebuilt[~((rebuilt['ticker'].fillna('') == '') & (rebuilt['name'].fillna('') == ''))]
            rebuilt['strategy'] = chosen
            # 종가는 화면에 소수점 없이 반올림해서 보여줄 뿐, 실제 저장값은 항상 마지막으로 조회된 정밀값을 그대로 유지한다
            # (편집 화면에 나온 반올림값을 저장하면 조회할 때마다 정밀도가 깎여나간다).
            _meta_cols = ['role', 'prices', 'signal_ticker', 'close', 'last_fetch_date', 'price_source']
            old_meta = subset.drop_duplicates('ticker').set_index('ticker')[_meta_cols]
            def carry(row):
                if row['ticker'] in old_meta.index:
                    m = old_meta.loc[row['ticker']]
                    return pd.Series({'role': m['role'], 'prices': m['prices'], 'signal_ticker': m['signal_ticker'] or row['ticker'], 'close': m['close'],
                                      'last_fetch_date': m.get('last_fetch_date', ''), 'price_source': m.get('price_source', '')})
                return pd.Series({'role': '사용자 추가', 'prices': [], 'signal_ticker': row['ticker'], 'close': 0.0,
                                  'last_fetch_date': '', 'price_source': ''})
            meta = rebuilt.apply(carry, axis=1)
            rebuilt = pd.concat([rebuilt.reset_index(drop=True), meta.reset_index(drop=True)], axis=1)
            rebuilt['id'] = [str(i) for i in range(len(rebuilt))]
            assets2 = assets[~assets['strategy'].eq(chosen)].copy()
            assets2 = pd.concat([assets2, clean_records(rebuilt)], ignore_index=True)
            st.session_state.assets = assets2; put_state('assets', assets2.to_dict('records'))
            new_cfg = {'code': chosen, 'account': edit_account.strip() or chosen, 'description': edit_desc.strip(), 'dynamic': edit_dynamic, 'active': chosen_cfg.get('active', True), 'annual_limit': edit_limit}
            new_cfgs = [new_cfg if c['code'] == chosen else c for c in cfgs]
            if chosen not in [c['code'] for c in cfgs]: new_cfgs.append(new_cfg)
            put_state('strategies', new_cfgs)
            st.success('저장했습니다.'); toast('전략 구성을 저장했습니다.'); st.rerun()

    st.divider(); st.markdown('### 📊 사용자 정의 벤치마크')
    st.caption('전략 비교 페이지에 표시할 추가 벤치마크입니다. 기본 QQQ·SPY·KOSPI200은 항상 포함됩니다. 표시명과 야후 티커를 입력하세요(예: KODEX 200 → 069500.KS, 나스닥 원화 ETF → 133690.KS).')
    try: saved_cbm = get_state('custom_benchmarks')
    except Exception: saved_cbm = {}
    if not isinstance(saved_cbm, dict): saved_cbm = {}
    bmc1, bmc2 = st.columns(2)
    nb_name = bmc1.text_input('표시명', key='cb_name', placeholder='예: KODEX 200')
    nb_sym = bmc2.text_input('야후 티커', key='cb_sym', placeholder='예: 069500.KS')
    if st.button('벤치마크 추가', key='cb_add'):
        nb_name = nb_name.strip(); nb_sym = nb_sym.strip()
        if not nb_name or not nb_sym:
            st.error('표시명과 티커를 모두 입력하세요.')
        else:
            saved_cbm[nb_name] = nb_sym
            put_state('custom_benchmarks', saved_cbm)
            st.success(f'{nb_name} ({nb_sym}) 벤치마크를 추가했습니다.'); st.rerun()
    if saved_cbm:
        for k, v in list(saved_cbm.items()):
            rc1, rc2 = st.columns([3, 1])
            rc1.caption(f'{k} → {v}')
            if rc2.button('삭제', key=f'cb_del_{k}'):
                saved_cbm.pop(k, None)
                put_state('custom_benchmarks', saved_cbm)
                st.rerun()

    st.divider(); st.markdown('### 히스토리 저장')
    st.caption('현재 모든 전략의 구성·비중·분류를 한 번에 히스토리와 총자산 시계열에 저장합니다.')
    hist_date = st.date_input('저장할 날짜', date.today(), key='hist_save_date')
    _past_date = (pd.Timestamp(hist_date).date() < date.today())
    if _past_date:
        st.caption('과거 날짜로 저장하면 해당 날짜의 종가를 캐시에서 재사용하고(없으면 다시 조회) 그 시점 평가액으로 기록합니다. 조회할 수 없는 종목은 현재 종가로 저장됩니다.')
    if st.button('오늘 날짜로 전체 스냅샷을 히스토리에 저장', type='primary', key='save_snapshot_btn'):
        if _past_date:
            _to_fetch = [i for i, a in assets.iterrows() if str(a['ticker']).strip() and str(a['ticker']).strip() != 'CASH']
            _prog2 = st.progress(0.0, text='과거 날짜 종가 조회 준비 중...')
            for _k, i in enumerate(_to_fetch, 1):
                _a = assets.loc[i]
                _mkt = _a['market'] or 'KR'
                _prog2.progress(min(1.0, (_k - 1) / max(1, len(_to_fetch))), text=f"{_a['ticker']} 종가 조회 중...")
                try:
                    _row = fetch_price_day(_mkt, 'krx', _a['ticker'], hist_date.isoformat(), force_refresh=False)
                    _v = _row.iloc[-1]
                    assets.at[i, 'close'] = _v['close']
                    _hd = str(_v['date'])
                    assets.at[i, 'last_fetch_date'] = f'{_hd[:4]}-{_hd[4:6]}-{_hd[6:]}'
                except Exception:
                    pass
                _prog2.progress(min(1.0, _k / max(1, len(_to_fetch))))
            _prog2.empty()
            st.session_state.assets = assets
        total_saved = save_history_snapshot(assets, hist_date)
        st.success(f'히스토리에 저장했습니다. (총자산 {w(total_saved)})')
        mom = compute_mom_delta()
        if mom:
            arrow = '▲' if mom['total_delta'] >= 0 else '▼'
            st.info(f"직전 저장({mom['prev_date']}) 대비 총자산 {arrow} {w(abs(mom['total_delta']))} ({mom['prev_date']} → {mom['cur_date']})")
        rec = next((x for x in get_state('history') if x['date'] == hist_date.isoformat()), None)
        if rec:
            row, leftover = build_category_row(rec['date'], rec.get('by_category') or {})
            st.markdown('**구글 스프레드시트에 붙여넣을 한 줄** (날짜, 현금, 금, 선진국주식, 신흥국주식, 선진국채권, 신흥국채권)')
            st.code(row, language=None)
            st.caption('복사 버튼을 누르고 시트의 첫 칸에 붙여넣으면 자동으로 열이 나뉩니다.')
            if leftover:
                st.warning('행에 포함되지 않은 분류가 있습니다(0원이 아님): ' + ', '.join(f'{k} {w(v)}' for k, v in leftover.items()))

elif page == '📈 히스토리':
    st.subheader('리밸런싱 히스토리')
    h = get_state('history')
    if not h:
        st.info('아직 저장된 히스토리가 없습니다. 전략 구성 페이지 하단 또는 Action Plan 페이지에서 저장하세요.')
    else:
        hdf = pd.DataFrame(h).sort_values('date').reset_index(drop=True)
        years = sorted({pd.Timestamp(x['date']).year for x in h}, reverse=True)
        f1, f2 = st.columns([1, 2])
        with f1:
            hy = st.selectbox('조회 연도', ['전체'] + years, key='hist_year_v11')
        with f2:
            hint = '전체 기간' if hy == '전체' else f'{hy}년 저장 기록'
            st.caption(f'{hint} · 총 {len(hdf)}회 스냅샷')
        view = hdf if hy == '전체' else hdf[hdf['date'].str.startswith(str(hy))].copy()
        if view.empty:
            st.info('선택한 조건에 저장된 히스토리가 없습니다.')
        else:
            last = view.iloc[-1]; prev = view.iloc[-2] if len(view) >= 2 else None
            k1, k2, k3 = st.columns(3)
            k1.metric('최근 총자산', w(n(last.get('total'))))
            if prev is not None:
                d = n(last.get('total')) - n(prev.get('total'))
                k2.metric('직전 대비', w(abs(d)), delta=('▲ ' if d >= 0 else '▼ ') + w(abs(d)))
            else:
                k2.metric('저장 횟수', f'{len(view)}회')
            k3.metric('최근 저장일', str(last['date']))

            tab1, tab2, tab3, tab4, tab5 = st.tabs(['요약', '전략', '자산군', '스냅샷', '연간 리포트'])
            with tab1:
                mom = compute_mom_delta()
                if mom:
                    st.markdown(f"#### 최근 변화 · {mom['prev_date']} → {mom['cur_date']}")
                    arrow = '▲' if mom['total_delta'] >= 0 else '▼'
                    st.metric('총자산', w(mom['total_cur']), delta=f'{arrow} {w(abs(mom["total_delta"]))}')
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption('전략별 증감'); render_diff_table(mom['by_strategy'])
                    with c2:
                        st.caption('분류별 증감'); render_diff_table(mom['by_category'])
                chart_df = view[['date', 'total']].assign(date=lambda x: pd.to_datetime(x.date)).set_index('date')
                st.line_chart(chart_df['total'])
                if MOBILE:
                    st.markdown('#### 최근 저장 기록')
                    for i in range(len(view)-1, -1, -1):
                        r = view.iloc[i]
                        dtext = ''
                        if i > 0:
                            d = n(r.get('total')) - n(view.iloc[i-1].get('total'))
                            dtext = f' · 직전 대비 {("+" if d >= 0 else "")}{w(d)}'
                        st.markdown(f'<div class="history-card"><div class="history-date">{r["date"]} · {w(n(r.get("total")))}</div><div class="history-sub">{str(r.get("plan") or "저장된 액션플랜 메모 없음")[:100]}{dtext}</div></div>', unsafe_allow_html=True)
                else:
                    _hcols = ['date','total','plan'] + (['saved_at'] if 'saved_at' in view.columns else [])
                    show = view[_hcols].copy(); show['total'] = show['total'].map(w)
                    st.dataframe(show.rename(columns={'date':'날짜','total':'총자산','plan':'액션플랜 메모','saved_at':'마지막 저장'}), use_container_width=True, hide_index=True)

            with tab2:
                by_strat = pd.DataFrame([{**{'date':r['date']}, **(r.get('by_strategy') or {})} for _, r in view.iterrows()])
                if not by_strat.empty:
                    by_strat = by_strat.set_index('date'); by_strat.index = pd.to_datetime(by_strat.index); filled = by_strat.fillna(0)
                    selected = st.multiselect('전략 선택', list(filled.columns), default=list(filled.columns)[:min(3,len(filled.columns))], key='hist_strategy_pick_v11')
                    if selected:
                        st.line_chart(filled[selected])
                        rows=[]
                        for name in selected:
                            vals=filled[name].tolist(); startv=n(vals[0]); endv=n(vals[-1])
                            rows.append({'전략':name,'최근':endv,'기간증감':endv-startv,'기간수익률':(endv/startv-1) if startv>0 else None})
                        sdf=pd.DataFrame(rows)
                        if MOBILE:
                            for _,r in sdf.iterrows():
                                mobile_card(r['전략'], [f'최근 {w(r["최근"])}', f'기간 {w(r["기간증감"])} · {p(r["기간수익률"]) if pd.notna(r["기간수익률"]) else "—"}'], tone='pos' if r['기간증감']>=0 else 'neg')
                        else:
                            sdf['최근']=sdf['최근'].map(w); sdf['기간증감']=sdf['기간증감'].map(w); sdf['기간수익률']=sdf['기간수익률'].map(lambda x:p(x) if pd.notna(x) else '—')
                            st.dataframe(sdf,use_container_width=True,hide_index=True)

            with tab3:
                by_cat = pd.DataFrame([{**{'date':r['date']}, **(r.get('by_category') or {})} for _, r in view.iterrows()])
                if not by_cat.empty:
                    by_cat=by_cat.set_index('date'); by_cat.index=pd.to_datetime(by_cat.index)
                    selected=st.multiselect('자산군 선택',list(by_cat.columns),default=list(by_cat.columns)[:min(4,len(by_cat.columns))],key='hist_cat_pick_v11')
                    if selected: st.line_chart(by_cat[selected].fillna(0))
                    show=by_cat[selected].reset_index() if selected else by_cat.reset_index()
                    for c in show.columns:
                        if c!='date': show[c]=show[c].map(lambda x:w(x) if pd.notna(x) else '—')
                    st.dataframe(show.rename(columns={'date':'날짜'}),use_container_width=True,hide_index=True)

            with tab4:
                pick = st.selectbox('확인할 저장일', list(reversed(view['date'].tolist())), key='history_detail_date_v11')
                rec = next((r for r in h if r['date']==pick), None)
                if rec:
                    c1,c2,c3=st.columns(3); c1.metric('총자산',w(n(rec.get('total')))); c2.metric('전략 수',f'{len(rec.get("by_strategy") or {})}개'); c3.metric('저장일', rec.get('saved_at') or rec['date'])
                    comp=rec.get('composition') or []
                    if comp:
                        cdf=pd.DataFrame(comp)
                        if MOBILE:
                            for strat,g in cdf.groupby('전략'):
                                st.markdown(f'#### {strat}')
                                for _,r in g.iterrows():
                                    render_mobile_target_weight_card(r['ETF'],r['현재비중'],r['목표비중'],r['현재금액'])
                        else:
                            show=cdf.copy(); show['현재금액']=show['현재금액'].map(w); show['현재비중']=show['현재비중'].map(lambda x:f'{x:.1f}%'); show['목표비중']=show['목표비중'].map(lambda x:f'{x:.1f}%'); st.dataframe(show,use_container_width=True,hide_index=True)
                    if rec.get('plan'): st.markdown('#### 저장 당시 Action Plan'); st.info(rec['plan'])
                    exec_recs=[x for x in get_state('executions') if x.get('date')==rec['date']]
                    if exec_recs:
                        st.markdown('#### 계획 대비 실제 실행'); edf=pd.DataFrame(exec_recs); edf['차이']=edf['actual']-edf['planned']; edf['실행']=edf['done'].map(lambda x:'체결' if x else '미체결')
                        for c in ['planned','actual','차이']: edf[c]=edf[c].map(w)
                        st.dataframe(edf[['strategy','ETF','실행','planned','actual','차이']].rename(columns={'strategy':'전략','planned':'계획','actual':'실제'}),use_container_width=True,hide_index=True)
                    row,leftover=build_category_row(rec['date'],rec.get('by_category') or {}); st.markdown('#### 스프레드시트용 한 줄'); st.code(row,language=None)
                    if leftover: st.caption('행에 포함되지 않은 분류: '+', '.join(f'{k} {w(v)}' for k,v in leftover.items()))
                    st.markdown('#### 스냅샷 관리')
                    _h_opts = list(reversed([x['date'] for x in h]))
                    _hc1, _hc2 = st.columns([2, 1])
                    with _hc1:
                        _del_date = st.selectbox('삭제할 날짜(히스토리·총자산 시계열에서 함께 제거)', ['(선택 안 함)'] + _h_opts, key='hist_del_pick')
                    with _hc2:
                        _del_confirm = st.checkbox('삭제 확인', key='hist_del_confirm')
                    if _del_date != '(선택 안 함)' and _del_date is not None:
                        if st.button('🗑 해당 날짜 히스토리 삭제', key='hist_del_btn', disabled=not _del_confirm):
                            h2 = [x for x in h if x['date'] != _del_date]
                            put_state('history', h2)
                            e2 = [x for x in get_state('equity') if x['date'] != _del_date]
                            put_state('equity', e2)
                            st.success(f'{_del_date} 기록을 삭제했습니다.'); st.rerun()

            with tab5:
                years_avail=sorted({pd.Timestamp(r['date']).year for r in h},reverse=True)
                ry=st.selectbox('연도 선택',years_avail,key='report_year_v11')
                year_recs=sorted([r for r in h if pd.Timestamp(r['date']).year==ry],key=lambda x:x['date'])
                if year_recs:
                    first_rec,last_rec=year_recs[0],year_recs[-1]; total_start=n(first_rec.get('total')); total_end=n(last_rec.get('total')); delta=total_end-total_start
                    c1,c2,c3=st.columns(3); c1.metric('시작',w(total_start)); c2.metric('종료',w(total_end),delta=w(delta)); mm=portfolio_perf([{'date':r['date'],'value':n(r.get('total'))} for r in year_recs]); c3.metric('기간 MDD',p(mm[1]) if mm else '—')
                    st.line_chart(pd.DataFrame([{'date':r['date'],'value':n(r.get('total'))} for r in year_recs]).assign(date=lambda x:pd.to_datetime(x.date)).set_index('date')['value'])
                    rows=[]
                    for code in sorted(set((first_rec.get('by_strategy') or {}).keys()) | set((last_rec.get('by_strategy') or {}).keys())):
                        s0=n((first_rec.get('by_strategy') or {}).get(code,0)); s1=n((last_rec.get('by_strategy') or {}).get(code,0)); rows.append({'전략':code,'연초':w(s0),'연말':w(s1),'증감':w(s1-s0)})
                    if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

    st.divider()
    st.markdown('### 백업 · 복원')
    st.caption(f'현재 DB 파일 위치: `{DB_PATH}` — app.py를 다른 폴더로 옮겨도 이 경로는 바뀌지 않습니다.')
    st.info('⚠️ **app.py를 업데이트(코드 교체·재배포)하기 전에는 항상 먼저 "JSON 백업 다운로드"를 눌러 파일을 저장해두세요.** 업데이트 후 데이터가 비어 있으면 "JSON 백업 파일로 복원"으로 그대로 되살릴 수 있습니다.')
    bc1, bc2 = st.columns(2)
    with bc1:
        st.caption('JSON 백업에는 보유수량·전략 구성 등은 저장하지만 종가(close)와 가격이력(prices)은 저장하지 않습니다.')
        st.download_button('JSON 백업 다운로드', json.dumps(export_backup_dict(), ensure_ascii=False, indent=2, default=str), file_name=f'portfolio-backup-{date.today().isoformat()}.json', mime='application/json')
        if h:
            st.download_button('CSV 히스토리(요약)', pd.DataFrame(h).drop(columns=['composition', 'by_strategy', 'by_category'], errors='ignore').to_csv(index=False), file_name='rebalance-history.csv', mime='text/csv')
        backup_dir = Path.home() / '.asset_allocation_app' / 'backups'
        auto_files = sorted(backup_dir.glob('backup-*.json')) if backup_dir.exists() else []
        if auto_files:
            st.caption(f'매달 스냅샷 저장 시 자동으로도 백업됩니다 (최근 {len(auto_files)}개 보관 중, 최신: {auto_files[-1].name}). 이 파일은 앱이 로컬에서 계속 실행되는 동안만 남아있습니다.')
    with bc2:
        st.markdown('**JSON 백업 복원**')
        st.caption('복원 시 JSON 안에 close/prices가 있더라도 무시하며, 가격은 선택한 기준일에 새로 조회합니다.')
        st.caption('파일 선택이 브라우저에서 오류가 날 경우 아래의 JSON 직접 붙여넣기를 사용해도 됩니다.')
        restore_mode = st.radio('복원 방식', ['JSON 직접 붙여넣기', '파일 선택'], horizontal=True, key='restore_mode')
        restore_text = ''
        if restore_mode == '파일 선택':
            up = st.file_uploader('JSON 백업 파일 선택', type=['json'], key='restore_upload', help='Streamlit 파일 선택기가 정상적으로 로드되는 경우 사용합니다.')
            if up is not None:
                try:
                    restore_text = up.getvalue().decode('utf-8-sig')
                except Exception as e:
                    st.error(f'파일을 읽지 못했습니다: {e}')
        else:
            restore_text = st.text_area('JSON 내용 붙여넣기', height=180, key='restore_json_text', placeholder='{\n  "assets": [...],\n  "strategies": [...]\n}')

        if restore_text.strip():
            st.warning('복원하면 현재 저장된 데이터를 덮어씁니다.')
            if st.button('이 백업으로 복원', type='primary', key='restore_btn'):
                try:
                    data = json.loads(restore_text.lstrip('\ufeff'))
                    if not isinstance(data, dict):
                        raise ValueError('JSON 최상위 구조가 객체(dict)가 아닙니다.')
                    restored, skipped = [], []
                    for k in ALL_KV_KEYS:
                        if k in data:
                            value = data[k]
                            if k in ('assets','history','equity','cashflows','benchmarks','strategies','category_targets','executions') and not isinstance(value, (list, dict)):
                                raise ValueError(f'{k} 항목의 형식이 올바르지 않습니다.')
                            if k == 'assets':
                                # v8부터는 새 백업뿐 아니라 과거 백업을 복원할 때도
                                # stale close/prices를 가져오지 않는다. 가격은 선택일에 다시 조회한다.
                                value = strip_asset_price_data(value)
                            put_state(k, value); restored.append(k)
                        else:
                            skipped.append(k)
                    st.session_state.pop('assets', None)
                    a_count = len(data.get('assets', [])) if isinstance(data.get('assets', []), list) else 0
                    s_count = len(data.get('strategies', [])) if isinstance(data.get('strategies', []), list) else 0
                    h_count = len(data.get('history', [])) if isinstance(data.get('history', []), list) else 0
                    st.success(f'복원했습니다 — 전략 {s_count}개, 종목 {a_count}개, 히스토리 {h_count}건.')
                    toast('백업에서 복원했습니다.')
                    if skipped: st.caption(f'백업 파일에 없어 건너뛴 항목: {", ".join(skipped)} (이전 버전 백업이면 정상입니다)')
                    st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f'JSON 형식이 올바르지 않습니다: {e}')
                except Exception as e:
                    st.error(f'복원 실패: {e}')

    st.divider()
    with st.expander('🛠️ 고급 · 문제 해결', expanded=False):
        st.markdown('### 가격 캐시', help=PRICE_DATA_HELP)
        init_db(); _con = sqlite3.connect(DB_PATH)
        _n_cached = _con.execute('SELECT COUNT(*) FROM price_cache').fetchone()[0]
        _n_tickers = _con.execute('SELECT COUNT(DISTINCT ticker) FROM price_cache').fetchone()[0]
        _con.close()
        st.caption(f'캐시된 가격 데이터: 종목 {_n_tickers}개 · {_n_cached:,}개 날짜. 지나간 달/과거 거래일은 캐시에서 재사용하고, 새로 생긴 날짜만 조회합니다.')
        _fxd2, _fxr2, _fxs2 = cache_fx_latest()
        if _fxd2:
            st.caption(f'USD/KRW 가장 최근 캐시: {_fxd2} · {num0(_fxr2)}원 · {_fxs2 or "—"}')
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button('🗑️ 가격 캐시 전체 삭제', use_container_width=True):
                cache_clear_prices()
                st.success('SQLite 가격 캐시와 Yahoo 런타임 캐시를 함께 삭제했습니다.')
        with cc2:
            if st.button('♻️ 가격 조회 캐시만 초기화', use_container_width=True):
                clear_all_price_caches()
                st.success('Streamlit 가격 조회 캐시를 초기화했습니다. DB의 과거 가격은 유지됩니다.')
        st.caption('값이 의심될 때만 사용하세요: 조회 캐시 초기화 → 강제 새로고침 → 필요하면 전체 캐시 삭제 순서입니다.')

else:  # ⚖️ 전략 비교
    st.subheader('전략별 성과 비교')
    e = get_state('equity'); cf = get_state('cashflows')
    if not e:
        st.info('아직 총자산 히스토리가 없습니다. 설정에서 스냅샷을 저장하면 여기 반영됩니다.')
    # 비교 구간 선택 (기준일 = 마지막 저장일)
    _last_date = sorted(e, key=lambda x: x['date'])[-1]['date'] if e else None
    _cut = None
    if _last_date:
        _today = pd.Timestamp(_last_date)
        _range_opt = st.radio('비교 구간', ['전체', '1년', '6개월', '3개월', '1개월', 'YTD'], horizontal=True, index=0, key='perf_range')
        if _range_opt == '1년': _cut = _today - pd.Timedelta(days=365)
        elif _range_opt == '6개월': _cut = _today - pd.Timedelta(days=182)
        elif _range_opt == '3개월': _cut = _today - pd.Timedelta(days=91)
        elif _range_opt == '1개월': _cut = _today - pd.Timedelta(days=31)
        elif _range_opt == 'YTD': _cut = pd.Timestamp(f'{_today.year}-01-01')
    def _slice(rows):
        if not rows or _cut is None: return rows
        return [r for r in rows if pd.Timestamp(r['date']) >= _cut]
    m = portfolio_perf(_slice(e)); irr = calc_xirr(_slice(e), cf); twr = calc_twr(_slice(e), cf)
    a, b, c, d = st.columns(4)
    a.metric('CAGR', p(m[0]) if m else '—'); b.metric('MDD', p(m[1]) if m else '—')
    c.metric('IRR/XIRR', p(irr) if irr is not None else '—'); d.metric('TWR(자금흐름 제거)', p(twr) if twr is not None else '—')
    st.caption('XIRR은 실제 돈의 성장(입출금 시점 반영), TWR은 투자 결정의 성과(입출금 효과 제거)입니다. 둘을 함께 보세요.')
    st.caption('IRR 계산 규칙: 마지막 저장일과 같은 날짜의 입출금은 평가액에 이미 반영된 것으로 보고 XIRR에서 제외합니다. 전략 태그가 없는 입출금은 전체 XIRR에만 반영되고 연간 한도 추적·전략별 IRR에는 포함되지 않습니다.')
    if e: st.line_chart(pd.DataFrame(_slice(e)).assign(date=lambda x: pd.to_datetime(x.date)).set_index('date')['value'])

    st.divider(); st.subheader('벤치마크 (자동 조회)')
    st.caption('기본 QQQ·SPY·KOSPI200 + 설정에서 추가한 사용자 정의 벤치마크를 불러옵니다. 히스토리 저장 시 신규 날짜는 자동으로 백필됩니다.')
    _krw_toggle = st.toggle('원화 환산 비교 (USD 벤치마크에 환율 반영)', value=False, key='bench_krw_toggle', help='환투자 수익이 벤치마크에 반영됩니다.')
    _tr_toggle = st.toggle('배당재투자 기준(TR) 비교', value=False, key='bench_tr_toggle', help='미국 벤치마크를 배당 재투자 기준 수정주가(adjclose)로 계산합니다(총수익 비교). 수정주가가 없는 종목은 원시 종가로 자동 전환됩니다.')
    if st.button('히스토리 날짜 기준 벤치마크 자동 채우기(누락분)', type='primary'):
        existing = get_state('benchmarks'); dates = sorted({x['date'] for x in e}); added = 0; errs = []
        for dt in dates:
            for name, sym in get_bench_symbols().items():
                if any(x['name'] == name and x['date'] == dt for x in existing): continue
                try:
                    row = fetch_yahoo_day(sym, dt)
                    rec = {'name': name, 'date': dt, 'value': float(row.iloc[-1]['close'])}
                    if 'adjclose' in row.columns and n(row.iloc[-1].get('adjclose')) > 0:
                        rec['adjclose'] = float(n(row.iloc[-1]['adjclose']))
                    existing.append(rec); added += 1
                except Exception as ex:
                    errs.append(f'{name} {dt}: {ex}')
        put_state('benchmarks', existing); st.success(f'{added}개 벤치마크 값을 채웠습니다.')
        if errs: st.warning(' / '.join(errs[:5]))
        st.rerun()

    bench_all = get_state('benchmarks')
    _fx_series = {}
    if _krw_toggle and e:
        for _dt in sorted({x['date'] for x in e}):
            _r = get_usd_krw_rate(_dt)
            if _r: _fx_series[_dt] = _r
    series = {}
    if e:
        first = sorted(e, key=lambda x: x['date'])[0]['date']; base = sorted(e, key=lambda x: x['date'])[0]['value']
        if base > 0:
            series['내 포트폴리오'] = [{'date': x['date'], 'value': x['value'] / base * 100} for x in _slice(e)]
            for name in get_bench_symbols().keys():
                z = sorted([x for x in bench_all if x['name'] == name and x['date'] >= first], key=lambda x: x['date'])
                if not z: continue
                def _bv(x):
                    if _tr_toggle:
                        av = n(x.get('adjclose'))
                        if av > 0: return av
                    return n(x.get('value'))
                raw = [{'date': x['date'], 'val': _bv(x)} for x in z]
                raw = [r for r in raw if r['val'] > 0]
                if not raw: continue
                base_v = raw[0]['val']
                vals = [{'date': r['date'], 'value': r['val'] / base_v * 100} for r in raw]
                if _krw_toggle:
                    _r0 = _fx_series.get(raw[0]['date'])
                    if _r0:
                        _lastr = _r0; norm = []
                        for r in raw:
                            _rx = _fx_series.get(r['date'], _lastr)
                            if _rx: _lastr = _rx
                            norm.append({'date': r['date'], 'value': (r['val'] / base_v) * (_lastr / _r0) * 100})
                        vals = norm
                series[name] = vals
        else:
            st.caption('첫 저장된 총자산이 0원이라 벤치마크 대비 비교는 아직 계산할 수 없습니다. 보유수량·종가를 입력한 뒤 다시 저장해보세요.')
    if series:
        chart = pd.concat([pd.DataFrame(v).assign(date=lambda x: pd.to_datetime(x.date)).set_index('date').rename(columns={'value': k}) for k, v in series.items()], axis=1).sort_index().ffill()
        st.line_chart(chart)
        _rows = []
        _port_period = None
        for name, vals in series.items():
            mm = portfolio_perf(vals)
            _dd, _dd_len, _rec_len = mdd_details(vals)
            _sor = sortino_ratio(vals)
            _per = (vals[-1]['value'] / vals[0]['value'] - 1) if vals and vals[0]['value'] > 0 else None
            if name == '내 포트폴리오': _port_period = _per
            _rel = None
            if name != '내 포트폴리오' and _port_period is not None and _per is not None:
                _rel = _port_period - _per
            _rows.append({'항목': name,
                          'CAGR': p(mm[0]) if mm and mm[0] is not None else '—',
                          '기간수익률': p(_per) if _per is not None else '—',
                          '상대(내-벤치)': p(_rel) if _rel is not None else '—',
                          'MDD': p(mm[1]) if mm and mm[1] is not None else '—',
                          'MDD기간(일)': (_dd_len if _dd_len is not None else '—'),
                          '회복(일)': (_rec_len if _rec_len is not None else '—'),
                          '변동성': p(mm[2]) if mm and mm[2] is not None else '—',
                          '샤프': f'{mm[3]:.2f}' if mm and mm[3] is not None else '—',
                          '소르티노': f'{_sor:.2f}' if _sor is not None else '—'})
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
        _por_irr = calc_xirr(_slice(e), cf)
        if _por_irr is not None:
            _b_recs = [(x['date'], n(x['value'])) for x in bench_all if x['name'] == 'QQQ']
            _b_irr = benchmark_attributed_xirr(_b_recs, cf, _last_date or date.today().isoformat())
            if _b_irr is not None:
                st.info(f"동일 입출금을 벤치마크(QQQ)에 넣었다면 XIRR ≈ {p(_b_irr)} — 내 XIRR {p(_por_irr)} 대비 비교해보세요.")

    st.divider(); st.subheader('전략별 성과 비교')
    st.caption('전략을 같은 시작점(100)으로 정규화해 비교합니다(위에서 고른 구간 적용). 아래에서 전략과 벤치마크를 선택하세요.')
    h_hist = get_state('history')
    by_strat_series = {}
    for rec in sorted(h_hist, key=lambda x: x['date']):
        for strat, val in (rec.get('by_strategy') or {}).items():
            by_strat_series.setdefault(strat, []).append({'date': rec['date'], 'value': val})
    if by_strat_series:
        avail_strats = sorted(by_strat_series.keys())
        picked_strats = st.multiselect('비교할 전략', avail_strats, default=avail_strats[:min(3, len(avail_strats))], key='perf_strategy_pick_v11')
        if picked_strats:
            strat_series = {}
            for strat in picked_strats:
                vals = sorted(_slice(by_strat_series[strat]), key=lambda x: x['date'])
                if vals and vals[0]['value'] > 0:
                    base2 = vals[0]['value']
                    strat_series[strat] = [{'date': v['date'], 'value': v['value'] / base2 * 100} for v in vals]
            combined = dict(strat_series)
            for name in get_bench_symbols().keys():
                if name in series: combined[name] = series[name]
            if combined:
                chart2 = pd.concat([pd.DataFrame(v).assign(date=lambda x: pd.to_datetime(x.date)).set_index('date').rename(columns={'value': k}) for k, v in combined.items()], axis=1).sort_index().ffill()
                st.line_chart(chart2)
            _srows = []
            for strat in picked_strats:
                vals = sorted(_slice(by_strat_series[strat]), key=lambda x: x['date'])
                mm = portfolio_perf(vals)
                strat_cf = [c for c in cf if c.get('strategy') == strat]
                irr2 = calc_xirr(vals, strat_cf) if strat_cf else None
                twr2 = calc_twr(vals, strat_cf or [])
                _srows.append({'전략': strat,
                               'CAGR': p(mm[0]) if mm and mm[0] is not None else '—',
                               'MDD': p(mm[1]) if mm and mm[1] is not None else '—',
                               'IRR': p(irr2) if irr2 is not None else '(입출금 태그 없음)',
                               'TWR': p(twr2) if twr2 is not None else '—'})
            st.dataframe(pd.DataFrame(_srows), use_container_width=True, hide_index=True)
            _bets = {name: vals for name, vals in series.items() if name != '내 포트폴리오'}
            if '내 포트폴리오' in series and _bets:
                _beta_name = next(iter(_bets.keys()))
                _ba, _al = beta_alpha(series['내 포트폴리오'], _bets[_beta_name])
                if _ba is not None:
                    st.caption(f'내 포트폴리오 vs {_beta_name}: 베타 {_ba:.2f} · 구간 알파 {p(_al) if _al is not None else "—"}')
    else:
        st.caption('히스토리에 저장된 전략별 데이터가 아직 없습니다 (전략 구성 페이지에서 스냅샷을 저장하면 쌓입니다).')

    st.divider(); st.subheader('입출금 원장')
    st.caption('전략(계좌)을 지정하면 연금저축/ISA 납입한도 추적과 전략별 벤치마크 비교에 쓰입니다. 지정하지 않으면 전체 포트폴리오 성과 계산에만 반영됩니다.')
    cf_codes = ['(지정 안 함)'] + strategy_codes()
    cd = st.date_input('거래일', date.today(), key='cd'); ca = st.number_input('금액(입금 + / 출금 -)', step=100000.0, key='ca')
    cstrat = st.selectbox('전략(계좌)', cf_codes, key='cstrat'); cm = st.text_input('메모', key='cm')
    if st.button('입출금 저장'):
        x = get_state('cashflows')
        x.append({'date': cd.isoformat(), 'amount': ca, 'memo': cm, 'strategy': '' if cstrat == '(지정 안 함)' else cstrat})
        put_state('cashflows', x); st.success('저장했습니다.'); toast('입출금을 저장했습니다.')
    cf_list_raw = get_state('cashflows')
    for _r in cf_list_raw:
        if 'memo' not in _r: _r['memo'] = ''
        if 'strategy' not in _r: _r['strategy'] = ''
    cf_df = pd.DataFrame(cf_list_raw)
    cf_show = cf_df.copy()
    if not cf_show.empty:
        if 'strategy' not in cf_show: cf_show['strategy'] = ''
        cf_show['amount'] = cf_show['amount'].map(lambda x: f'{n(x):,.0f}원')
    if not cf_show.empty:
        st.caption('표에서 직접 수정하고 저장할 수 있습니다. 날짜(YYYY-MM-DD)·금액(입금 + / 출금 -)·전략·메모.')
        cf_edit = st.data_editor(
            cf_show, num_rows='dynamic', use_container_width=True, hide_index=True,
            column_config={
                'date': st.column_config.TextColumn('날짜(YYYY-MM-DD)'),
                'amount': st.column_config.TextColumn('금액'),
                'strategy': st.column_config.TextColumn('전략'),
                'memo': st.column_config.TextColumn('메모'),
            },
        )
        if st.button('입출금 표 저장(수정 반영)', key='cf_save_edit'):
            new_list = []
            ok = True
            for _, row in cf_edit.iterrows():
                try:
                    amt = float(str(row['amount']).replace(',', '').replace('원', '').strip())
                except (TypeError, ValueError):
                    amt = float('nan')
                if pd.isna(amt):
                    ok = False; break
                d_str = str(row['date']).strip()
                try:
                    pd.Timestamp(d_str)
                except Exception:
                    ok = False; break
                new_list.append({'date': d_str, 'amount': amt, 'memo': str(row.get('memo') or ''), 'strategy': str(row.get('strategy') or '')})
            if ok:
                put_state('cashflows', new_list); st.success('입출금 원장을 저장했습니다.'); st.rerun()
            else:
                st.error('날짜(YYYY-MM-DD) 또는 금액 형식을 확인하세요. 저장하지 않았습니다.')
    else:
        st.caption('아직 입출금 기록이 없습니다. 위에서 추가하거나 아래 CSV/정기납입으로 불러올 수 있습니다.')
    with st.expander('벌크 입력 · 정기납입 자동 생성', expanded=False):
        st.caption('CSV 형식: date,amount,memo,strategy (첫 줄 헤더). amount는 입금 + / 출금 -.')
        up_csv = st.file_uploader('입출금 CSV 업로드(추가)', type=['csv'], key='cf_csv')
        if up_csv is not None:
            try:
                df_in = pd.read_csv(up_csv)
                if {'date', 'amount'}.issubset(df_in.columns):
                    if st.button('CSV 기록 추가', key='cf_csv_add'):
                        cur = get_state('cashflows')
                        for _, row in df_in.iterrows():
                            try:
                                amt = float(row['amount'])
                                d_str = pd.Timestamp(str(row['date'])).strftime('%Y-%m-%d')
                            except Exception:
                                continue
                            cur.append({'date': d_str, 'amount': amt, 'memo': str(row.get('memo') or ''), 'strategy': str(row.get('strategy') or '')})
                        put_state('cashflows', cur); st.success(f'{len(df_in)}건 추가했습니다.'); st.rerun()
                else:
                    st.warning('CSV에 date, amount 열이 있어야 합니다.')
            except Exception as e:
                st.error(f'CSV를 읽지 못했습니다: {e}')
        st.markdown('**정기납입 자동 생성**')
        rc1, rc2, rc3, rc4 = st.columns(4)
        _cf_start = rc1.date_input('시작일', date.today(), key='cf_start')
        _cf_months = rc2.number_input('개월 수', min_value=1, max_value=120, value=12, key='cf_months')
        _cf_amt = rc3.number_input('월 납입액', step=100000.0, value=1000000.0, key='cf_amt')
        _cf_strat = rc4.selectbox('전략', cf_codes, key='cf_strat')
        if st.button('정기납입 기록 생성(추가)', key='cf_recur_add'):
            cur = get_state('cashflows')
            s = pd.Timestamp(_cf_start)
            added = 0
            for k in range(int(_cf_months)):
                d_str = (s + pd.DateOffset(months=k)).strftime('%Y-%m-%d')
                if any(x['date'] == d_str and abs(n(x.get('amount')) - n(_cf_amt)) < 1 and x.get('strategy') == ('' if _cf_strat == '(지정 안 함)' else _cf_strat) for x in cur):
                    continue
                cur.append({'date': d_str, 'amount': float(_cf_amt), 'memo': '정기납입', 'strategy': '' if _cf_strat == '(지정 안 함)' else _cf_strat})
                added += 1
            put_state('cashflows', cur); st.success(f'{added}건 추가했습니다.'); st.rerun()
    _cf_list = get_state('cashflows')
    if _cf_list:
        _cf_opts = [f"{i}: {x['date']} {w(x['amount'])} {str(x.get('memo', ''))}".strip() for i, x in enumerate(_cf_list)]
        _cf_del = st.selectbox('삭제할 입출금 기록', _cf_opts, key='cf_del')
        if st.button('선택 기록 삭제', key='cf_del_btn'):
            _cf_list.pop(int(_cf_del.split(':', 1)[0]))
            put_state('cashflows', _cf_list)
            st.success('삭제했습니다.'); st.rerun()