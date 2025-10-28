# Kim Secretary - 이력서 마스터 설계 문서

## 개요

업무일지를 기반으로 주간/월간 리포트를 자동 생성하고, 이를 바탕으로 이력서 콘텐츠를 추천 및 관리하는 시스템입니다.

### 핵심 기능
- Notion 기반 업무일지 관리
- AI 기반 주간/월간 리포트 자동 생성
- 이력서 콘텐츠 자동 추출 및 관리
- STAR 형식 성과 자동 변환
- 역량 분석 및 개선 제안

---

## 📊 Notion DB 구조 설계

### 1. 일일 업무일지 DB (기존)

**Database Name:** 📝 Daily Work Log

#### Properties
- **날짜** (Date) - 업무 날짜
- **제목** (Title) - 업무 제목
- **내용** (Content) - 실제 업무 내용
- **기술스택** (Multi-select) - 사용한 기술들
- **프로젝트** (Select) - 어느 프로젝트인지
- **성과타입** (Select) - 개발/리뷰/회의/학습/기타
- **AI피드백** (Rich Text) - 일일 AI 피드백
- **정량적성과** (Text) - "10% 개선", "100명 사용" 등
- **주간리포트** (Relation) - 주간 리포트와 연결

---

### 2. 주간 리포트 DB (신규)

**Database Name:** 📅 Weekly Reports

#### Properties
- **주차** (Title) - "2025-W04" 형식
- **시작일** (Date) - 주간 시작일
- **종료일** (Date) - 주간 종료일
- **요약** (Rich Text) - AI 생성 주간 요약
- **주요성과** (Rich Text) - STAR 형식으로 정리된 성과들
- **사용기술** (Multi-select) - 이번 주 사용한 모든 기술
- **배운점** (Rich Text) - 이번 주 학습 내용
- **개선점** (Rich Text) - AI가 제안하는 부족한 부분
- **일지목록** (Relation) - 일일 업무일지들과 연결
- **성과카테고리** (Multi-select) - 개발/리더십/협업/문제해결 등
- **이력서반영** (Checkbox) - 이력서에 추가할 만한 성과인지
- **월간리포트** (Relation) - 월간 리포트와 연결

---

### 3. 월간 리포트 DB (신규)

**Database Name:** 📆 Monthly Reports

#### Properties
- **월** (Title) - "2025-01" 형식
- **시작일** (Date) - 월간 시작일
- **종료일** (Date) - 월간 종료일
- **월간요약** (Rich Text) - 한 달 전체 요약
- **핵심성과** (Rich Text) - 이력서에 들어갈 수준의 성과
- **기술성장** (Rich Text) - 이번 달 배운 기술들
- **리더십경험** (Rich Text) - 리더십/협업 사례
- **문제해결사례** (Rich Text) - 주요 문제 해결 스토리
- **주간리포트** (Relation) - 주간 리포트들과 연결
- **역량분석** (Rich Text) - 강점/약점 분석
- **다음달목표** (Rich Text) - 개선 액션 아이템
- **이력서업데이트** (Files) - 생성된 이력서 PDF

---

### 4. 이력서 콘텐츠 DB (신규)

**Database Name:** 💼 Resume Contents

#### Properties
- **섹션** (Select) - 경력요약/주요성과/프로젝트/기술스택
- **제목** (Title) - 콘텐츠 제목
- **내용** (Rich Text) - STAR 형식 또는 bullet points
- **기간** (Date Range) - 해당 성과의 기간
- **출처** (Relation) - 월간/주간 리포트 참조
- **우선순위** (Select) - High/Medium/Low
- **직무타입** (Multi-select) - Backend/Frontend/DevOps 등
- **키워드** (Multi-select) - 검색용 태그
- **버전** (Select) - v1.0, v2.0 등 (이력서 버전 관리)
- **사용여부** (Checkbox) - 현재 이력서에 사용 중인지
- **마지막수정일** (Last edited time) - 자동 기록

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                   Notion Workspace                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐│
│  │ Daily Logs  │→ │Weekly Reports│→ │   Monthly   ││
│  │     DB      │  │      DB      │  │  Reports DB ││
│  └─────────────┘  └──────────────┘  └─────────────┘│
│                           ↓                          │
│                  ┌──────────────┐                    │
│                  │Resume Content│                    │
│                  │      DB      │                    │
│                  └──────────────┘                    │
└─────────────────────────────────────────────────────┘
                           ↑
                           │ Notion API
                           ↓
┌─────────────────────────────────────────────────────┐
│              Kim Secretary (Python)                  │
│  ┌──────────────────────────────────────────────┐  │
│  │           Core Modules                       │  │
│  ├──────────────────────────────────────────────┤  │
│  │ notion_client.py    - Notion API 래퍼        │  │
│  │ analyzer.py         - 데이터 분석 엔진       │  │
│  │ report_generator.py - 리포트 생성기          │  │
│  │ resume_builder.py   - 이력서 생성기          │  │
│  │ ai_coach.py         - AI 코칭 엔진           │  │
│  └──────────────────────────────────────────────┘  │
│                           ↓                          │
│  ┌──────────────────────────────────────────────┐  │
│  │        External Services                     │  │
│  ├──────────────────────────────────────────────┤  │
│  │ OpenAI/Claude API - 텍스트 분석 & 생성      │  │
│  │ (Optional) Slack  - 알림 발송               │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────┐
│              Scheduled Jobs (Cron)                   │
│  - 금요일 저녁: 주간 리포트 생성                    │
│  - 월말: 월간 리포트 생성                           │
│  - 분기말: 이력서 자동 업데이트                     │
└─────────────────────────────────────────────────────┘
```

---

## 🔄 구현 워크플로우

### 주간 리포트 생성 플로우

```python
# 매주 금요일 18:00 실행
def generate_weekly_report():
    # 1. 이번 주 일일 업무일지 가져오기
    daily_logs = notion.query_database(
        database_id=DAILY_LOG_DB,
        filter={
            "property": "날짜",
            "date": {"this_week": {}}
        }
    )

    # 2. AI 분석
    analysis = ai.analyze_weekly_logs(daily_logs)
    # - 주요 성과 추출
    # - 사용 기술 집계
    # - STAR 형식 변환
    # - 개선점 제안

    # 3. 주간 리포트 페이지 생성
    weekly_report = notion.create_page(
        database_id=WEEKLY_REPORT_DB,
        properties={
            "주차": f"2025-W{week_number}",
            "요약": analysis.summary,
            "주요성과": analysis.achievements,
            "개선점": analysis.improvements,
            ...
        }
    )

    # 4. 일일 업무일지와 연결
    for log in daily_logs:
        notion.update_page(
            page_id=log.id,
            properties={
                "주간리포트": {"relation": [{"id": weekly_report.id}]}
            }
        )

    # 5. (Optional) Slack 알림
    slack.send_message(
        channel="#work-reports",
        text=f"이번 주 리포트가 생성되었습니다!\n{weekly_report.url}"
    )
```

### 월간 리포트 생성 플로우

```python
# 매월 마지막 날 실행
def generate_monthly_report():
    # 1. 이번 달 주간 리포트 가져오기
    weekly_reports = notion.query_database(
        database_id=WEEKLY_REPORT_DB,
        filter={
            "property": "시작일",
            "date": {"this_month": {}}
        }
    )

    # 2. AI 분석 (더 깊은 분석)
    analysis = ai.analyze_monthly_reports(weekly_reports)
    # - 핵심 성과만 추출 (이력서급)
    # - 기술 성장 추적
    # - 역량 분석 (강점/약점)
    # - 다음 달 목표 제안

    # 3. 월간 리포트 생성
    monthly_report = notion.create_page(
        database_id=MONTHLY_REPORT_DB,
        properties={
            "월": "2025-01",
            "월간요약": analysis.summary,
            "핵심성과": analysis.key_achievements,
            "역량분석": analysis.competency_analysis,
            "다음달목표": analysis.next_goals,
            ...
        }
    )

    # 4. 이력서 콘텐츠 자동 추출
    if analysis.resume_worthy_achievements:
        for achievement in analysis.resume_worthy_achievements:
            notion.create_page(
                database_id=RESUME_CONTENT_DB,
                properties={
                    "섹션": "주요성과",
                    "내용": achievement.star_format,
                    "출처": {"relation": [{"id": monthly_report.id}]},
                    "우선순위": "High",
                    ...
                }
            )
```

---

## 💻 핵심 모듈 구조

```
src/kim_secretary/
├── __init__.py
├── config.py                 # 설정 (Notion API 키, DB ID 등)
├── notion/
│   ├── __init__.py
│   ├── client.py            # Notion API 래퍼
│   └── models.py            # Notion 데이터 모델
├── analyzers/
│   ├── __init__.py
│   ├── weekly_analyzer.py   # 주간 분석기
│   ├── monthly_analyzer.py  # 월간 분석기
│   └── achievement_extractor.py  # 성과 추출기
├── generators/
│   ├── __init__.py
│   ├── weekly_report.py     # 주간 리포트 생성
│   ├── monthly_report.py    # 월간 리포트 생성
│   └── resume.py            # 이력서 생성
├── ai/
│   ├── __init__.py
│   ├── client.py            # OpenAI/Claude 클라이언트
│   └── prompts.py           # AI 프롬프트 템플릿
├── schedulers/
│   ├── __init__.py
│   └── jobs.py              # Cron 작업 정의
└── cli.py                   # CLI 인터페이스
```

---

## 🎯 구현 로드맵

### Phase 1: 기반 구축 (1-2주)

1. **Notion API 연동**
   - notion-client 라이브러리 설치
   - 인증 및 DB 연결 테스트
   - CRUD 기본 기능 구현

2. **데이터 모델링**
   - Pydantic 모델 정의
   - 타입 안정성 확보

3. **AI 클라이언트 구현**
   - OpenAI/Claude API 연동
   - 기본 프롬프트 템플릿

### Phase 2: 주간 리포트 (1주)

1. **주간 분석기 구현**
   - 일일 업무일지 집계
   - 기술 스택 추출
   - 성과 분류

2. **주간 리포트 생성기**
   - AI 요약 생성
   - STAR 형식 변환
   - Notion에 자동 작성

3. **스케줄러 설정**
   - 금요일 자동 실행

### Phase 3: 월간 리포트 (1주)

1. **월간 분석기 구현**
   - 주간 리포트 종합 분석
   - 역량 분석 알고리즘
   - 트렌드 분석

2. **월간 리포트 생성기**
   - 핵심 성과 필터링
   - 개선 제안 생성
   - 이력서 콘텐츠 자동 추출

### Phase 4: 이력서 생성 (1-2주)

1. **이력서 빌더**
   - 다양한 템플릿 지원
   - PDF/마크다운 출력
   - 직무별 커스터마이징

2. **이력서 콘텐츠 관리**
   - 버전 관리
   - 우선순위 기반 선택

---

## 🚀 빠른 시작 가이드

### 필요한 의존성

```bash
pip install notion-client openai anthropic pydantic python-dotenv schedule
```

### 환경 변수 설정

`.env` 파일 생성:

```bash
NOTION_API_KEY=secret_xxxxx
NOTION_DAILY_LOG_DB_ID=xxxxx
NOTION_WEEKLY_REPORT_DB_ID=xxxxx
NOTION_MONTHLY_REPORT_DB_ID=xxxxx
NOTION_RESUME_CONTENT_DB_ID=xxxxx
OPENAI_API_KEY=sk-xxxxx
# or
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### CLI 사용 예시

```bash
# 주간 리포트 생성
$ python -m kim_secretary weekly-report
주간 리포트를 생성하고 있습니다...
✅ 5개의 일일 업무일지를 분석했습니다
✅ AI 분석 완료
✅ Notion에 주간 리포트를 작성했습니다
🔗 https://notion.so/xxxxx

# 월간 리포트 생성
$ python -m kim_secretary monthly-report

# 이력서 생성
$ python -m kim_secretary resume --format pdf --output resume.pdf
```

---

## 📝 AI 분석 예시

### STAR 형식 변환

**입력 (일일 업무일지):**
```
오늘 API 응답 속도가 너무 느려서 Redis 캐싱을 추가했다.
평균 응답 시간이 2초에서 200ms로 개선됨.
```

**출력 (STAR 형식):**
```
[Situation] API 응답 속도가 평균 2초로 사용자 경험에 악영향
[Task] 성능 개선을 통해 응답 속도 최적화 필요
[Action] Redis 기반 캐싱 레이어 설계 및 구현
[Result] 평균 응답 시간 90% 개선 (2초 → 200ms)
```

### 역량 분석 예시

```
[강점]
- 백엔드 성능 최적화 경험 풍부
- Redis, DB 인덱싱 등 다양한 최적화 기법 활용
- 정량적 성과 측정 습관화

[개선 필요]
- 프론트엔드 기술 경험 부족 (React 학습 권장)
- 리더십/협업 관련 성과 기록 부족
- 제안: 다음 스프린트에서 코드 리뷰 리드 또는 테크 톡 진행

[다음 달 목표]
- React 기초 학습 및 간단한 대시보드 구현
- 팀 회고 진행 및 개선 사항 리드
- 기술 블로그 작성 1회
```

---

## 🎨 이력서 템플릿 예시

### Backend Engineer 템플릿

```markdown
# 주요 성과
- Redis 캐싱 도입으로 API 응답 속도 90% 개선 (2초 → 200ms)
- 데이터베이스 쿼리 최적화로 대용량 데이터 처리 성능 3배 향상
- 마이크로서비스 아키텍처 전환으로 배포 주기 50% 단축

# 기술 스택
**Backend:** Python, FastAPI, Django
**Database:** PostgreSQL, Redis, MongoDB
**DevOps:** Docker, Kubernetes, AWS
**Tools:** Git, GitHub Actions, Grafana

# 프로젝트 경험
## E-commerce 플랫폼 성능 개선 (2024.10 - 2025.01)
- 대용량 트래픽 처리를 위한 캐싱 전략 수립
- 주문 처리 시스템 성능 최적화
- 모니터링 대시보드 구축
```

---

## 🔮 향후 확장 가능성

### 단기 (3개월)
- Slack 봇 통합으로 리포트 알림
- 이력서 A/B 테스팅 (어떤 표현이 더 효과적인지)
- 채용 공고 분석 및 매칭 기능

### 중기 (6개월)
- 포트폴리오 웹사이트 자동 생성
- 면접 예상 질문 & 답변 준비
- 동료 피드백 수집 및 반영

### 장기 (1년)
- 업계 트렌드 분석 및 학습 추천
- 커리어 패스 시뮬레이션
- 팀 단위 역량 분석 대시보드

---

## 📚 참고 자료

- [Notion API Documentation](https://developers.notion.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [STAR 기법 가이드](https://www.themuse.com/advice/star-interview-method)
