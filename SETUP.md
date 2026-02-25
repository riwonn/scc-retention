# 모임 리텐션 대시보드 설정 가이드

## 1. 의존성 설치

```bash
cd chess-retention
pip install -r requirements.txt
```

---

## 2. Google 서비스 계정 만들기

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 → 사용 설정된 API 및 서비스** 에서 **Google Sheets API** 활성화
4. **IAM 및 관리자 → 서비스 계정** → 서비스 계정 만들기
   - 이름 입력 후 생성
5. 만든 서비스 계정 클릭 → **키** 탭 → **키 추가 → 새 키 만들기 → JSON**
6. 다운로드된 JSON 파일 내용을 `secrets.toml`에 복사 (아래 참고)

---

## 3. 스프레드시트에 서비스 계정 공유

1. 구글 스프레드시트 열기
2. 우상단 **공유** 클릭
3. 서비스 계정 이메일(`...@...iam.gserviceaccount.com`)을 **뷰어**로 추가
4. 스프레드시트 URL에서 ID 복사
   - 예: `https://docs.google.com/spreadsheets/d/`**`1AbCdEfGhIj...`**`/edit`

---

## 4. secrets.toml 설정

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

`.streamlit/secrets.toml` 파일을 열고 아래 항목을 채우세요:

```toml
password = "원하는_비밀번호"
spreadsheet_id = "스프레드시트_ID"

[gcp_service_account]
# 다운로드한 JSON 파일에서 각 필드 복사
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

> ⚠️ `private_key` 값의 줄바꿈은 반드시 `\n`으로 유지되어야 합니다.

---

## 5. 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속 후 비밀번호 입력.

---

## 6. 협업자 공유 방법

### 로컬 네트워크 내 공유
같은 Wi-Fi라면 Streamlit 실행 시 출력되는 `Network URL`을 공유.

### 원격 공유 (임시)
```bash
# ngrok 설치 후
ngrok http 8501
```
나오는 URL을 협업자에게 공유. 비밀번호로 보호됩니다.

### 상시 배포
- **Streamlit Community Cloud** (무료): GitHub private repo에 올리고 배포
  - secrets.toml은 Streamlit Cloud 설정에서 입력 (코드에 포함 X)

---

## 시트 구조 요구사항

- 각 **시트 탭** = 이벤트 1회
- 필수 컬럼:
  - 이메일 주소 컬럼 (이름에 "email" 또는 "이메일" 포함)
  - `CheckedInAt` 컬럼 (실제 참석 여부; 없으면 등록 = 참석으로 처리)
- 탭 이름이 이벤트 이름으로 표시됩니다 (예: `2024-03-01`, `3월 정기 모임`)
