import re
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

st.set_page_config(
    page_title="MK Ranking Analysis",
    page_icon="📊",
    layout="centered"
)

# ============================================================
#  🔒 로그인
# ============================================================
def check_login():
    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
    <div style="max-width:420px;margin:60px auto;padding:40px;
         background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);
         border-radius:20px;box-shadow:0 24px 60px rgba(0,0,0,.5);text-align:center">
      <div style="font-size:44px;margin-bottom:12px">📊</div>
      <div style="color:#fff;font-size:22px;font-weight:700;margin-bottom:4px">MK Ranking Analysis</div>
      <div style="color:rgba(255,255,255,.4);font-size:13px;margin-bottom:32px">네이버 쇼핑 순위 &amp; 경쟁사 가격 모니터링</div>
    </div>
    """, unsafe_allow_html=True)

    pw = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요", label_visibility="collapsed")
    if st.button("🔓  로그인", use_container_width=True, type="primary"):
        if pw == st.secrets.get("APP_PASSWORD", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False

# ============================================================
#  ⚙️ 분석 함수 (버그 수정 포함)
# ============================================================
def strip_html(text):
    return re.sub(r'<[^>]+>', '', text)

def fetch_items(keyword, limit):
    client_id     = st.secrets["NAVER_CLIENT_ID"]
    client_secret = st.secrets["NAVER_CLIENT_SECRET"]
    url     = "https://openapi.naver.com/v1/search/shop.json"
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    resp    = requests.get(url, headers=headers, params={"query": keyword, "display": limit}, timeout=10)
    resp.raise_for_status()
    return resp.json().get('items', [])

def parse_df(items, my_store):
    """실제 네이버 검색 순위(i)를 기준으로 순위 부여 — price==0 건너뛰어도 순위 왜곡 없음"""
    rows = []
    for i, item in enumerate(items, 1):
        price = int(item.get('lprice', 0))
        if price == 0:
            continue
        mall  = item.get('mallName', '알수없음')
        title = strip_html(item.get('title', ''))
        rows.append({
            "순위":    i,
            "구분":    "mine" if my_store in mall else "comp",
            "썸네일":  item.get('image', ''),
            "업체명":  mall,
            "가격":    price,
            "브랜드":  item.get('brand', ''),
            "제조사":  item.get('maker', ''),
            "세분류":  item.get('category4', ''),
            "상품명":  title,
            "글자수":  len(title),
            "링크":    item.get('link', ''),
            "수집일시": datetime.now().strftime('%Y-%m-%d %H:%M'),
        })
    return pd.DataFrame(rows)

def filter_kw(df, kws):
    if not kws.strip():
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    for k in kws.split():
        mask &= df['상품명'].str.replace(" ", "").str.lower().str.contains(
            k.lower().replace(" ", ""), na=False, regex=False)
    return df[mask]

def make_rows(df, min_price):
    html = ""
    for _, r in df.iterrows():
        is_mine  = r['구분'] == 'mine'
        badge    = '<span class="mk-badge-mine">⭐ 내 상품</span>' if is_mine else '<span class="mk-badge-comp">경쟁사</span>'
        rank_tag = f'<span class="mk-rank-mine">{r["순위"]}</span>' if is_mine else f'<span class="mk-rank-comp">{r["순위"]}</span>'
        img      = f'<img src="{r["썸네일"]}" width="44" style="border-radius:6px;vertical-align:middle;">' if r['썸네일'] else '—'
        p_cls    = 'mk-price-low' if r['가격'] == min_price else 'mk-price'
        l_cls    = 'mk-len-bad' if r['글자수'] > 40 else 'mk-len-ok'
        l_warn   = ' ⚠️' if r['글자수'] > 40 else ''
        link     = f'<a href="{r["링크"]}" target="_blank">보기 →</a>' if r['링크'] else '—'
        name     = r['상품명'][:36] + '…' if len(r['상품명']) > 36 else r['상품명']
        html    += f"""<tr>
          <td>{rank_tag}</td><td>{badge}</td><td>{img}</td>
          <td class="mk-name">{name}</td>
          <td><span class="{l_cls}">{r['글자수']}자{l_warn}</span></td>
          <td class="{p_cls}">{r['가격']:,}원</td>
          <td class="mk-mall">{r['업체명']}</td>
          <td class="mk-link">{link}</td>
        </tr>"""
    return html

def build_result_html(df, store, target, limit):
    total     = len(df)
    mine_df   = df[df['구분'] == 'mine']
    min_price = df['가격'].min()
    max_price = df['가격'].max()
    mine_rank_str  = ', '.join(str(r) for r in mine_df['순위'].tolist()) if not mine_df.empty else '미노출'
    mine_count_str = f"{len(mine_df)}개 노출"

    target_html = ""
    if target.strip():
        tdf = filter_kw(df, target)
        if not tdf.empty:
            t_min   = tdf['가격'].min()
            t_min_r = tdf[tdf['가격'] == t_min].iloc[0]
            my_t    = tdf[tdf['구분'] == 'mine']
            if not my_t.empty:
                mr       = my_t.iloc[0]
                diff     = mr['가격'] - t_min
                diff_str = "✅ 최저가 동일" if diff == 0 else f"🔺 최저가 대비 +{diff:,}원"
                my_info  = f"""
                <div class="mk-card-item">
                  <div class="mk-ci-label">🐾 {store} 순위 / 가격</div>
                  <div class="mk-ci-value">{mr['순위']}위 · {mr['가격']:,}원</div>
                  <div class="mk-ci-sub">{diff_str}</div>
                </div>"""
            else:
                my_info = f"""
                <div class="mk-card-item">
                  <div class="mk-ci-label">🐾 {store}</div>
                  <div class="mk-ci-value" style="color:#f87171">상위 {total}위 내 미노출</div>
                </div>"""
            target_html = f"""
            <div class="mk-target-card">
              <div class="mk-target-title">🎯 타겟 분석 — "{target}"</div>
              <div class="mk-card-row">
                <div class="mk-card-item">
                  <div class="mk-ci-label">🥇 시장 최저가</div>
                  <div class="mk-ci-value" style="color:#6ee7b7">{t_min:,}원</div>
                  <div class="mk-ci-sub">{t_min_r['업체명']} · {t_min_r['순위']}위</div>
                </div>
                {my_info}
                <div class="mk-card-item">
                  <div class="mk-ci-label">📊 타겟 상품 수</div>
                  <div class="mk-ci-value">{len(tdf)}개</div>
                  <div class="mk-ci-sub">내 상품 {len(my_t)}개 포함</div>
                </div>
              </div>
            </div>"""
        else:
            target_html = f'<div class="mk-no-target">🎯 "{target}" 키워드 포함 상품이 상위 {total}위 내에 없습니다.</div>'

    thead = """<thead><tr>
      <th>순위</th><th>구분</th><th>썸네일</th><th>상품명</th>
      <th>글자수</th><th>가격</th><th>업체명</th><th>링크</th>
    </tr></thead>"""

    my_table = ""
    if not mine_df.empty:
        my_table = f"""
        <div class="mk-section-label">⭐ {store} 노출 상품 ({len(mine_df)}개)</div>
        <div class="mk-table-box">
          <table class="mk-table">{thead}<tbody>{make_rows(mine_df, min_price)}</tbody></table>
        </div>"""

    return f"""<!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
    * {{ font-family:'Noto Sans KR',sans-serif; box-sizing:border-box; margin:0; padding:0; }}
    body {{ background:linear-gradient(135deg,#0f0c29,#302b63,#24243e); padding:24px; min-height:100vh; }}
    .mk-stat-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px; }}
    .mk-stat {{ background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08); border-radius:14px; padding:16px 18px; }}
    .mk-stat-label {{ color:rgba(255,255,255,.4); font-size:11px; letter-spacing:.05em; margin-bottom:6px; }}
    .mk-stat-value {{ color:#fff; font-size:22px; font-weight:700; }}
    .mk-stat-unit {{ font-size:13px; color:rgba(255,255,255,.4); margin-left:2px; }}
    .mk-stat-sub {{ color:rgba(255,255,255,.3); font-size:11px; margin-top:4px; }}
    .mk-target-card {{ background:linear-gradient(135deg,rgba(124,58,237,.2),rgba(139,92,246,.08));
      border:1px solid rgba(139,92,246,.35); border-radius:14px; padding:18px 20px; margin-bottom:20px; }}
    .mk-target-title {{ color:#c4b5fd; font-size:12px; font-weight:600; letter-spacing:.06em; margin-bottom:14px; }}
    .mk-card-row {{ display:flex; gap:20px; flex-wrap:wrap; }}
    .mk-card-item {{ flex:1; min-width:160px; }}
    .mk-ci-label {{ color:rgba(255,255,255,.38); font-size:11px; margin-bottom:4px; }}
    .mk-ci-value {{ color:#fff; font-size:14px; font-weight:600; }}
    .mk-ci-sub {{ color:rgba(255,255,255,.4); font-size:12px; margin-top:3px; }}
    .mk-no-target {{ color:#f87171; font-size:13px; margin-bottom:16px; }}
    .mk-section-label {{ color:rgba(255,255,255,.7); font-size:12px; font-weight:600;
      letter-spacing:.06em; text-transform:uppercase;
      padding-bottom:10px; margin-bottom:12px; margin-top:20px;
      border-bottom:1px solid rgba(255,255,255,.07); }}
    .mk-table-box {{ background:#13111f; border-radius:12px; overflow:hidden;
      border:1px solid rgba(255,255,255,.07); margin-bottom:8px; }}
    .mk-scroll {{ max-height:420px; overflow-y:auto; }}
    .mk-scroll::-webkit-scrollbar {{ width:5px; }}
    .mk-scroll::-webkit-scrollbar-track {{ background:rgba(255,255,255,.03); }}
    .mk-scroll::-webkit-scrollbar-thumb {{ background:rgba(167,139,250,.35); border-radius:3px; }}
    .mk-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    .mk-table thead tr {{ background:rgba(167,139,250,.1); }}
    .mk-table th {{ color:rgba(255,255,255,.5); font-size:11px; font-weight:500;
      letter-spacing:.06em; text-transform:uppercase;
      padding:11px 12px; text-align:left; white-space:nowrap; }}
    .mk-table td {{ padding:10px 12px; color:rgba(255,255,255,.8);
      border-top:1px solid rgba(255,255,255,.05); vertical-align:middle; }}
    .mk-table tr:hover td {{ background:rgba(255,255,255,.03); }}
    .mk-badge-mine {{ background:rgba(167,139,250,.2); color:#c4b5fd;
      border-radius:6px; padding:2px 7px; font-size:11px; font-weight:600; white-space:nowrap; }}
    .mk-badge-comp {{ background:rgba(255,255,255,.07); color:rgba(255,255,255,.4);
      border-radius:6px; padding:2px 7px; font-size:11px; white-space:nowrap; }}
    .mk-rank-mine {{ background:#7c3aed; color:#fff; border-radius:6px;
      padding:2px 8px; font-weight:700; font-size:13px; }}
    .mk-rank-comp {{ color:rgba(255,255,255,.45); }}
    .mk-len-ok  {{ color:#6ee7b7; font-weight:600; }}
    .mk-len-bad {{ color:#f87171; font-weight:700; }}
    .mk-price   {{ color:#fde68a; font-weight:600; }}
    .mk-price-low {{ color:#6ee7b7; font-weight:700; }}
    .mk-name {{ max-width:220px; white-space:normal; line-height:1.4; word-break:keep-all; }}
    .mk-mall {{ color:rgba(255,255,255,.4); font-size:12px; }}
    .mk-link a {{ color:#818cf8; font-weight:600; text-decoration:none; }}
    .mk-link a:hover {{ text-decoration:underline; }}
    </style></head><body>
    <div class="mk-stat-grid">
      <div class="mk-stat">
        <div class="mk-stat-label">📦 조회 상품</div>
        <div class="mk-stat-value">{total}<span class="mk-stat-unit">개</span></div>
        <div class="mk-stat-sub">상위 {limit}위 기준</div>
      </div>
      <div class="mk-stat">
        <div class="mk-stat-label">💰 최저가</div>
        <div class="mk-stat-value" style="color:#6ee7b7">{min_price:,}<span class="mk-stat-unit">원</span></div>
        <div class="mk-stat-sub">최고가 {max_price:,}원</div>
      </div>
      <div class="mk-stat">
        <div class="mk-stat-label">⭐ {store} 현황</div>
        <div class="mk-stat-value" style="color:#c4b5fd;font-size:18px">{mine_rank_str}</div>
        <div class="mk-stat-sub">{mine_count_str}</div>
      </div>
    </div>
    {target_html}
    {my_table}
    <div class="mk-section-label">📋 전체 시장 리스트 ({total}개)</div>
    <div class="mk-table-box mk-scroll">
      <table class="mk-table">{thead}<tbody>{make_rows(df, min_price)}</tbody></table>
    </div>
    </body></html>"""

# ============================================================
#  🖼️ 메인 UI
# ============================================================
if not check_login():
    st.stop()

st.markdown("""
<div style="display:flex;align-items:center;gap:14px;
     border-bottom:1px solid rgba(255,255,255,.1);padding-bottom:20px;margin-bottom:24px">
  <div style="width:48px;height:48px;border-radius:14px;
       background:linear-gradient(135deg,#667eea,#764ba2);
       display:flex;align-items:center;justify-content:center;font-size:22px">📊</div>
  <div>
    <div style="font-size:20px;font-weight:700">MK Ranking Analysis</div>
    <div style="color:rgba(255,255,255,.4);font-size:12px;margin-top:3px">
      네이버 쇼핑 순위 &amp; 경쟁사 가격 모니터링
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    keyword = st.text_input("🔍 검색 키워드", value="abc케어사료", placeholder="예: 강아지사료 1kg")
with col2:
    store = st.text_input("🏪 내 스토어명", value="올댓펫", placeholder="스토어명 정확히 입력")

target = st.text_input(
    "🎯 타겟 상품 키워드",
    value="1kg",
    placeholder="예: 1kg 소고기  (공백 구분 시 AND 검색)",
)
limit = st.slider("📋 조회 상품 수 (최대 100개)", min_value=10, max_value=100, value=100, step=10)

run = st.button("🚀  시장 분석 시작", use_container_width=True, type="primary")

if run:
    if not keyword.strip():
        st.error("검색 키워드를 입력해 주세요.")
        st.stop()

    with st.spinner(f"**{keyword}** 시장 조사 중입니다..."):
        try:
            items = fetch_items(keyword, limit)
        except Exception as e:
            st.error(f"API 오류: {e}")
            st.stop()

    df = parse_df(items, store)
    if df.empty:
        st.warning("검색 결과가 없습니다.")
        st.stop()

    # 결과 HTML 렌더링
    result_html = build_result_html(df, store, target, limit)
    components.html(result_html, height=900, scrolling=True)

    # CSV 다운로드 (Streamlit 네이티브 버튼)
    fname = f"{store}_Ranking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    csv_bytes = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label="📥  CSV 다운로드",
        data=csv_bytes,
        file_name=fname,
        mime="text/csv",
        use_container_width=True,
    )
