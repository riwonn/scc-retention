"""
체스 모임 리텐션 대시보드
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

st.set_page_config(
    page_title="모임 리텐션 분석",
    page_icon="♟️",
    layout="wide",
)


# ── 비밀번호 인증 ────────────────────────────────────────────────────────────
def check_auth():
    if st.session_state.get("authenticated"):
        return True

    st.title("♟️ 모임 리텐션 대시보드")
    st.subheader("비밀번호를 입력하세요")
    pw = st.text_input("비밀번호", type="password", key="pw_input")
    if st.button("로그인"):
        if pw == st.secrets.get("password", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()


check_auth()


# ── 데이터 로드 ──────────────────────────────────────────────────────────────
spreadsheet_id = st.secrets.get("spreadsheet_id", "")

st.title("♟️ 모임 리텐션 대시보드")

col_title, col_refresh = st.columns([8, 1])
with col_refresh:
    if st.button("🔄 새로고침"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

if not spreadsheet_id:
    st.error("`secrets.toml`에 `spreadsheet_id`를 설정해주세요.")
    st.stop()

with st.spinner("Google Sheets에서 데이터 불러오는 중..."):
    try:
        events = load_all_events(spreadsheet_id)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        st.stop()

if not events:
    st.warning("시트에 데이터가 없습니다.")
    st.stop()

matrix, detail_df = build_attendance_matrix(events)

if matrix.empty:
    st.warning("출석 데이터를 찾을 수 없습니다. 이메일 컬럼 또는 CheckedInAt 컬럼을 확인해주세요.")
    st.stop()


# ── 사이드바: 이벤트 선택 ────────────────────────────────────────────────────
all_events = list(matrix.columns)
with st.sidebar:
    st.header("필터")
    selected_events = st.multiselect(
        "분석할 이벤트 선택",
        options=all_events,
        default=all_events,
    )
    st.caption(f"전체 {len(all_events)}개 이벤트 · {matrix.shape[0]}명")

if not selected_events:
    st.warning("이벤트를 하나 이상 선택해주세요.")
    st.stop()

# 선택한 이벤트만 필터링
filtered_matrix = matrix[selected_events]
filtered_detail = detail_df[detail_df["event"].isin(selected_events)] if not detail_df.empty else detail_df


# ── 상단 KPI ─────────────────────────────────────────────────────────────────
total_unique = filtered_matrix.index.nunique()
total_events = len(selected_events)
multi_attendees = int((filtered_matrix.sum(axis=1) > 1).sum())
avg_events_per_person = filtered_matrix.sum(axis=1).mean()

k1, k2, k3, k4 = st.columns(4)
k1.metric("총 고유 참석자", f"{total_unique}명")
k2.metric("이벤트 수", f"{total_events}회")
k3.metric("2회 이상 참석자", f"{multi_attendees}명",
          help="재방문 경험이 있는 멤버 수")
k4.metric("1인당 평균 참석", f"{avg_events_per_person:.1f}회")

st.divider()


# ── 탭 ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["📅 이벤트별 요약", "📊 참석 빈도", "🔄 코호트 리텐션", "🏅 멤버 순위"]
)


# ── Tab 1: 이벤트별 요약 ─────────────────────────────────────────────────────
with tab1:
    summary_df = event_summary(filtered_matrix, filtered_detail)

    # 차트: 신규 vs 복귀
    fig_bar = px.bar(
        summary_df,
        x="이벤트",
        y=["신규", "복귀"],
        barmode="stack",
        color_discrete_map={"신규": "#4C8BF5", "복귀": "#34A853"},
        title="이벤트별 신규 / 복귀 참석자",
        labels={"value": "인원", "variable": "구분"},
    )
    fig_bar.update_layout(legend_title_text="")
    st.plotly_chart(fig_bar, use_container_width=True)

    # 복귀율 라인
    retention_vals = [
        v if v != "-" else None for v in summary_df["복귀율(%)"].tolist()
    ]
    if any(v is not None for v in retention_vals):
        fig_line = go.Figure()
        fig_line.add_trace(
            go.Scatter(
                x=summary_df["이벤트"],
                y=retention_vals,
                mode="lines+markers",
                line=dict(color="#FBBC05", width=2),
                name="복귀율(%)",
            )
        )
        fig_line.update_layout(
            title="이벤트별 복귀율 (%)",
            yaxis=dict(range=[0, 100], ticksuffix="%"),
            showlegend=False,
        )
        st.plotly_chart(fig_line, use_container_width=True)

    st.dataframe(summary_df, use_container_width=True, hide_index=True)


# ── Tab 2: 참석 빈도 분포 ────────────────────────────────────────────────────
with tab2:
    dist_df = frequency_distribution(filtered_matrix)

    fig_hist = px.bar(
        dist_df,
        x="참석 횟수",
        y="인원 수",
        title="참석 횟수 분포 (몇 번 온 사람이 몇 명인가)",
        color="인원 수",
        color_continuous_scale="Blues",
        text="인원 수",
    )
    fig_hist.update_traces(textposition="outside")
    fig_hist.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_hist, use_container_width=True)

    # 누적 비율 파이
    fig_pie = px.pie(
        dist_df,
        names="참석 횟수",
        values="인원 수",
        title="참석 횟수별 비율",
        hole=0.4,
    )
    fig_pie.update_traces(
        texttemplate="%{label}회: %{percent}",
        textposition="outside",
    )
    st.plotly_chart(fig_pie, use_container_width=True)


# ── Tab 3: 코호트 리텐션 ────────────────────────────────────────────────────
with tab3:
    cohort_df = cohort_retention(filtered_matrix)

    if cohort_df.empty:
        st.info("코호트 분석을 위한 데이터가 충분하지 않습니다.")
    else:
        st.caption("각 셀: 해당 코호트 중 N번째 이벤트에도 참석한 비율 (%)")

        # 숫자 컬럼만 히트맵
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
                hovertemplate="코호트: %{y}<br>오프셋: %{x}<br>리텐션: %{z:.1f}%<extra></extra>",
            )
        )
        fig_hm.update_layout(
            title="코호트 리텐션 히트맵",
            xaxis_title="첫 참석 기준 +N번째 이벤트",
            yaxis_title="코호트 (첫 참석 이벤트)",
            height=max(300, len(cohort_df) * 50 + 100),
        )
        st.plotly_chart(fig_hm, use_container_width=True)

        st.dataframe(
            cohort_df.style.format("{:.1f}%", subset=numeric_cols, na_rep="-"),
            use_container_width=True,
        )


# ── Tab 4: 멤버 순위 (익명화) ────────────────────────────────────────────────
with tab4:
    freq_df = attendance_frequency(filtered_matrix)
    freq_df.index.name = "순위"

    st.caption("개인정보 보호를 위해 이메일은 익명 ID로 표시됩니다.")

    # 상위 참석자 막대 차트
    top_n = min(20, len(freq_df))
    fig_top = px.bar(
        freq_df.head(top_n),
        x="참석 횟수",
        y="user_id",
        orientation="h",
        title=f"참석 횟수 상위 {top_n}명",
        color="참석 횟수",
        color_continuous_scale="Purples",
        labels={"user_id": "멤버 ID"},
    )
    fig_top.update_layout(
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_top, use_container_width=True)

    st.dataframe(freq_df, use_container_width=True)
