"""
Google Sheets에서 이벤트 데이터를 불러옵니다.
각 시트 탭 = 이벤트 1회.
"""
import hashlib
import pandas as pd
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# 컬럼 탐색에 사용할 키워드
EMAIL_KEYWORDS = ["email", "이메일"]
NAME_KEYWORDS  = ["이름", "name"]
CHECKEDIN_COL  = "CheckedInAt"
COUNT_COL      = "CheckinCount"


@st.cache_resource(ttl=300)  # 5분 캐시
def get_gspread_client():
    info = dict(st.secrets["gcp_service_account"])
    # TOML 형식에 따라 \n이 이스케이프된 경우 실제 줄바꿈으로 변환
    if "private_key" in info:
        info["private_key"] = info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """키워드 중 하나가 포함된 컬럼명을 반환합니다 (대소문자 무시)."""
    for col in df.columns:
        if any(kw.lower() in col.lower() for kw in keywords):
            return col
    return None


def anonymize_email(email: str) -> str:
    """이메일을 SHA-256 해시의 앞 8자리로 익명화합니다."""
    normalized = email.strip().lower()
    h = hashlib.sha256(normalized.encode()).hexdigest()
    return f"#{h[:8]}"


@st.cache_data(ttl=300)  # 5분 캐시
def load_all_events(spreadsheet_id: str) -> dict[str, pd.DataFrame]:
    """
    스프레드시트의 모든 시트 탭을 불러와 {탭이름: DataFrame} 형태로 반환합니다.
    """
    client = get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id)

    events: dict[str, pd.DataFrame] = {}
    for worksheet in spreadsheet.worksheets():
        records = worksheet.get_all_records()
        if not records:
            continue
        df = pd.DataFrame(records)
        # 빈 문자열 → NaN
        df.replace("", pd.NA, inplace=True)
        events[worksheet.title] = df

    return events


def build_attendance_matrix(
    events: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    출석 매트릭스와 원본 행 데이터를 반환합니다.

    출석 매트릭스: rows=이름(또는 user_hash), cols=event_name, values=0/1
    행 데이터: user_id, event, registered, attended 컬럼
    """
    rows = []
    name_map: dict[str, str] = {}  # user_hash -> 이름

    for event_name, df in events.items():
        email_col = find_column(df, EMAIL_KEYWORDS)
        if email_col is None:
            continue

        name_col = find_column(df, NAME_KEYWORDS)
        has_checkin = CHECKEDIN_COL in df.columns

        for _, row in df.iterrows():
            raw_email = row.get(email_col)
            if pd.isna(raw_email):
                continue
            email_str = str(raw_email).strip()
            if not email_str:
                continue

            user_hash = anonymize_email(email_str)

            # 이름 수집 (있을 경우)
            if name_col:
                raw_name = row.get(name_col)
                if not pd.isna(raw_name) and str(raw_name).strip():
                    name_map[user_hash] = str(raw_name).strip()

            # 실제 참석 여부
            if has_checkin:
                attended = not pd.isna(row.get(CHECKEDIN_COL))
            else:
                attended = True

            rows.append(
                {
                    "user_hash": user_hash,
                    "event": event_name,
                    "registered": True,
                    "attended": attended,
                }
            )

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    detail_df = pd.DataFrame(rows)

    # 출석 매트릭스 (실제 참석자만)
    attended_df = detail_df[detail_df["attended"]]
    if attended_df.empty:
        return pd.DataFrame(), detail_df

    matrix = attended_df.pivot_table(
        index="user_hash",
        columns="event",
        values="attended",
        aggfunc="max",
        fill_value=0,
    ).astype(int)

    # 이름이 있으면 인덱스를 이름으로 교체
    matrix.index = matrix.index.map(lambda h: name_map.get(h, h))
    detail_df["user_hash"] = detail_df["user_hash"].map(lambda h: name_map.get(h, h))

    return matrix, detail_df
