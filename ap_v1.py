import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import yfinance as yf
import re
import ast

import streamlit as st

import streamlit as st

# --- ここから追加：スマホ＆iPad向けのサイズ調整 ---
st.markdown(
    """
    <style>
    /* 1. スマホ向けの調整 (画面幅 640px 以下) */
    @media (max-width: 640px) {
        html { font-size: 14px; }
        .block-container { padding: 1rem !important; }
    }

    /* 2. iPad/タブレット向けの調整 (画面幅 641px 〜 1024px) */
    @media (min-width: 641px) and (max-width: 1024px) {
        html {
            /* 全体的なフォントサイズをガッツリ下げる */
            font-size: 12px; 
        }
        /* 画面全体を60%スケールにするイメージで余白や要素を調整 */
        .block-container {
            max-width: 60% !important; /* コンテンツ幅を絞る */
            margin: 0 auto;
        }
        /* ボタンやグラフなどもさらにコンパクトに */
        .stButton button, .stSelectbox, .stTextInput input {
            transform: scale(0.8); /* 要素自体を少し縮小 */
            transform-origin: left;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)
# --- ここまで追加 ---


st.title("マイアプリ")
# 以下、元のコード...

# --- 0. ページ設定・カスタムCSS ---
st.set_page_config(page_title="資産運用シミュレーター V2", layout="wide")
st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"] { overflow: hidden !important; height: 100vh; }
    .block-container { padding-top: 3.5rem !important; max-width: 99% !important; }
    
    /* サイドバーの余白調整 */
    div[data-testid="stSidebarUserContent"] { padding-top: 1rem !important; }

    /* 銘柄ボタン：左寄せ・省略設定（完璧版） */
    div.stButton > button { 
        justify-content: flex-start !important; 
        text-align: left !important; 
        padding-left: 10px !important;
        width: 100% !important;
        height: 32px !important; 
        font-size: 0.82rem !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    /* 各種テキスト表示設定 */
    .list-text { font-weight: bold; font-size: 0.85rem; text-align: right; width: 100%; line-height: 32px; }
    .status-tag { display: inline-block; font-size: 0.7rem; padding: 1px 5px; border-radius: 4px; font-weight: bold; text-align: center; }
    .tag-nisa { background-color: #E1F5FE; color: #03A9F4; border: 1px solid #03A9F4; }
    .tag-tokutei { background-color: #F5F5F5; color: #9E9E9E; border: 1px solid #9E9E9E; }
    .amt_heavy-plus { color: #28B463; font-weight: bold; font-size: 0.85rem; }
    .amt_heavy-minus { color: #E74C3C; font-weight: bold; font-size: 0.85rem; }
    .profit-plus { color: #28B463; font-weight: bold; }
    .profit-minus { color: #E74C3C; font-weight: bold; }
    .change-label { font-size: 0.65rem; color: #7F8C8D; display: block; line-height: 1.1; }
    .warning-box { background-color: #FDEDEC; border: 1px solid #E74C3C; color: #E74C3C; padding: 8px; border-radius: 5px; font-weight: bold; text-align: center; margin: 5px 0; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. 定数・関数定義 ---
CAT_ORDER = ["日本株", "外国株", "投資信託", "現金"]
COLOR_MAP = {"日本株": "#FFD1DC", "外国株": "#D1E9FF", "投資信託": "#D1FFD1", "現金": "#E0E0E0"}
JP_SECTORS = ["情報・通信業", "サービス業", "医薬品", "銀行業", "小売業", "卸売業", "機械", "電気機器", "輸送用機器", "不動産業", "建設業", "化学", "食料品", "鉄鋼", "保険業", "その他金融業", "その他製品"]
US_SECTORS = ["テクノロジー", "金融", "ヘルスケア", "一般消費財", "生活必需品", "エネルギー", "公益事業", "不動産", "素材", "資本財", "通信サービス"]
SENSITIVITY_MAP = {
    "ディフェンシブ": ["医薬品", "食料品", "情報・通信業", "サービス業", "小売業", "ヘルスケア", "生活必需品", "公益事業", "通信サービス"],
    "景気敏感": ["機械", "電気機器", "輸送用機器", "鉄鋼", "化学", "不動産業", "素材", "資本財", "金融", "エネルギー", "銀行業", "その他金融業"],
    "中立/現金": ["現金", "建設業", "不動産", "その他製品", "投資信託"]
}

def clean_name(n): return re.sub(r'特定|ＮＩＳＡ|NISA|USD|EUR|MXN|HKD|AUD|/|^\d+\s*', '', str(n)).strip() if not pd.isna(n) else ""
def extract_code(v): m = re.search(r'([A-Z0-9]{4,})', str(v)); return m.group(1) if m else ""
def get_sensitivity(s):
    for cat, sectors in SENSITIVITY_MAP.items():
        if s in sectors: return cat
    return "中立/現金"

@st.cache_data(ttl=3600)
def get_live_rate():
    try: return round(yf.Ticker("USDJPY=X").history(period="1d")['Close'].iloc[-1], 2)
    except: return 150.0

def calc_dividend(d, q, cur, cat, nisa, ex, mode):
    if cat == '現金': return 0.0
    r = 1.0 if cur == 'JPY' else ex
    adj = 10000.0 if cat == '投資信託' else 1.0
    raw = (d * q * r) / adj
    if mode == "税引前": return raw
    return raw * ((0.9 if cur == 'USD' else 1.0) if nisa else 0.79685)

if 'portfolio_list' not in st.session_state: st.session_state.portfolio_list = []
if 'edit_index' not in st.session_state: st.session_state.edit_index = None
if 'saved_sims' not in st.session_state: st.session_state.saved_sims = [{"data": None, "note": ""} for _ in range(3)]
# --- 2. サイドバー (確実なタイトル表示・統合インポート) ---
st.sidebar.header("🎯 基本設定")
tax_mode = st.sidebar.radio("配当表示設定", ["税引後", "税引前"], horizontal=True, key="tax_mode_v22")
target_asset_man = st.sidebar.number_input("目標総資産(万円)", value=3000, step=100)
target_monthly_div_man = st.sidebar.number_input("目標月配当(万円)", value=10.0, step=0.5)

st.sidebar.divider()

# 枠のすぐ上に日本語タイトルを表示（これが最も確実です）
st.sidebar.markdown("### 1. 保有銘柄csv")
rakuten_file = st.sidebar.file_uploader("楽天証券からダウンロードしたCSV", type="csv", label_visibility="collapsed")

st.sidebar.markdown("### 2. データ保存csv")
setting_file = st.sidebar.file_uploader("以前保存したシミュレーションCSV", type="csv", label_visibility="collapsed")

st.sidebar.markdown("### 3. 配当csv")
div_file = st.sidebar.file_uploader("銘柄名,コード,配当金,入金日のCSV", type="csv", label_visibility="collapsed")

if st.sidebar.button("データを反映して統合", type="primary", use_container_width=True):
    merged = {}
    
    # A. 保有銘柄CSVの解析
    if rakuten_file:
        try:
            content = rakuten_file.read().decode('cp932')
            lines = content.splitlines()
            h_idx = next((i for i, l in enumerate(lines) if '種別' in l and '銘柄' in l), -1)
            if h_idx != -1:
                df_r = pd.read_csv(io.StringIO("\n".join(lines[h_idx:])), header=0)
                for _, row in df_r.iterrows():
                    rt, raw_n = str(row.iloc[0]), str(row.iloc[2]).strip()
                    if any(x in raw_n for x in ["円/", "nan", "合計", "資産合計"]): continue
                    qty = float(str(row.iloc[4]).replace(',','') or 0)
                    if qty <= 0: continue
                    
                    if '投資信託' in rt or '投信' in rt: cat = '投資信託'
                    elif '外国株式' in rt or '米国株式' in rt or 'USD' in raw_n: cat = '外国株'
                    else: cat = '日本株'
                    
                    name, code = clean_name(raw_n), extract_code(row.iloc)
                    merged[name] = {
                        '銘柄名':name, 'コード':code, 'カテゴリー':cat, 'セクター':cat,
                        '現在価格':float(str(row.iloc[8]).replace(',','') or 0), '保有数量':qty,
                        '取得単価':float(str(row.iloc[6]).replace(',','') or 0), '現状1株配当':0.0,
                        '変更単価':float(str(row.iloc[8]).replace(',','') or 0), '変更数量':0.0, '変更1株配当':0.0,
                        'currency':'USD' if cat == '外国株' else 'JPY', 'is_nisa':'NISA' in str(row.iloc[3]), 'div_schedule_v2':[]
                    }
        except Exception: st.sidebar.error("保有銘柄CSVの読み込みに失敗しました。")

    # B. 保存済みデータの復元
    if setting_file:
        try:
            df_s = pd.read_csv(io.StringIO(setting_file.read().decode('utf-8-sig')))
            for _, row in df_s.iterrows():
                nm = clean_name(row['銘柄名'])
                it = row.to_dict()
                if 'div_schedule_v2' in it and isinstance(it['div_schedule_v2'], str):
                    it['div_schedule_v2'] = ast.literal_eval(it['div_schedule_v2'])
                merged[nm] = it
        except Exception: st.sidebar.error("データ保存CSVの読み込みに失敗しました。")

    # C. 配当CSVの反映 (最強ロジック)
    if div_file and merged:
        try:
            raw_d = div_file.read()
            try: df_div = pd.read_csv(io.BytesIO(raw_d), encoding='utf-8-sig')
            except: df_div = pd.read_csv(io.BytesIO(raw_d), encoding='cp932')
            
            c_code = next((c for c in df_div.columns if 'コード' in c or 'code' in c.lower()), None)
            c_amt = next((c for c in df_div.columns if '配当金' in c or '金額' in c), None)
            c_date = next((c for c in df_div.columns if '日' in c or '月' in c), None)
            c_name = next((c for c in df_div.columns if '銘柄' in c or '名称' in c), None)
            
            for k in merged: merged[k]['div_schedule_v2'] = []
            m_count = 0
            for _, d_row in df_div.iterrows():
                d_code = str(d_row.get(c_code, '')).split('.')[0].strip()
                d_name = clean_name(d_row.get(c_name, ''))
                target = next((k for k, v in merged.items() if (d_code and d_code != "nan" and str(v.get('コード')) == d_code) or k == d_name), None)
                if target:
                    amt_v = float(re.sub(r'[^\d.]', '', str(d_row.get(c_amt, 0))) or 0)
                    dt = str(d_row.get(c_date, ''))
                    m_match = re.search(r'(\d{1,2})', dt.split('/')[-2] if '/' in dt and len(dt.split('/')) > 1 else dt)
                    m_val = int(m_match.group(1)) if m_match else 1
                    if len(merged[target]['div_schedule_v2']) < 4:
                        merged[target]['div_schedule_v2'].append({"amount": amt_v, "months": [m_val]})
                        m_count += 1
            for k in merged:
                merged[k]['現状1株配当'] = sum(s['amount'] * len(s['months']) for s in merged[k]['div_schedule_v2'])
                merged[k]['変更1株配当'] = merged[k]['現状1株配当']
            st.sidebar.success(f"配当情報を {m_count}件 反映しました")
        except Exception: st.sidebar.error("配当CSVの反映に失敗しました")
    
    if merged: st.session_state.portfolio_list = list(merged.values()); st.rerun()

st.session_state['ex_rate_v22'] = get_live_rate()
if st.session_state.portfolio_list:
    csv_out = pd.DataFrame(st.session_state.portfolio_list).to_csv(index=False).encode('utf-8-sig')
    st.sidebar.download_button("📩 現在の全データをCSV保存", data=csv_out, file_name="my_portfolio.csv", use_container_width=True)
# --- 2.2 計算ロジック・ダイアログ ---
def get_current_df(tax_mode="税引後"):
    if not st.session_state.portfolio_list: return pd.DataFrame()
    d = pd.DataFrame(st.session_state.portfolio_list)
    ex = st.session_state.get('ex_rate_v22', 150.0)
    def apply_calc(row):
        r = 1.0 if row.get('currency') == 'JPY' else ex
        adj = 10000.0 if row.get('カテゴリー') == '投資信託' else 1.0
        val = (row.get('現在価格', 0) * row.get('保有数量', 0) * r) / adj
        cost = (row.get('取得単価', 0) * row.get('保有数量', 0) * r) / adj
        div = calc_dividend(row.get('現状1株配当', 0), row.get('保有数量', 0), row.get('currency', 'JPY'), row.get('カテゴリー', '日本株'), row.get('is_nisa', False), ex, tax_mode)
        return pd.Series([val, cost, div])
    d[['評価額', '投資金額', '年間配当']] = d.apply(apply_calc, axis=1)
    return d

@st.dialog("配当スケジュールの詳細設定")
def edit_div_schedule(idx):
    it = st.session_state.portfolio_list[idx]
    st.write(f"### {it.get('銘柄名','')} - 配当設定")
    if 'div_schedule_v2' not in it or not isinstance(it['div_schedule_v2'], list): it['div_schedule_v2'] = [{"amount": 0.0, "months": []} for _ in range(4)]
    while len(it['div_schedule_v2']) < 4: it['div_schedule_v2'].append({"amount": 0.0, "months": []})
    for i in range(4):
        st.markdown(f"**【 {i+1} 回目 】**")
        c1, c2 = st.columns([0.3, 0.7])
        it['div_schedule_v2'][i]['amount'] = c1.number_input(f"単価", value=float(it['div_schedule_v2'][i]['amount']), step=0.1, format="%.1f", key=f"amt_v22_{idx}_{i}")
        sel_m = it['div_schedule_v2'][i]['months']
        with c2:
            m_cols = st.columns(6)
            new_sel = []
            for m in range(1, 13):
                with m_cols[(m-1)%6]:
                    if st.checkbox(f"{m}月", value=(m in sel_m), key=f"chk_v22_{idx}_{i}_{m}"): new_sel.append(m)
            it['div_schedule_v2'][i]['months'] = new_sel
    if st.button("設定を反映", type="primary", use_container_width=True):
        it['変更1株配当'] = sum(item['amount'] * len(item['months']) for item in it['div_schedule_v2'])
        st.rerun()

# --- 3. メイン表示 ---
if not st.session_state.portfolio_list:
    st.info("左側のサイドバーから「保有銘柄csv」を読み込むか、保存ファイルを読み込んでください。")
    st.stop()

tab_dash, tab_edit = st.tabs(["🚀 ダッシュボード", "📝 銘柄編集・リバランス"])

with tab_dash:
    df_m = get_current_df(tax_mode)
    if not df_m.empty:
        v, c, d = df_m['評価額'].sum(), df_m['投資金額'].sum(), df_m['年間配当'].sum()
        m1, m2, m3, m4 = st.columns(4); m1.metric("時価総額", f"¥{v:,.0f}", delta=f"¥{v - c:,.0f}"); m2.metric("投資総額", f"¥{c:,.0f}"); m3.metric(f"配当({tax_mode})", f"年間 ¥{d:,.0f}"); m4.metric("月平均配当", f"¥{d/12:,.0f}")
        st.divider()
        m_dist = {m: 0.0 for m in range(1, 13)}; ex_val = st.session_state.get('ex_rate_v22', 150.0)
        for it in st.session_state.portfolio_list:
            for sc in it.get('div_schedule_v2', []):
                r = 1.0 if it.get('currency') == 'JPY' else ex_val; adj = 10000.0 if it.get('カテゴリー') == '投資信託' else 1.0
                base_a = (sc.get('amount', 0) * it.get('保有数量', 0) * r) / adj
                if tax_mode == "税引後": base_a *= (0.9 if it.get('currency') == 'USD' else 1.0) if it.get('is_nisa') else 0.79685
                for month in sc.get('months', []):
                    if 1 <= month <= 12: m_dist[month] += base_a
        df_monthly = pd.DataFrame({"月": [f"{m}月" for m in range(1, 13)], "配当金": list(m_dist.values())})
        cg1, cg2 = st.columns([0.65, 0.35])
        with cg1: st.plotly_chart(px.bar(df_monthly, x="月", y="配当金", title="月別受取配当推移", text_auto='.2s').update_layout(height=400), use_container_width=True)
        with cg2: p_dash = df_m.groupby('カテゴリー')['評価額'].sum().reindex(CAT_ORDER).fillna(0); st.plotly_chart(go.Figure(data=[go.Pie(labels=p_dash.index, values=p_dash.values, hole=0.4, sort=False, direction='clockwise', marker=dict(colors=[COLOR_MAP[cat] for cat in CAT_ORDER]))]).update_layout(title="資産構成比", height=400), use_container_width=True)

with tab_edit:
    cl_list, cl_form, cl_res = st.columns([4.0, 1.3, 4.7])
    with cl_list:
        st.subheader("📋 銘柄リスト")
        tabs = st.tabs(CAT_ORDER)
        for i, cat_nm in enumerate(CAT_ORDER):
            with tabs[i]:
                with st.container(height=850, border=True):
                    for idx, it in enumerate(st.session_state.portfolio_list):
                        if it.get('カテゴリー') == cat_nm:
                            r_c1, r_c2, r_c3, r_c4, r_c5 = st.columns([0.38, 0.12, 0.17, 0.17, 0.16])
                            with r_c1:
                                code_lbl = f"[{it.get('コード','')}] " if it.get('コード') else ""
                                if st.button(f"{code_lbl}{it.get('銘柄名','')}", key=f"btn_l_{idx}", type="primary" if st.session_state.edit_index == idx else "secondary"): st.session_state.edit_index = idx; st.rerun()
                            with r_c2: st.markdown(f'<div class="status-tag {"tag-nisa" if it.get("is_nisa") else "tag-tokutei"}">{"NISA" if it.get("is_nisa") else "特定"}</div>', unsafe_allow_html=True)
                            with r_c3: p_sym = "$" if it.get("currency")=="USD" else "¥"; st.markdown(f'<div class="list-text">{p_sym}{it.get("現在価格",0):,.1f}</div>', unsafe_allow_html=True)
                            with r_c4: q_sym = "口" if it.get('カテゴリー')=="投資信託" else "株"; st.markdown(f'<div class="list-text" style="color:#5D6D7E;">{it.get("保有数量",0):,.0f}{q_sym}</div>', unsafe_allow_html=True)
                            with r_c5: prf = (it.get("現在価格",0) - it.get("取得単価",1)) / it.get("取得単価",1) * 100 if it.get("取得単価",0) > 0 else 0; st.markdown(f'<div class="list-text {"profit-plus" if prf>=0 else "profit-minus"}">{prf:+.1f}%</div>', unsafe_allow_html=True)

    with cl_form:
        st.subheader("🖋️ 編集")
        if st.session_state.edit_index is not None:
            idx_e = st.session_state.edit_index; it_e = st.session_state.portfolio_list[idx_e]
            it_e['変更単価'] = st.number_input("予測単価", value=float(it_e.get('変更単価', it_e['現在価格'])), step=0.1, key=f"sim_p_{idx_e}")
            it_e['変更数量'] = st.number_input("増減数量", value=float(it_e.get('変更数量', 0.0)), step=100.0, format="%.0f", key=f"sim_q_{idx_e}")
            it_e['変更1株配当'] = st.number_input("予測配当(年)", value=float(it_e.get('変更1株配当', it_e['現状1株配当'])), step=0.1, key=f"sim_d_{idx_e}")
            with st.expander("詳細設定"):
                it_e['銘柄名'] = st.text_input("名称", it_e.get('銘柄名',''), key=f"ed_nm_{idx_e}")
                it_e['カテゴリー'] = st.selectbox("カテ", CAT_ORDER, index=CAT_ORDER.index(it_e['カテゴリー']), key=f"ed_ct_{idx_e}")
                s_list = JP_SECTORS if it_e['カテゴリー']=="日本株" else (US_SECTORS if it_e['カテゴリー']=="外国株" else [it_e.get('カテゴリー')])
                it_e['セクター'] = st.selectbox("セクター", s_list, index=s_list.index(it_e['セクター']) if it_e['セクター'] in s_list else 0, key=f"ed_sc_{idx_e}")
                if st.button("📅 配当設定", use_container_width=True): edit_div_schedule(idx_e)
            if st.button("🗑️ 削除", use_container_width=True): st.session_state.portfolio_list.pop(idx_e); st.session_state.edit_index = None; st.rerun()
        else: st.info("銘柄を選択")

    with cl_res:
        st.subheader("📊 リバランス対比")
        with st.container(height=900, border=True):
            if st.session_state.portfolio_list:
                df_curr_r = get_current_df(tax_mode); sims_f, net_i, chg_l = [], 0.0, []; ex_s = st.session_state.get('ex_rate_v22', 150.0)
                for i_s, it_s in enumerate(st.session_state.portfolio_list):
                    r_s = it_s.copy(); r_ex = 1.0 if r_s.get('currency') == 'JPY' else ex_s; adj_s = 10000.0 if r_s.get('カテゴリー') == '投資信託' else 1.0; nq_s = max(0, r_s.get('保有数量',0) + r_s.get('変更数量',0))
                    sim_b = r_s.get('変更1株配当', 0) if r_s.get('変更1株配当', 0) > 0 else r_s.get('現状1株配当', 0); r_s['新配'] = calc_dividend(sim_b, nq_s, r_s.get('currency','JPY'), r_s.get('カテゴリー','日本株'), r_s.get('is_nisa',False), ex_s, tax_mode)
                    impact = 0.0; sim_p = r_s.get('変更単価', r_s['現在価格'])
                    if r_s.get('変更数量',0) < 0: sv = (sim_p * abs(r_s['変更数量'])) * r_ex / adj_s; tx = max(0, ((sim_p - r_s.get('取得単価',0)) * abs(r_s['変更数量']) * r_ex / adj_s) * 0.20315) if not r_s.get('is_nisa') else 0; impact = sv - tx
                    else: impact = -(sim_p * r_s.get('変更数量',0) * r_ex) / adj_s
                    if (r_s.get('変更数量',0) != 0 or r_s.get('変更単価',0) != r_s.get('現在価格',0) or r_s.get('変更1株配当',0) != r_s.get('現状1株配当',0)):
                        det = [f"数:{r_s.get('保有数量',0):,.0f}→{nq_s:,.0f}" if r_s.get('変更数量',0)!=0 else ""]; chg_l.append({"idx": i_s, "name": r_s.get('銘柄名',''), "nisa": r_s.get('is_nisa'), "amt_txt": f"{'+' if impact>=0 else ''}¥{abs(impact):,.0f}", "cls": "amt_heavy-plus" if impact>=0 else "amt_heavy-minus", "det": " / ".join([d for d in det if d])}); net_i += impact
                    r_s['新評'] = (sim_p * nq_s * r_ex) / adj_s; r_s['敏感度'] = get_sensitivity(r_s.get('セクター', '')); sims_f.append(r_s)
                df_sim_f = pd.DataFrame(sims_f); c_now = df_curr_r[df_curr_r['カテゴリー']=='現金']['評価額'].sum() if not df_curr_r[df_curr_r['カテゴリー']=='現金'].empty else 0; s_cash = c_now + net_i; df_sf_final = pd.concat([df_sim_f[df_sim_f['カテゴリー']!='現金'], pd.DataFrame([{'カテゴリー':'現金','セクター':'現金','敏感度':'中立/現金','新評':max(0, s_cash),'新配':0}])], ignore_index=True)
                cm1, cm2 = st.columns(2); cm1.metric("【現】時価総額", f"¥{df_curr_r['評価額'].sum():,.0f}"); cm1.metric(f"【現】配当", f"¥{df_curr_r['年間配当'].sum():,.0f}"); cm2.metric("【予】時価総額", f"¥{df_sf_final['新評'].sum():,.0f}", delta=f"¥{df_sf_final['新評'].sum()-df_curr_r['評価額'].sum():,.0f}"); cm2.metric(f"【予】配当", f"¥{df_sf_final['新配'].sum():,.0f}", delta=f"¥{df_sf_final['新配'].sum()-df_curr_r['年間配当'].sum():,.0f}")
                p1 = df_curr_r.groupby('カテゴリー')['評価額'].sum().reindex(CAT_ORDER).fillna(0); p2 = df_sf_final.groupby('カテゴリー')['新評'].sum().reindex(CAT_ORDER).fillna(0); fig_comp = make_subplots(rows=1, cols=2, specs=[[{'type':'domain'}, {'type':'domain'}]], subplot_titles=("現構成", "予構成")); fig_comp.add_trace(go.Pie(labels=p1.index, values=p1.values, hole=0.3, sort=False, direction='clockwise', marker=dict(colors=[COLOR_MAP.get(cat, "#BDC3C7") for cat in CAT_ORDER])), 1, 1); fig_comp.add_trace(go.Pie(labels=p2.index, values=p2.values, hole=0.3, sort=False, direction='clockwise', marker=dict(colors=[COLOR_MAP.get(cat, "#BDC3C7") for cat in CAT_ORDER])), 1, 2); st.plotly_chart(fig_comp.update_layout(height=260, showlegend=False, margin=dict(t=30, b=10, l=10, r=10)), use_container_width=True)
                sen_order = ["ディフェンシブ", "景気敏感", "中立/現金"]; sen_colors = ["#7DCEA0", "#F1948A", "#D5DBDB"]; df_curr_r['敏感度'] = df_curr_r['セクター'].apply(get_sensitivity); s1 = df_curr_r.groupby('敏感度')['評価額'].sum().reindex(sen_order).fillna(0); s2 = df_sf_final.groupby('敏感度')['新評'].sum().reindex(sen_order).fillna(0); fig_sen = make_subplots(rows=1, cols=2, specs=[[{'type':'domain'}, {'type':'domain'}]]); fig_sen.add_trace(go.Pie(labels=s1.index, values=s1.values, hole=0.5, marker=dict(colors=sen_colors), textinfo='label+percent'), 1, 1); fig_sen.add_trace(go.Pie(labels=s2.index, values=s2.values, hole=0.5, marker=dict(colors=sen_colors), textinfo='label+percent'), 1, 2); st.plotly_chart(fig_sen.update_layout(height=200, showlegend=False, margin=dict(t=10,b=10), annotations=[dict(text='現', x=0.22, y=0.5, showarrow=False), dict(text='予', x=0.78, y=0.5, showarrow=False)]), use_container_width=True)
                if s_cash < 0: st.markdown(f'<div class="warning-box">⚠️ 資金不足: ¥{abs(s_cash):,.0f}</div>', unsafe_allow_html=True)
                for item in chg_l:
                    sc1, sc2, sc3 = st.columns([0.65, 0.27, 0.08]); sc1.markdown(f'**{item["name"]}**<br><span class="change-label">{item["det"]}</span>', unsafe_allow_html=True); sc2.markdown(f'<div class="{item["cls"]}">{item["amt_txt"]}</div>', unsafe_allow_html=True)
                    if sc3.button("×", key=f"rv_btn_{item['idx']}"): to = st.session_state.portfolio_list[item['idx']]; to['変更単価'], to['変更数量'], to['変更1株配当'] = to.get('現在価格',0), 0.0, to.get('現状1株配当',0); st.rerun()
                st.divider(); st.write("📂 お気に入りスロット")
                sc_r = st.columns(3)
                for i in range(3):
                    with sc_r[i]:
                        slot = st.session_state.saved_sims[i]; is_saved = slot["data"] is not None; c_b1, c_b2, c_b3 = st.columns([1, 1, 0.5])
                        if c_b1.button("✅ 保存済" if is_saved else f"保存{i+1}", key=f"sv_{i}", use_container_width=True): slot["data"] = [x.copy() for x in st.session_state.portfolio_list]; st.rerun()
                        if c_b2.button("呼出", key=f"ld_{i}", use_container_width=True):
                            if slot["data"]: st.session_state.portfolio_list = [x.copy() for x in slot["data"]]; st.rerun()
                        if c_b3.button("🗑️", key=f"del_{i}"): slot["data"], slot["note"] = None, ""; st.rerun()
                        slot["note"] = st.text_area(f"メモ{i+1}", value=slot["note"], key=f"n_{i}", height=70, label_visibility="collapsed")
