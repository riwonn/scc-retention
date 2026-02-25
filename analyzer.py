"""
출석 매트릭스를 기반으로 리텐션 지표를 계산합니다.
"""
import pandas as pd


def event_summary(matrix: pd.DataFrame, detail_df: pd.DataFrame) -> pd.DataFrame:
    """
    이벤트별 요약:
    - 등록자 수, 실제 참석자 수, 신규/복귀 참석자 수, 복귀율
    """
    event_cols = list(matrix.columns)
    results = []
    cumulative_seen: set = set()

    for event in event_cols:
        attendees = set(matrix.index[matrix[event] > 0].tolist())
        new_users = attendees - cumulative_seen
        returning_users = attendees & cumulative_seen

        # 복귀율: 이전까지 온 사람 중 이번에도 온 비율
        prev_base = len(cumulative_seen)
        retention_rate = (
            len(returning_users) / prev_base * 100 if prev_base > 0 else None
        )

        # 등록자 수 (실제 참석 여부 무관)
        registered_count = (
            detail_df[detail_df["event"] == event]["user_hash"].nunique()
            if detail_df is not None
            else None
        )

        results.append(
            {
                "이벤트": event,
                "등록자": registered_count,
                "참석자": len(attendees),
                "신규": len(new_users),
                "복귀": len(returning_users),
                "복귀율(%)": round(retention_rate, 1) if retention_rate is not None else "-",
            }
        )
        cumulative_seen |= attendees

    return pd.DataFrame(results)


def attendance_frequency(matrix: pd.DataFrame) -> pd.DataFrame:
    """
    사람별 총 참석 횟수 분포 (익명화된 ID 포함).
    """
    counts = matrix.sum(axis=1).rename("참석 횟수").reset_index()
    counts.columns = ["user_id", "참석 횟수"]
    counts = counts.sort_values("참석 횟수", ascending=False).reset_index(drop=True)
    counts.index += 1  # 1부터 시작하는 순위
    return counts


def cohort_retention(matrix: pd.DataFrame) -> pd.DataFrame:
    """
    코호트 리텐션 테이블.
    코호트 = 처음 참석한 이벤트.
    각 셀: 코호트 중 N번째 이후 이벤트에도 온 비율(%).
    """
    event_cols = list(matrix.columns)
    n = len(event_cols)

    # 각 사용자의 첫 참석 이벤트 인덱스
    def first_event_idx(row):
        for i, col in enumerate(event_cols):
            if row[col] > 0:
                return i
        return None

    matrix = matrix.copy()
    matrix["cohort_idx"] = matrix.apply(first_event_idx, axis=1)
    matrix = matrix.dropna(subset=["cohort_idx"])
    matrix["cohort_idx"] = matrix["cohort_idx"].astype(int)

    cohort_data = {}
    for c_idx in range(n):
        cohort = matrix[matrix["cohort_idx"] == c_idx]
        if cohort.empty:
            continue
        cohort_size = len(cohort)
        row = {"코호트": event_cols[c_idx], "코호트 크기": cohort_size}
        for offset in range(n - c_idx):
            target_idx = c_idx + offset
            target_col = event_cols[target_idx]
            came = cohort[target_col].sum()
            row[f"+{offset}"] = round(came / cohort_size * 100, 1)
        cohort_data[c_idx] = row

    if not cohort_data:
        return pd.DataFrame()

    df = pd.DataFrame(cohort_data.values()).set_index("코호트")
    return df


def frequency_distribution(matrix: pd.DataFrame) -> pd.DataFrame:
    """몇 번 참석한 사람이 몇 명인지 분포."""
    counts = matrix.sum(axis=1)
    dist = counts.value_counts().sort_index().reset_index()
    dist.columns = ["참석 횟수", "인원 수"]
    return dist


