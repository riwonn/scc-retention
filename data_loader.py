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
EMAIL_KEYWORDS   = ["email", "이메일"]
NAME_KEYWORDS    = ["이름", "name"]
PAYMENT_KEYWORDS  = ["결제 방법", "결제방법", "payment method", "계좌이체", "참가비"]
REFERRAL_KEYWORDS = ["알게 되셨나요", "어떻게 알게", "how did you find", "find about"]
CHECKEDIN_COL     = "CheckedInAt"
COUNT_COL         = "CheckinCount"


@st.cache_resource(ttl=300)  # 5분 캐시
def get_gspread_client():
    info = dict(st.secrets["gcp_service_account"])
    # TOML 형식에 따라 \n이 이스케이프된 경우 실제 줄바꿈으로 변환
    if "private_key" in info:
        info["private_key"] = info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def find_payment_column(df: pd.DataFrame) -> str | None:
    """결제 방법 컬럼만을 위한 정밀 탐색.
    헤더가 '결제 방법'으로 시작하는 컬럼을 최우선으로 찾고,
    없으면 고유 키워드(계좌이체·참가비)가 포함된 컬럼을 반환합니다."""
    for col in df.columns:
        c = col.strip().lower()
        if c.startswith("결제 방법") or c.startswith("결제방법"):
            return col
    for col in df.columns:
        if "계좌이체" in col or "참가비" in col:
            return col
    return None


def find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """키워드를 가장 많이 포함한 컬럼명을 반환합니다 (대소문자 무시).
    동수일 경우 먼저 나오는 컬럼 우선."""
    best_col, best_score = None, 0
    for col in df.columns:
        col_lower = col.lower()
        score = sum(1 for kw in keywords if kw.lower() in col_lower)
        if score > best_score:
            best_col, best_score = col, score
    return best_col if best_score > 0 else None


def anonymize_email(email: str) -> str:
    """이메일을 SHA-256 해시의 앞 8자리로 익명화합니다."""
    normalized = email.strip().lower()
    h = hashlib.sha256(normalized.encode()).hexdigest()
    return f"#{h[:8]}"


def debug_worksheet(spreadsheet_id: str, sheet_title: str) -> str:
    """캐시 없이 특정 시트를 직접 조회해 결과 또는 에러 메시지를 반환합니다."""
    client = get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    for ws in spreadsheet.worksheets():
        if ws.title == sheet_title:
            try:
                values = ws.get_all_values()
                return f"✅ 성공: {len(values)}행 반환 (헤더 포함)"
            except Exception as e:
                return f"❌ 예외 발생: {type(e).__name__}: {e}"
    return "❌ 시트를 찾을 수 없음"


def get_worksheet_names(spreadsheet_id: str) -> list[str]:
    """캐시 없이 스프레드시트의 모든 시트 탭 이름을 반환합니다."""
    client = get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    return [ws.title for ws in spreadsheet.worksheets()]


@st.cache_data(ttl=300)  # 5분 캐시
def load_all_events(spreadsheet_id: str) -> dict[str, pd.DataFrame]:
    """
    스프레드시트의 모든 시트 탭을 불러와 {탭이름: DataFrame} 형태로 반환합니다.
    """
    client = get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id)

    events: dict[str, pd.DataFrame] = {}
    for worksheet in spreadsheet.worksheets():
        try:
            # get_all_values() 대신 셀 범위로 직접 요청 — 시트 이름 특수문자 우회
            values = spreadsheet.values_get(
                f"'{worksheet.title.replace(chr(39), chr(39)*2)}'",
                params={"valueRenderOption": "FORMATTED_VALUE"},
            ).get("values", [])
        except Exception:
            try:
                # fallback: gid 기반으로 worksheet 객체를 통해 다시 시도
                values = worksheet.get_all_values()
            except Exception:
                continue
        if len(values) < 2:
            continue
        headers, *rows = values
        # 행 길이가 헤더보다 짧은 경우 빈 문자열로 패딩
        n = len(headers)
        rows = [r + [""] * (n - len(r)) for r in rows]
        df = pd.DataFrame(rows, columns=headers)
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
    all_dfs = []
    name_map: dict[str, str] = {}  # user_hash -> 이름

    for event_name, df in events.items():
        email_col = find_column(df, EMAIL_KEYWORDS)
        if email_col is None:
            continue

        name_col = find_column(df, NAME_KEYWORDS)
        has_checkin = CHECKEDIN_COL in df.columns

        # Filter to rows with valid emails
        email_series = df[email_col].dropna()
        email_series = email_series[email_series.astype(str).str.strip() != ""]
        if email_series.empty:
            continue

        hash_series = email_series.astype(str).str.strip().apply(anonymize_email)

        # 이름 수집 (있을 경우)
        if name_col:
            name_series = df.loc[email_series.index, name_col]
            valid_mask = name_series.notna() & (name_series.astype(str).str.strip() != "")
            name_map.update(dict(zip(
                hash_series[valid_mask],
                name_series[valid_mask].astype(str).str.strip(),
            )))

        # 실제 참석 여부
        if has_checkin:
            attended_series = df.loc[email_series.index, CHECKEDIN_COL].notna()
        else:
            attended_series = pd.Series(True, index=email_series.index)

        all_dfs.append(pd.DataFrame({
            "user_hash": hash_series.values,
            "event": event_name,
            "registered": True,
            "attended": attended_series.values,
        }))

    if not all_dfs:
        return pd.DataFrame(), pd.DataFrame()

    detail_df = pd.concat(all_dfs, ignore_index=True)

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

def build_payment_data(events: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    결제 컬럼이 있는 시트에서 결제 데이터를 추출합니다.
    반환: user_hash, name, event, paid, method 컬럼의 DataFrame
    """
    all_dfs = []
    name_map: dict[str, str] = {}

    for event_name, df in events.items():
        email_col = find_column(df, EMAIL_KEYWORDS)
        if email_col is None:
            continue

        payment_col = find_payment_column(df)
        if payment_col is None:
            continue

        name_col = find_column(df, NAME_KEYWORDS)

        email_series = df[email_col].dropna()
        email_series = email_series[email_series.astype(str).str.strip() != ""]
        if email_series.empty:
            continue

        hash_series = email_series.astype(str).str.strip().apply(anonymize_email)

        if name_col:
            name_series = df.loc[email_series.index, name_col]
            valid_mask = name_series.notna() & (
                name_series.astype(str).str.strip() != ""
            )
            name_map.update(
                dict(
                    zip(
                        hash_series[valid_mask],
                        name_series[valid_mask].astype(str).str.strip(),
                    )
                )
            )

        payment_series = df.loc[email_series.index, payment_col]
        payment_str = payment_series.astype(str).str.strip()

        # 비어있지 않으면 결제 완료 (계좌이체든 현금이든 모두 paid)
        paid_series = payment_series.notna() & (payment_str != "") & (payment_str != "nan")

        def _classify(x: str) -> str:
            xl = x.lower()
            if "입금" in x:
                return "계좌이체"
            if "직접" in x or "현금" in x or "cash" in xl:
                return "현금"
            if x and x != "nan":
                return "기타"
            return ""

        method_series = payment_str.apply(_classify).where(paid_series)

        all_dfs.append(
            pd.DataFrame(
                {
                    "user_hash": hash_series.values,
                    "event": event_name,
                    "paid": paid_series.values,
                    "method": method_series.values,
                }
            )
        )

    if not all_dfs:
        return pd.DataFrame()

    pay_df = pd.concat(all_dfs, ignore_index=True)
    pay_df["name"] = pay_df["user_hash"].map(lambda h: name_map.get(h, h))
    return pay_df


def build_referral_data(events: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    '어떻게 알게 되셨나요' 컬럼이 있는 시트에서 유입 경로 데이터를 추출합니다.
    반환: event, source 컬럼의 DataFrame
    """
    rows = []
    for event_name, df in events.items():
        referral_col = find_column(df, REFERRAL_KEYWORDS)
        if referral_col is None:
            continue
        for val in df[referral_col].dropna():
            source = str(val).strip()
            if source:
                rows.append({"event": event_name, "source": source})

    return pd.DataFrame(rows) if rows else pd.DataFrame()