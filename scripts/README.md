# 데이터베이스 초기화 스크립트

## 개요

비어있는 Notion 데이터베이스에 주간/월간 리포트 스키마를 자동으로 생성하는 스크립트입니다.

## 사전 준비

1. **Notion에서 빈 데이터베이스 생성**
   - 주간 리포트용 DB 생성
   - 월간 리포트용 DB 생성
   - (선택) 이력서 콘텐츠용 DB 생성

2. **Notion Integration 권한 설정**
   - 각 데이터베이스에 Notion Integration 연결 필요
   - 데이터베이스 우측 상단 `...` → `Connections` → Integration 추가

3. **환경 변수 설정**
   - `.env` 파일에 `NOTION_API_KEY` 설정되어 있어야 함

## 사용 방법

### 1. 주간 리포트 DB 초기화

```bash
# 가상환경 활성화 (Docker 사용 시 생략)
source .venv/bin/activate

# URL로 초기화
python scripts/init_report_databases.py \
  --type weekly \
  --db-id "https://www.notion.so/workspace/YOUR_DB_ID?v=..."

# 또는 DB ID로 직접 초기화
python scripts/init_report_databases.py \
  --type weekly \
  --db-id "29ab3645-abb5-80ea-9bb1-dcb7310735c7"
```

**생성되는 속성:**
- 주차 (Title)
- 시작일, 종료일 (Date)
- 요약, 주요성과, 배운점, 개선점 (Rich Text)
- 사용기술, 성과카테고리 (Multi-select)
- 이력서반영 (Checkbox)
- AI 생성 완료 (Select)

### 2. 월간 리포트 DB 초기화

```bash
python scripts/init_report_databases.py \
  --type monthly \
  --db-id "YOUR_MONTHLY_DB_ID"
```

**생성되는 속성:**
- 월 (Title)
- 시작일, 종료일 (Date)
- 월간요약, 핵심성과, 기술성장, 리더십경험, 문제해결사례, 역량분석, 다음달목표 (Rich Text)
- AI 생성 완료 (Select)

### 3. 업무일지 DB에 속성 추가

```bash
python scripts/init_report_databases.py \
  --type work-log \
  --db-id "YOUR_WORK_LOG_DB_ID"
```

**추가되는 속성:**
- 정량적성과 (Rich Text)
- 성과타입 (Select)
- 기술스택 (Multi-select)
- 프로젝트 (Select)

### 4. Relation 연결 (고급)

주간 리포트와 업무일지를 자동으로 연결:

```bash
python scripts/init_report_databases.py \
  --type weekly \
  --db-id "WEEKLY_REPORT_DB_ID" \
  --work-log-db "WORK_LOG_DB_ID"
```

월간 리포트와 주간 리포트를 자동으로 연결:

```bash
python scripts/init_report_databases.py \
  --type monthly \
  --db-id "MONTHLY_REPORT_DB_ID" \
  --weekly-report-db "WEEKLY_REPORT_DB_ID"
```

## Docker 환경에서 실행

```bash
docker-compose exec kim-secretary python scripts/init_report_databases.py \
  --type weekly \
  --db-id "YOUR_DB_ID"
```

## 예시: 전체 초기화 워크플로우

```bash
# 1. 주간 리포트 DB 초기화 + 업무일지 연결
python scripts/init_report_databases.py \
  --type weekly \
  --db-id "29ab3645-abb5-80ea-9bb1-dcb7310735c7" \
  --work-log-db "업무일지_DB_ID"

# 2. 월간 리포트 DB 초기화 + 주간 리포트 연결
python scripts/init_report_databases.py \
  --type monthly \
  --db-id "월간리포트_DB_ID" \
  --weekly-report-db "29ab3645-abb5-80ea-9bb1-dcb7310735c7"

# 3. 기존 업무일지 DB에 속성 추가
python scripts/init_report_databases.py \
  --type work-log \
  --db-id "업무일지_DB_ID"
```

## 주의사항

1. **Integration 권한**: 스크립트 실행 전에 반드시 각 DB에 Notion Integration을 연결해야 합니다
2. **기존 속성 보존**: 이미 같은 이름의 속성이 있으면 업데이트되지만, 기존 데이터는 보존됩니다
3. **Relation 이름**: Relation 속성 이름은 자동으로 "일지목록", "주간리포트", "월간리포트"로 생성됩니다

## 문제 해결

### "데이터베이스 연결 실패" 에러
- Notion Integration이 해당 DB에 연결되어 있는지 확인
- DB ID가 올바른지 확인 (URL에서 추출된 ID 확인)
- `.env` 파일의 `NOTION_API_KEY`가 올바른지 확인

### "ModuleNotFoundError" 에러
- 가상환경이 활성화되어 있는지 확인: `source .venv/bin/activate`
- 의존성 설치: `pip install -r requirements.txt`

### URL 파싱 실패
- URL 형식 확인: `https://www.notion.so/workspace/DATABASE_ID?v=...`
- 또는 하이픈 형식의 DB ID를 직접 사용: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

## 다음 단계

초기화 완료 후:
1. Notion에서 각 DB를 열어 속성이 정상적으로 생성되었는지 확인
2. `.env` 파일에 통합 DB ID 매핑 설정:
   ```bash
   NOTION_USER_DATABASE_MAPPING='{"USER_ID":{"alias":"홍길동","work_log_db":"xxx","weekly_report_db":"xxx","monthly_report_db":"xxx","resume_content_db":"xxx"}}'
   ```
3. Phase 2 구현 진행 (주간 리포트 생성 로직)
