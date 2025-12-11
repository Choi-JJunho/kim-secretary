# 김비서 (Kim Secretary) - Slack Bot

노션 연동 Slack 비서 봇

## 기능

### 🌅 기상 관리
- ✅ 기상 시간 기록 및 추적
- 🤖 자동 응답 및 인터랙티브 버튼
- 📊 기상 통계 조회
- ⏰ 매일 아침 6:30 자동 기상 메시지

### 📝 업무일지 AI 피드백
- 업무일지 AI 피드백 생성 (선택 가능한 tone: spicy/normal/mild)
- AI 모델 선택 (Gemini, Claude, Codex, Ollama)
- 자동 폴백 (Gemini ↔ Claude)

### 📅 주간/월간 리포트
- **수동 생성**: `/주간리포트`, `/월간리포트` 슬래시 명령어
- **배치 생성**: 누락된 주간 리포트를 일괄 생성 (비동기 5개씩 병렬 처리)
- **자동 생성**:
  - 매주 금요일 22:00 - 주간 리포트 자동 생성
  - 매월 1일 22:00 - 월간 리포트 자동 생성 (전월 리포트)
- STAR 형식의 구조화된 리포트
- 우선순위 점수 기반 핵심 성과 선별
- 🎯 이력서용 성과 추출 및 개선 조언
- 📋 이력서 기반 맞춤형 피드백
- 🔄 트렌드 분석 (기술/성과/학습)
- 🗺️ 3개월 커리어 로드맵 제공

### 🎯 성과 분석 (Achievement Analysis)
- **슬래시 명령어**: `/성과분석`로 간편하게 실행
- **기간 선택**: 특정 기간의 업무일지 일괄 분석
- **AI 기반 성과 추출**: 이력서 가치가 있는 성과만 자동 선별
- **STAR 변환**: 추출된 성과를 STAR 형식으로 자동 변환
- **우선순위 점수**: 1-10점 척도로 성과의 이력서 가치 평가
- **Notion 통합**: 분석 결과가 통합 성과 페이지에 자동 추가
- **테스트 스크립트**: 단일/배치 분석 모두 지원

### 📄 이력서 평가 (Resume Evaluation)
- **자동 직군 분류**: PDF 이력서 업로드 시 AI가 적합한 직군 자동 추천
  - Backend, Frontend, App, Full Stack, Infra, QA, Device 직군 지원
- **직군별 평가**: 분류된 직군의 토스 채용공고 기준으로 맞춤형 평가
- **토스 채용공고 스크래핑**: 최신 채용 요구사항 기반 평가 기준 자동 생성
- **100점 척도 평가**:
  - 핵심 기술 역량 (40점)
  - 문제 해결 능력 (25점)
  - 소프트 스킬 (20점)
  - 도메인 적합성 (15점)
- **등급 시스템**: S/A/B/C/D 등급 및 채용 권장 수준 제공
- **추천 채용공고 링크**: 분류된 직군의 토스 채용 페이지 자동 제공
- **Slack 전용 채널**: 특정 채널에 PDF 업로드 시 자동 평가

### 📤 업무일지 자동 발행 (Work Log Publishing)
- **Notion 연동**: Notion에서 "발행" 체크박스 클릭 시 자동 발행
- **GitHub 발행**: junogarden-web 블로그 저장소에 마크다운 파일 자동 생성
- **Git 자동화**: 커밋 및 푸시 자동 처리
- **Slack 알림**: 발행 진행 상황 및 결과 실시간 알림
- **Vercel 배포**: GitHub 푸시 시 자동 배포

## 사전 요구사항

- Python 3.13+
- Docker (크로스플랫폼 빌드 시)
- Slack Workspace 및 Bot Token
- Notion API Key 및 Database ID

## 로컬 개발

### 1. 의존성 설치

```bash
# 가상환경 생성
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일 생성:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_WAKE_UP_CHANNEL_ID=...
SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID=...
SLACK_WORK_LOG_REPORT_CHANNEL_ID=...
SLACK_REPORT_CHANNEL_ID=...
SLACK_RESUME_FEEDBACK_CHANNEL_ID=...  # 이력서 평가 전용 채널

# Notion Configuration
NOTION_API_KEY=...
NOTION_WAKE_UP_DATABASE_ID=...

# User Database Mapping (유저별 업무일지/리포트 DB)
# alias: 관리 편의를 위한 별칭
# resume_page: 이력서 페이지 ID (선택, 이력서 기반 조언 기능에 사용)
# achievements_page: 통합 성과 페이지 ID (선택, 성과 분석 결과가 이 페이지에 추가됨)
NOTION_USER_DATABASE_MAPPING='{"USER_ID":{"alias":"홍길동","work_log_db":"...","weekly_report_db":"...","monthly_report_db":"...","resume_page":"...","achievements_page":"..."}}'

# AI Provider - Gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT=5000

# GitHub Configuration (업무일지 자동 발행용)
GITHUB_TOKEN=ghp_...  # Personal Access Token (repo 권한)
GITHUB_REPO_URL=https://github.com/junotech-labs/junogarden.git
GIT_AUTHOR_NAME=Secretary Bot
GIT_AUTHOR_EMAIL=secretary@junogarden.com
```

### 3. 실행

```bash
python app.py
```

## Docker 배포

### 크로스플랫폼 빌드 (ARM → AMD64/ARM64)

ARM 기반 Mac에서 AMD64 및 ARM64용 이미지를 동시에 빌드합니다.

#### 1. Docker Buildx 설정 (최초 1회)

```bash
# buildx 버전 확인
docker buildx version

# buildx가 없으면 Docker Desktop 업데이트 또는 다음 명령어 실행
# Mac: brew install docker-buildx
```

#### 2. Docker Hub 로그인

```bash
docker login
```

#### 3. 수동 빌드 명령어

스크립트를 사용하지 않고 직접 빌드하려면:

```bash
# 1. 빌더 생성 (최초 1회)
docker buildx create --name multiplatform --use
docker buildx inspect --bootstrap

# 2. 크로스플랫폼 빌드 및 푸시
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t junho5336/kim-secretary:prod \
  --push \
  .
```

## 개발 가이드

### 프로젝트 구조

```
secretary/
├── app.py                      # 메인 애플리케이션
├── src/
│   ├── chat/                   # 채팅 핸들러
│   ├── commands/               # 슬래시 커맨드
│   │   ├── handlers.py         # 슬래시 커맨드 핸들러
│   │   ├── publish_handler.py  # 업무일지 발행 핸들러
│   │   └── resume_handler.py   # 이력서 평가 핸들러 ⭐ NEW
│   ├── github/                 # GitHub 연동
│   │   └── junogarden_publisher.py  # 블로그 발행 관리
│   ├── notion/                 # Notion API 클라이언트
│   │   ├── client.py           # 공통 클라이언트
│   │   ├── wake_up.py          # 기상 기록 관리
│   │   ├── work_log_agent.py   # 업무일지 피드백 생성
│   │   ├── weekly_report_agent.py   # 주간 리포트 생성
│   │   ├── monthly_report_agent.py  # 월간 리포트 생성
│   │   ├── achievement_agent.py     # 성과 분석 에이전트
│   │   ├── db_schema.py        # 데이터베이스 스키마 정의
│   │   └── db_initializer.py   # 데이터베이스 초기화
│   ├── resume_evaluator/       # 이력서 평가 모듈 ⭐ NEW
│   │   ├── workflow.py         # 평가 워크플로우 (분류→스크래핑→평가)
│   │   ├── job_classifier.py   # AI 기반 직군 분류기
│   │   ├── scraper.py          # 토스 채용공고 스크래퍼 (Playwright)
│   │   ├── evaluator.py        # 이력서 평가 에이전트
│   │   ├── prompt_generator.py # 평가 프롬프트 생성기
│   │   └── models.py           # 데이터 모델 (직군, 평가결과 등)
│   ├── analyzers/              # AI 분석 모듈
│   │   ├── weekly_analyzer.py  # 주간 분석 (이력서 연동)
│   │   ├── monthly_analyzer.py # 월간 분석 (이력서 연동)
│   │   └── achievement_extractor.py  # 성과 STAR 변환
│   ├── ai/                     # AI 제공자 (Gemini, Claude, Ollama)
│   ├── common/                 # 공통 유틸리티
│   │   ├── types.py            # 타입 정의
│   │   ├── notion_blocks.py    # Notion 블록 변환
│   │   └── slack_modal_builder.py  # Slack 모달 빌더
│   └── prompts/                # AI 프롬프트 템플릿
├── scripts/                    # 유틸리티 스크립트
│   ├── batch_generate_weekly_reports.py  # 주간 리포트 배치 생성
│   ├── batch_generate_monthly_reports.py # 월간 리포트 배치 생성
│   ├── test_weekly_report.py   # 주간 리포트 테스트
│   ├── test_monthly_report.py  # 월간 리포트 테스트
│   ├── test_achievement_analysis.py      # 성과 분석 테스트
│   ├── test_resume_eval.py     # 이력서 평가 테스트 ⭐ NEW
│   └── download_work_logs.py   # 업무일지 다운로드
└── Dockerfile                  # Docker 이미지 정의
```

### 코드 스타일

- Python 3.13+ 타입 힌트 사용
- 비동기 함수 (`async/await`) 활용
- 한글 주석 및 docstring

## AI 프롬프트 엔지니어링

주간/월간 리포트 생성 시 고급 프롬프트 엔지니어링 기법을 적용하여 분석 품질을 향상시켰습니다.

### 적용 기법

1. **Chain of Thought (단계별 추론)**
   - 5단계 분석 프로세스: 데이터 수집 → 우선순위 평가 → STAR 구조화 → 갭 분석 → 자기 검증
   - AI가 단계별로 사고하도록 유도하여 더 체계적인 분석 생성

2. **Priority Scoring Framework (우선순위 점수화)**
   - 주간: 20점 만점 (임팩트 5 + 난이도 5 + 정량화 5 + 이력서가치 5)
   - 월간: 25점 만점 (비즈니스임팩트 7 + 난이도 7 + 지속가능성 6 + 이력서가치 5)
   - 성과의 중요도를 정량적으로 평가하여 핵심 성과 선별

3. **Few-shot Learning (예시 학습)**
   - 각 프롬프트에 "나쁜 예시 vs 좋은 예시" 3-4개 제공
   - AI가 원하는 출력 형식과 품질을 명확히 이해

4. **Resume Gap Analysis (이력서 갭 분석)**
   - 4단계 프레임워크: 강점 파악 → 약점 식별 → 성과 매칭 → 커리어 방향
   - 이력서 개선을 위한 구체적이고 실행 가능한 조언 생성

5. **Meta-cognition (자기 검증)**
   - 출력 전 체크리스트로 품질 보증
   - 정량적 지표, STAR 논리성, 실행 가능성 등 검증

6. **Trend Analysis (트렌드 분석, 월간만)**
   - 기술/성과/학습 3가지 영역의 시간별 변화 패턴 분석
   - 단순 나열이 아닌 성장 궤적 시각화

### 프롬프트 파일

- `src/prompts/weekly_report_analysis.txt`: 주간 리포트 분석 프롬프트
- `src/prompts/monthly_report_analysis.txt`: 월간 리포트 분석 프롬프트

### 출력 품질 개선 효과

- ✅ 정량적 지표 포함률 100% 달성
- ✅ STAR 형식 구조화로 이력서 활용도 향상
- ✅ 우선순위 점수로 핵심 성과 명확화
- ✅ 실행 가능한 이력서 조언 및 커리어 로드맵 제공
- ✅ Before/After 비교로 성장 가시화

## 배치 생성

업무일지와 주간 리포트를 기반으로 누락된 리포트를 일괄 생성할 수 있습니다.

### 주간 리포트 배치 생성

업무일지를 기반으로 누락된 주간 리포트를 일괄 생성합니다.

```bash
# 기본 실행 (환경변수에서 첫 번째 유저 자동 탐지)
python3 scripts/batch_generate_weekly_reports.py

# 특정 유저 지정
python3 scripts/batch_generate_weekly_reports.py --user-id U0521JJF170

# 모든 유저에 대해 실행
python3 scripts/batch_generate_weekly_reports.py --all-users

# AI 제공자 변경 (기본값: claude)
python3 scripts/batch_generate_weekly_reports.py --ai-provider gemini

# 동시 처리 개수 변경 (기본값: 5)
python3 scripts/batch_generate_weekly_reports.py --batch-size 3
```

#### 동작 원리

1. **업무일지 조회**: 업무일지 DB에서 모든 작성일 가져오기
2. **주차 그룹화**: 날짜를 ISO 주차 기준으로 그룹화 (예: 2025-W03)
3. **누락 확인**: 주간 리포트 DB와 비교하여 누락된 주차 식별
4. **배치 생성**: 누락된 주차에 대해 5개씩 비동기 병렬 처리

#### 특징

- ✅ **비동기 처리**: asyncio.Semaphore로 동시 실행 제어
- ✅ **청크 처리**: 5개씩 묶어서 병렬 실행 (API 제한 고려)
- ✅ **자동 건너뛰기**: 업무일지가 없는 주차는 자동 건너뛰기
- ✅ **상세한 로그**: 각 주차별 생성 상태 실시간 출력
- ✅ **결과 요약**: 성공/실패/건너뛴 주차 통계 제공

#### 예상 출력

```
============================================================
👤 유저: U0521JJF170
============================================================

✅ Initialized for user U0521JJF170 (AI: claude, batch_size: 5)
📅 업무일지 날짜 조회 중...
✅ 총 45개의 업무일지 발견
📊 기존 주간 리포트 조회 중...
✅ 기존 주간 리포트: 3개
📅 업무일지가 있는 주차: 8개
🔍 생성할 주간 리포트: 5개

📋 생성 대상 주차:
  • 2025-W01 (업무일지 5개)
  • 2025-W02 (업무일지 4개)
  • 2025-W04 (업무일지 6개)
  • 2025-W05 (업무일지 3개)
  • 2025-W06 (업무일지 7개)

============================================================
📦 배치 생성 시작: 5개 주차
⚙️ 동시 처리: 5개
🤖 AI: claude
============================================================

🔄 [2025-W01] 주간 리포트 생성 시작...
🔄 [2025-W02] 주간 리포트 생성 시작...
🔄 [2025-W04] 주간 리포트 생성 시작...
🔄 [2025-W05] 주간 리포트 생성 시작...
🔄 [2025-W06] 주간 리포트 생성 시작...
✅ [2025-W01] 완료! (업무일지: 5개)
✅ [2025-W02] 완료! (업무일지: 4개)
✅ [2025-W04] 완료! (업무일지: 6개)
✅ [2025-W05] 완료! (업무일지: 3개)
✅ [2025-W06] 완료! (업무일지: 7개)

============================================================
✅ 배치 생성 완료!
============================================================
📊 총 시도: 5개
✅ 성공: 5개
⚠️ 건너뜀: 0개
❌ 실패: 0개
============================================================
```

### 월간 리포트 배치 생성

주간 리포트를 기반으로 누락된 월간 리포트를 일괄 생성합니다.

```bash
# 기본 실행 (환경변수에서 첫 번째 유저 자동 탐지)
python3 scripts/batch_generate_monthly_reports.py

# 특정 유저 지정
python3 scripts/batch_generate_monthly_reports.py --user-id U0521JJF170

# 모든 유저에 대해 실행
python3 scripts/batch_generate_monthly_reports.py --all-users

# AI 제공자 변경 (기본값: claude)
python3 scripts/batch_generate_monthly_reports.py --ai-provider gemini

# 동시 처리 개수 변경 (기본값: 3)
python3 scripts/batch_generate_monthly_reports.py --batch-size 2
```

#### 동작 원리

1. **주간 리포트 조회**: 주간 리포트 DB에서 모든 시작일 가져오기
2. **월 그룹화**: 날짜를 년-월 기준으로 그룹화 (예: 2025-01)
3. **누락 확인**: 월간 리포트 DB와 비교하여 누락된 월 식별
4. **배치 생성**: 누락된 월에 대해 3개씩 비동기 병렬 처리

#### 특징

- ✅ **비동기 처리**: asyncio.Semaphore로 동시 실행 제어
- ✅ **청크 처리**: 3개씩 묶어서 병렬 실행 (월간 리포트는 더 무거움)
- ✅ **자동 건너뛰기**: 주간 리포트가 없는 월은 자동 건너뛰기
- ✅ **상세한 로그**: 각 월별 생성 상태 실시간 출력
- ✅ **결과 요약**: 성공/실패/건너뛴 월 통계 제공

## 성과 분석 (Achievement Analysis)

업무일지에서 이력서에 활용할 수 있는 의미 있는 성과를 자동으로 추출하고 STAR 형식으로 변환합니다.

### Slack 슬래시 명령어

```
/성과분석
```

1. 모달에서 분석 기간(시작일/종료일) 선택
2. AI 모델 선택 (Claude, Gemini 등)
3. "분석 시작" 버튼 클릭
4. 분석 진행 상황을 실시간으로 확인
5. 완료 후 통합 성과 페이지에서 STAR 형식 성과 확인 (환경변수 `achievements_page` 설정 필요)

### 테스트 스크립트

성과 분석 기능을 CLI에서 테스트할 수 있습니다.

```bash
# 인터랙티브 모드 (메뉴 선택)
python3 scripts/test_achievement_analysis.py

# 1. 단일 페이지 분석
python3 scripts/test_achievement_analysis.py

# 2. 배치 분석 (기간 지정)
python3 scripts/test_achievement_analysis.py
```

#### 단일 페이지 분석

특정 업무일지 페이지를 분석합니다.

```bash
# 인터랙티브 모드
python3 scripts/test_achievement_analysis.py
# 1 선택 → 페이지 ID 입력

# Non-interactive 모드
python3 scripts/test_achievement_analysis.py 1 <page_id> [ai_provider]
```

**예시 출력:**

```
============================================================
단일 페이지 성과 분석 테스트
============================================================
분석할 페이지 ID 입력: abc123def456
AI 모델 선택 (기본값: claude): claude

============================================================
🚀 성과 분석 시작
  페이지 ID: abc123def456
  AI: CLAUDE
============================================================

⏳ 📋 업무일지 조회 중...
⏳ 📖 업무일지 내용 읽는 중...
⏳ 🔍 성과 추출 중... (내용 길이: 1234자)
⏳ ⭐ STAR 변환 중... (1/2)
⏳ ⭐ STAR 변환 중... (2/2)
⏳ 📝 통합 성과 페이지에 추가 중...
⏳ 🏁 분석 완료!

============================================================
✅ 성과 분석 완료!
============================================================

📄 페이지 ID: abc123def456
🤖 AI: CLAUDE
🎯 추출된 성과: 2개

--------------------------------------------------------------------------------
📊 추출된 성과 목록
--------------------------------------------------------------------------------

1. API 응답 속도 90% 개선
   카테고리: 개발
   우선순위: 9/10
   기술 스택: Redis, Python, API, Caching

2. 사용자 인증 시스템 구축
   카테고리: 개발
   우선순위: 8/10
   기술 스택: OAuth, JWT, Spring Boot

--------------------------------------------------------------------------------
⭐ STAR 형식 변환
--------------------------------------------------------------------------------

1. [Situation] 프로덕션 API 응답 속도가 평균 2초로 사용자 이탈률 증가
[Task] 응답 속도를 1초 이하로 개선하여 사용자 경험 향상 목표
[Action] Redis 기반 캐싱 레이어를 설계하고 구현...
[Result] 평균 응답 시간 90% 개선 (2초 → 200ms), 사용자 이탈률 15% → 5% 감소

============================================================
✨ 통합 성과 페이지에서 확인하세요: https://notion.so/2a9b3645abb580f68721c9a95c56ce45
============================================================
```

#### 배치 분석 (기간 지정)

특정 기간의 모든 업무일지를 일괄 분석합니다.

```bash
# 인터랙티브 모드
python3 scripts/test_achievement_analysis.py
# 2 선택 → 날짜 범위 입력

# Non-interactive 모드
python3 scripts/test_achievement_analysis.py 2 [start_date] [end_date] [ai_provider]

# 예시: 최근 7일 분석 (기본값)
python3 scripts/test_achievement_analysis.py 2

# 예시: 특정 기간 분석
python3 scripts/test_achievement_analysis.py 2 2025-01-01 2025-01-31 claude
```

**예시 출력:**

```
============================================================
배치 성과 분석 테스트
============================================================
시작일 입력 (YYYY-MM-DD, 기본값: 2025-01-05): 2025-01-01
종료일 입력 (YYYY-MM-DD, 기본값: 2025-01-12): 2025-01-31
AI 모델 선택 (기본값: claude): claude

============================================================
🚀 배치 성과 분석 시작
  기간: 2025-01-01 ~ 2025-01-31
  AI: CLAUDE
============================================================

📅 조회된 업무일지: 15개 (2025-01-01 ~ 2025-01-31)
⏳ 분석 중... (1/15) [1/15]
⏳ 분석 중... (2/15) [2/15]
...
⏳ 분석 중... (15/15) [15/15]

============================================================
✅ 배치 분석 완료!
============================================================

📆 기간: 2025-01-01 ~ 2025-01-31
🤖 AI: CLAUDE
📊 총 업무일지: 15개
✅ 분석 성공: 15개
❌ 분석 실패: 0개
🎯 추출된 총 성과: 23개

============================================================
✨ 통합 성과 페이지에서 확인하세요: https://notion.so/2a9b3645abb580f68721c9a95c56ce45
============================================================
```

### 작동 원리

#### 1. 성과 추출 (AI 기반)

업무일지 내용을 분석하여 이력서 가치가 있는 성과만 추출합니다.

**추출 기준:**
- ✅ 비즈니스 임팩트가 있는 작업 (매출, 사용자 수, 전환율 등)
- ✅ 기술적 난이도가 있는 작업 (새로운 기술 스택, 아키텍처 설계 등)
- ✅ 문제 해결 능력을 보여주는 작업 (버그 수정, 장애 대응 등)
- ✅ 협업 및 리더십을 보여주는 작업 (멘토링, 기술 문서 작성 등)
- ✅ 학습 및 성장을 보여주는 작업 (새로운 기술 학습 및 실전 적용)

**추출하지 않는 작업:**
- ❌ 일상적이고 반복적인 작업
- ❌ 임팩트가 미미한 작업
- ❌ 실전 적용이 없는 개인 학습

**출력 정보:**
```json
{
  "title": "성과 제목 (한 줄 요약)",
  "description": "성과 상세 설명",
  "impact": "비즈니스/기술 임팩트 (정량적 지표 포함)",
  "tech_stack": ["기술1", "기술2"],
  "category": "개발|리뷰|회의|학습|기타",
  "priority": 9,  // 이력서 가치 점수 (1-10)
  "resume_worthy": true
}
```

#### 2. STAR 형식 변환

추출된 성과를 STAR 형식으로 자동 변환합니다.

**STAR 형식:**
- **S (Situation)**: 상황/배경 - 어떤 상황이었나?
- **T (Task)**: 과제/목표 - 무엇을 해결해야 했나?
- **A (Action)**: 행동/실행 - 구체적으로 무엇을 했나?
- **R (Result)**: 결과/성과 - 어떤 결과를 얻었나? (정량적 지표 필수)

#### 3. Notion 통합

분석 결과가 통합 성과 페이지에 자동으로 추가됩니다.

**환경 변수 설정:**
- `NOTION_USER_DATABASE_MAPPING`의 `achievements_page` 필드에 통합 성과 페이지 ID 설정
- 미설정 시 성과 추출 및 STAR 변환은 수행되지만 Notion에 추가되지 않음

**추가되는 내용 (통합 성과 페이지):**
```markdown
---

## 📅 2025-01-15 - [업무일지 제목]

**원본 페이지**: [[업무일지 제목]](https://notion.so/abc123...)

### 성과 1

[Situation] ...
[Task] ...
[Action] ...
[Result] ...

### 성과 2

[Situation] ...
...
```

**통합 페이지의 장점:**
- ✅ 모든 성과를 한 곳에서 조회 가능
- ✅ 이력서 작성 시 빠른 검색 및 복사
- ✅ 원본 업무일지로 바로 이동 (링크 포함)

### 특징

- ✅ **선별적 추출**: 이력서 가치가 있는 성과만 자동 선별 (우선순위 7점 이상)
- ✅ **정량적 지표 우선**: 숫자(%, 초, 건수 등)를 포함한 성과 우대
- ✅ **STAR 자동 변환**: 추출된 성과를 즉시 STAR 형식으로 구조화
- ✅ **배치 처리 지원**: 여러 업무일지를 한 번에 분석 가능
- ✅ **AI 폴백**: Claude 실패 시 Gemini로 자동 전환
- ✅ **실시간 진행 상황**: Slack에서 분석 진행 상태 실시간 확인

## 업무일지 다운로드

Notion에 저장된 업무일지를 로컬로 다운로드할 수 있습니다.

### 사용법

```bash
# 인터랙티브 모드 (대화형으로 옵션 선택)
python3 scripts/download_work_logs.py

# Non-interactive 모드
python3 scripts/download_work_logs.py [output_dir] [format] [start_date] [end_date]

# 예시: 마크다운 형식으로 전체 다운로드
python3 scripts/download_work_logs.py ./my_logs markdown

# 예시: 특정 기간만 JSON 형식으로 다운로드
python3 scripts/download_work_logs.py ./2025_logs json 2025-01-01 2025-01-31

# 예시: 마크다운 + JSON 둘 다 저장
python3 scripts/download_work_logs.py ./backup both
```

### 출력 형식

1. **markdown**: 마크다운 파일로 저장 (`.md`)
   - 프론트매터(frontmatter)에 메타데이터 포함
   - 내용은 마크다운 형식

2. **json**: JSON 파일로 저장 (`.json`)
   - 메타데이터, 내용, 모든 속성 포함
   - 프로그래밍으로 처리하기 쉬움

3. **both**: 마크다운 + JSON 둘 다 저장

### 파일 구조

```
work_logs_export/
├── index.json                 # 전체 인덱스 (다운로드 정보 + 페이지 목록)
├── 20250101_제목.md          # 마크다운 파일
├── 20250101_제목.json        # JSON 파일
├── 20250102_제목.md
├── 20250102_제목.json
└── ...
```

#### 마크다운 파일 예시 (`20250101_API_성능_개선.md`)

```markdown
---
title: API 성능 개선 작업
date: 2025-01-01
page_id: abc123def456
url: https://notion.so/abc123def456
---

## 오늘 작업

1. Redis 캐싱 추가
2. 데이터베이스 쿼리 최적화
3. 성능 테스트

## 성과

- API 응답 시간 90% 개선 (2초 → 200ms)
- 사용자 이탈률 10% 감소
```

#### JSON 파일 예시 (`20250101_API_성능_개선.json`)

```json
{
  "metadata": {
    "page_id": "abc123def456",
    "title": "API 성능 개선 작업",
    "date": "2025-01-01",
    "url": "https://notion.so/abc123def456",
    "downloaded_at": "2025-01-12T10:30:00+09:00",
    "성과타입": "개발",
    "기술스택": ["Python", "Redis", "PostgreSQL"],
    "이력서반영": "예"
  },
  "content": "## 오늘 작업\n\n1. Redis 캐싱 추가\n...",
  "properties": {
    "작성일": { "date": { "start": "2025-01-01" } },
    "성과타입": { "select": { "name": "개발" } },
    ...
  }
}
```

#### 인덱스 파일 예시 (`index.json`)

```json
{
  "total": 15,
  "downloaded": 15,
  "failed": 0,
  "download_date": "2025-01-12T10:30:00+09:00",
  "database_id": "db123",
  "date_range": {
    "start": "2025-01-01",
    "end": "2025-01-31"
  },
  "pages": [
    {
      "page_id": "abc123",
      "title": "API 성능 개선 작업",
      "date": "2025-01-01",
      "url": "https://notion.so/abc123"
    },
    ...
  ]
}
```

### 특징

- ✅ **날짜 범위 지정**: 전체 또는 특정 기간만 선택 가능
- ✅ **메타데이터 보존**: 제목, 날짜, 속성 등 모든 정보 포함
- ✅ **마크다운 변환**: Notion 블록을 마크다운으로 변환
- ✅ **인덱스 생성**: 전체 다운로드 정보 및 페이지 목록 자동 생성
- ✅ **파일명 자동 생성**: 날짜 + 제목으로 읽기 쉬운 파일명
- ✅ **진행 상황 표시**: 실시간 다운로드 진행 상황 출력

### 활용 사례

1. **백업**: 정기적으로 로컬 백업 생성
2. **이전**: 다른 시스템으로 데이터 이전
3. **분석**: 로컬에서 텍스트 분석 또는 통계 생성
4. **아카이브**: 연도별/월별로 아카이브 생성
5. **버전 관리**: Git 등으로 변경 이력 추적

## 업무일지 자동 발행 (Work Log Publishing)

Notion에서 업무일지를 작성하고 "발행" 체크박스를 클릭하면 자동으로 junogarden-web 블로그에 발행됩니다.

### 아키텍처

```
Notion (발행 체크)
    ↓ Automation (Webhook)
Slack (메시지 수신)
    ↓ Socket Mode
Secretary Bot (처리)
    ↓ Git Push
GitHub (junogarden-web)
    ↓ Vercel Deploy
블로그 사이트
```

### 설정 방법

1. **Notion Database Property 추가**
   - `발행` (Checkbox): 체크 시 발행 트리거
   - `발행완료` (Checkbox): 발행 성공 시 자동 체크
   - `발행일시` (Date): 발행 시각 자동 기록

2. **Notion Automation 설정**
   - Trigger: `발행` property가 checked될 때
   - Action: Slack Webhook으로 JSON 전송
   ```json
   {"action":"publish_work_log","date":"{{작성일}}","page_id":"{{ID}}","user_id":"U12345678"}
   ```

3. **환경변수 설정** (위 환경변수 섹션 참조)

4. **Docker 볼륨 마운트**
   ```yaml
   volumes:
     - /root/junogarden-web:/app/junogarden-web:rw
   ```

### 사용 방법

1. Notion에서 업무일지 작성
2. 작성 완료 후 `발행` 체크박스 클릭
3. Slack에서 발행 진행 상황 및 결과 확인
4. 블로그에서 발행된 글 확인

### Slack 알림 예시

```
📤 @user 업무일지 발행 시작...
📅 날짜: 2025-12-08

⏳ Notion 페이지 로드 중...
```

```
✅ @user 업무일지 발행 완료!

📅 날짜: 2025-12-08
📄 제목: 2025-12-08 업무일지
🏷️ 태그: Kotlin, Spring
🔗 커밋: abc1234
📁 경로: content/work-logs/daily/2025-12-08.md
```

자세한 설정 가이드는 [docs/PUBLISH_WORK_LOG_SETUP.md](./docs/PUBLISH_WORK_LOG_SETUP.md)를 참고하세요.
