"""
체스 모임 리텐션 대시보드 / Chess Club Retention Dashboard
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from data_loader import load_all_events, build_attendance_matrix
from analyzer import (
    event_summary,
    attendance_frequency,
    cohort_retention,
    frequency_distribution,
)


# ── 테마 ──────────────────────────────────────────────────────────────────────
_DARK  = {"bg": "#111111", "bg2": "#2A0D29", "text": "#F0D8EE", "accent": "#FCACF3"}
_LIGHT = {"bg": "#F7F0F6", "bg2": "#EAD8E9", "text": "#1A0A19", "accent": "#6E003D"}


def _css(c: dict) -> str:
    btn_bg = "#FCACF3"
    btn_fg = "#2A0D29"
    return (
        f".stApp,[data-testid='stAppViewContainer']{{background-color:{c['bg']} !important}}"
        f"section[data-testid='stSidebar']>div:first-child{{background-color:{c['bg2']} !important}}"
        f"[data-testid='stHeader']{{background-color:{c['bg']} !important}}"
        f"p,span,label,h1,h2,h3,h4,li,"
        f"[data-testid='stMetricLabel'],[data-testid='stMetricValue']{{color:{c['text']} !important}}"
        f"[data-testid='metric-container']{{background-color:{c['bg2']} !important;border-radius:8px;padding:1rem}}"
        f".stTabs [data-baseweb='tab-list']{{background-color:{c['bg2']} !important}}"
        f".stTabs [data-baseweb='tab']{{color:{c['text']} !important}}"
        f".stTabs [aria-selected='true']{{background-color:{c['accent']}33 !important;color:{c['accent']} !important}}"
        f".stButton>button{{background-color:{btn_bg} !important;color:{btn_fg} !important;border:none !important}}"
        f"[data-testid='stSidebarContent'] label,"
        f"[data-testid='stSidebarContent'] span,"
        f"[data-testid='stSidebarContent'] p{{color:{c['text']} !important}}"
    )


def apply_theme() -> None:
    mode = st.session_state.get("theme_mode", "system")
    if mode == "dark":
        block = _css(_DARK)
    elif mode == "light":
        block = _css(_LIGHT)
    else:
        block = (
            f"@media(prefers-color-scheme:dark){{{_css(_DARK)}}}"
            f"@media(prefers-color-scheme:light){{{_css(_LIGHT)}}}"
        )
    st.html(f"<style>{block}</style>")


# ── 번역 사전 ──────────────────────────────────────────────────────────────────
TRANSLATIONS = {
    "ko": {
        "page_title": "서울체스클럽 리텐션 분석",
        "app_title": "♟️ 서울체스클럽 리텐션 대시보드",
        "enter_password": "비밀번호를 입력하세요",
        "password": "비밀번호",
        "login": "로그인",
        "wrong_password": "비밀번호가 틀렸습니다.",
        "refresh": "🔄 새로고침",
        "no_spreadsheet_id": "`secrets.toml`에 `spreadsheet_id`를 설정해주세요.",
        "loading": "Google Sheets에서 데이터 불러오는 중...",
        "load_failed": "데이터 로드 실패: ",
        "no_data": "시트에 데이터가 없습니다.",
        "no_attendance": "출석 데이터를 찾을 수 없습니다. 이메일 컬럼 또는 CheckedInAt 컬럼을 확인해주세요.",
        "filter": "필터",
        "language": "언어 / Language",
        "theme": "테마",
        "theme_system": "💻 시스템",
        "theme_light": "☀️ 라이트",
        "theme_dark": "🌙 다크",
        "select_events": "분석할 이벤트 선택",
        "total_caption": "{n_events}개 이벤트 · {n_members}명",
        "select_one_event": "이벤트를 하나 이상 선택해주세요.",
        "total_unique": "총 고유 참석자",
        "n_events": "이벤트 수",
        "returning_2plus": "2회 이상 참석자",
        "returning_help": "재방문 경험이 있는 멤버 수",
        "avg_per_person": "1인당 평균 참석",
        "unit_person": "명",
        "unit_times": "회",
        "tab1": "📅 이벤트별 요약",
        "tab2": "📊 참석 빈도",
        "tab3": "🔄 코호트 리텐션",
        "tab4": "🏅 멤버 순위",
        "bar_title": "이벤트별 신규 / 복귀 참석자",
        "bar_y": "인원",
        "line_title": "이벤트별 복귀율 (%)",
        "hist_title": "참석 횟수 분포 (몇 번 온 사람이 몇 명인가)",
        "pie_title": "참석 횟수별 비율",
        "pie_template": "%{label}회: %{percent}",
        "cohort_no_data": "코호트 분석을 위한 데이터가 충분하지 않습니다.",
        "cohort_caption": "각 셀: 해당 코호트 중 N번째 이벤트에도 참석한 비율 (%)",
        "cohort_title": "코호트 리텐션 히트맵",
        "cohort_x": "첫 참석 기준 +N번째 이벤트",
        "cohort_y": "코호트 (첫 참석 이벤트)",
        "cohort_hover": "코호트: %{y}<br>오프셋: %{x}<br>리텐션: %{z:.1f}%<extra></extra>",
        "member_caption": "이름 컬럼이 없는 경우 익명 ID(#해시)로 표시됩니다.",
        "top_n_title": "참석 횟수 상위 {n}명",
        "member_label": "이름",
        "col_event": "이벤트",
        "col_registered": "등록자",
        "col_attended": "참석자",
        "col_new": "신규",
        "col_returning": "복귀",
        "col_retention": "복귀율(%)",
        "col_attend_count": "참석 횟수",
        "col_people_count": "인원 수",
        "col_cohort_size": "코호트 크기",
        "col_rank": "순위",
        "col_name": "이름",
    },
    "en": {
        "page_title": "Seoul Chess Club Retention Analysis",
        "app_title": "♟️ Seoul Chess Club Retention Dashboard",
        "enter_password": "Enter your password",
        "password": "Password",
        "login": "Login",
        "wrong_password": "Incorrect password.",
        "refresh": "🔄 Refresh",
        "no_spreadsheet_id": "Please set `spreadsheet_id` in `secrets.toml`.",
        "loading": "Loading data from Google Sheets...",
        "load_failed": "Failed to load data: ",
        "no_data": "No data found in the sheet.",
        "no_attendance": "No attendance data found. Please check the email or CheckedInAt column.",
        "filter": "Filter",
        "language": "언어 / Language",
        "theme": "Theme",
        "theme_system": "💻 System",
        "theme_light": "☀️ Light",
        "theme_dark": "🌙 Dark",
        "select_events": "Select events to analyze",
        "total_caption": "{n_events} events · {n_members} members",
        "select_one_event": "Please select at least one event.",
        "total_unique": "Total Unique Attendees",
        "n_events": "Events",
        "returning_2plus": "Returned 2+ Times",
        "returning_help": "Members who have attended more than once",
        "avg_per_person": "Avg. Attendance / Person",
        "unit_person": "",
        "unit_times": "",
        "tab1": "📅 Event Summary",
        "tab2": "📊 Attendance Frequency",
        "tab3": "🔄 Cohort Retention",
        "tab4": "🏅 Member Rankings",
        "bar_title": "New vs. Returning Attendees per Event",
        "bar_y": "Count",
        "line_title": "Return Rate (%) per Event",
        "hist_title": "Attendance Frequency Distribution",
        "pie_title": "Attendance Frequency Breakdown",
        "pie_template": "%{label}x: %{percent}",
        "cohort_no_data": "Not enough data for cohort analysis.",
        "cohort_caption": "Each cell: % of cohort who also attended the Nth event",
        "cohort_title": "Cohort Retention Heatmap",
        "cohort_x": "+N events from first attendance",
        "cohort_y": "Cohort (first event attended)",
        "cohort_hover": "Cohort: %{y}<br>Offset: %{x}<br>Retention: %{z:.1f}%<extra></extra>",
        "member_caption": "Shown as anonymous ID (#hash) if no name column exists.",
        "top_n_title": "Top {n} Members by Attendance",
        "member_label": "Name",
        "col_event": "Event",
        "col_registered": "Registered",
        "col_attended": "Attended",
        "col_new": "New",
        "col_returning": "Returning",
        "col_retention": "Return Rate (%)",
        "col_attend_count": "Times Attended",
        "col_people_count": "People",
        "col_cohort_size": "Cohort Size",
        "col_rank": "Rank",
        "col_name": "Name",
    },
}


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("lang", "ko")
    text = TRANSLATIONS[lang].get(key, key)
    return text.format(**kwargs) if kwargs else text


st.set_page_config(
    page_title="♟️ Retention Dashboard",
    page_icon="♟️",
    layout="wide",
)


# ── 비밀번호 인증 ────────────────────────────────────────────────────────────
def check_auth():
    if st.session_state.get("authenticated"):
        return True

    st.title(t("app_title"))
    st.subheader(t("enter_password"))
    pw = st.text_input(t("password"), type="password", key="pw_input")
    if st.button(t("login")):
        if pw == st.secrets.get("password", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error(t("wrong_password"))
    st.stop()


check_auth()
apply_theme()


# ── 데이터 로드 ──────────────────────────────────────────────────────────────
spreadsheet_id = st.secrets.get("spreadsheet_id", "")

st.title(t("app_title"))

col_title, col_refresh = st.columns([8, 1])
with col_refresh:
    if st.button(t("refresh")):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

if not spreadsheet_id:
    st.error(t("no_spreadsheet_id"))
    st.stop()

with st.spinner(t("loading")):
    try:
        events = load_all_events(spreadsheet_id)
    except Exception as e:
        st.error(t("load_failed") + str(e))
        st.stop()

if not events:
    st.warning(t("no_data"))
    st.stop()

matrix, detail_df = build_attendance_matrix(events)

if matrix.empty:
    st.warning(t("no_attendance"))
    st.stop()


# ── 사이드바: 설정 + 이벤트 필터 ─────────────────────────────────────────────
all_events = list(matrix.columns)
with st.sidebar:
    with st.expander("⚙️ Settings", expanded=False):
        lang_choice = st.radio(t("language"), ["한국어", "English"], horizontal=True)
        st.session_state.lang = "ko" if lang_choice == "한국어" else "en"

        theme_opts = [t("theme_system"), t("theme_light"), t("theme_dark")]
        theme_choice = st.radio(t("theme"), theme_opts, horizontal=True)
        if t("theme_dark") in theme_choice:
            st.session_state.theme_mode = "dark"
        elif t("theme_light") in theme_choice:
            st.session_state.theme_mode = "light"
        else:
            st.session_state.theme_mode = "system"
        apply_theme()

    st.header(t("filter"))
    selected_events = st.multiselect(
        t("select_events"),
        options=all_events,
        default=all_events,
    )
    st.caption(t("total_caption", n_events=len(all_events), n_members=matrix.shape[0]))

if not selected_events:
    st.warning(t("select_one_event"))
    st.stop()

filtered_matrix = matrix[selected_events]
filtered_detail = detail_df[detail_df["event"].isin(selected_events)] if not detail_df.empty else detail_df


# ── 상단 KPI ─────────────────────────────────────────────────────────────────
total_unique = filtered_matrix.index.nunique()
total_events = len(selected_events)
multi_attendees = int((filtered_matrix.sum(axis=1) > 1).sum())
avg_events_per_person = filtered_matrix.sum(axis=1).mean()

up = t("unit_person")
ut = t("unit_times")

k1, k2, k3, k4 = st.columns(4)
k1.metric(t("total_unique"), f"{total_unique}{up}")
k2.metric(t("n_events"), f"{total_events}{ut}")
k3.metric(t("returning_2plus"), f"{multi_attendees}{up}", help=t("returning_help"))
k4.metric(t("avg_per_person"), f"{avg_events_per_person:.1f}{ut}")

st.divider()


# ── 탭 ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    [t("tab1"), t("tab2"), t("tab3"), t("tab4")]
)


# ── Tab 1: 이벤트별 요약 ─────────────────────────────────────────────────────
with tab1:
    summary_df = event_summary(filtered_matrix, filtered_detail)

    # 표시용 컬럼명 번역
    col_map = {
        "이벤트": t("col_event"),
        "등록자": t("col_registered"),
        "참석자": t("col_attended"),
        "신규": t("col_new"),
        "복귀": t("col_returning"),
        "복귀율(%)": t("col_retention"),
    }
    display_summary = summary_df.rename(columns=col_map)

    fig_bar = px.bar(
        display_summary,
        x=t("col_event"),
        y=[t("col_new"), t("col_returning")],
        barmode="stack",
        color_discrete_map={t("col_new"): "#4C8BF5", t("col_returning"): "#34A853"},
        title=t("bar_title"),
        labels={"value": t("bar_y"), "variable": ""},
    )
    fig_bar.update_layout(legend_title_text="")
    st.plotly_chart(fig_bar, use_container_width=True)

    retention_vals = [
        v if v != "-" else None for v in summary_df["복귀율(%)"].tolist()
    ]
    if any(v is not None for v in retention_vals):
        fig_line = go.Figure()
        fig_line.add_trace(
            go.Scatter(
                x=display_summary[t("col_event")],
                y=retention_vals,
                mode="lines+markers",
                line=dict(color="#FBBC05", width=2),
                name=t("col_retention"),
            )
        )
        fig_line.update_layout(
            title=t("line_title"),
            yaxis=dict(range=[0, 100], ticksuffix="%"),
            showlegend=False,
        )
        st.plotly_chart(fig_line, use_container_width=True)

    st.dataframe(display_summary, use_container_width=True, hide_index=True)


# ── Tab 2: 참석 빈도 분포 ────────────────────────────────────────────────────
with tab2:
    dist_df = frequency_distribution(filtered_matrix)
    display_dist = dist_df.rename(columns={
        "참석 횟수": t("col_attend_count"),
        "인원 수": t("col_people_count"),
    })

    fig_hist = px.bar(
        display_dist,
        x=t("col_attend_count"),
        y=t("col_people_count"),
        title=t("hist_title"),
        color=t("col_people_count"),
        color_continuous_scale="Blues",
        text=t("col_people_count"),
    )
    fig_hist.update_traces(textposition="outside")
    fig_hist.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_hist, use_container_width=True)

    fig_pie = px.pie(
        display_dist,
        names=t("col_attend_count"),
        values=t("col_people_count"),
        title=t("pie_title"),
        hole=0.4,
    )
    fig_pie.update_traces(
        texttemplate=t("pie_template"),
        textposition="outside",
    )
    st.plotly_chart(fig_pie, use_container_width=True)


# ── Tab 3: 코호트 리텐션 ────────────────────────────────────────────────────
with tab3:
    cohort_df = cohort_retention(filtered_matrix)

    if cohort_df.empty:
        st.info(t("cohort_no_data"))
    else:
        st.caption(t("cohort_caption"))

        numeric_cols = [c for c in cohort_df.columns if c != "코호트 크기"]
        heatmap_df = cohort_df[numeric_cols].copy()

        fig_hm = go.Figure(
            data=go.Heatmap(
                z=heatmap_df.values,
                x=heatmap_df.columns.tolist(),
                y=heatmap_df.index.tolist(),
                colorscale="Greens",
                zmin=0,
                zmax=100,
                text=[[f"{v:.0f}%" if pd.notna(v) else "" for v in row]
                      for row in heatmap_df.values],
                texttemplate="%{text}",
                hovertemplate=t("cohort_hover"),
            )
        )
        fig_hm.update_layout(
            title=t("cohort_title"),
            xaxis_title=t("cohort_x"),
            yaxis_title=t("cohort_y"),
            height=max(300, len(cohort_df) * 50 + 100),
        )
        st.plotly_chart(fig_hm, use_container_width=True)

        display_cohort = cohort_df.rename(columns={"코호트 크기": t("col_cohort_size")})
        display_numeric = [c for c in display_cohort.columns if c != t("col_cohort_size")]
        st.dataframe(
            display_cohort.style.format("{:.1f}%", subset=display_numeric, na_rep="-"),
            use_container_width=True,
        )


# ── Tab 4: 멤버 순위 ─────────────────────────────────────────────────────────
with tab4:
    freq_df = attendance_frequency(filtered_matrix)
    freq_df.index.name = t("col_rank")
    display_freq = freq_df.rename(columns={
        "user_id": t("member_label"),
        "참석 횟수": t("col_attend_count"),
    })

    st.caption(t("member_caption"))

    top_n = min(20, len(display_freq))
    fig_top = px.bar(
        display_freq.head(top_n),
        x=t("col_attend_count"),
        y=t("member_label"),
        orientation="h",
        title=t("top_n_title", n=top_n),
        color=t("col_attend_count"),
        color_continuous_scale="Purples",
        labels={t("member_label"): t("member_label")},
    )
    fig_top.update_layout(
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_top, use_container_width=True)

    st.dataframe(display_freq, use_container_width=True)
