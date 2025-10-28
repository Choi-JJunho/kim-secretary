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
  - 매주 금요일 18:00 - 주간 리포트 자동 생성
  - 매월 마지막 날 18:00 - 월간 리포트 자동 생성
- STAR 형식의 구조화된 리포트
- 우선순위 점수 기반 핵심 성과 선별
- 🎯 이력서용 성과 추출 및 개선 조언
- 📋 이력서 기반 맞춤형 피드백
- 🔄 트렌드 분석 (기술/성과/학습)
- 🗺️ 3개월 커리어 로드맵 제공

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

# Notion Configuration
NOTION_API_KEY=...
NOTION_WAKE_UP_DATABASE_ID=...

# User Database Mapping (유저별 업무일지/리포트 DB)
# alias: 관리 편의를 위한 별칭
# resume_page: 이력서 페이지 ID (선택, 이력서 기반 조언 기능에 사용)
NOTION_USER_DATABASE_MAPPING='{"USER_ID":{"alias":"홍길동","work_log_db":"...","weekly_report_db":"...","monthly_report_db":"...","resume_page":"..."}}'

# AI Provider - Gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT=5000
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
│   ├── notion/                 # Notion API 클라이언트
│   │   ├── client.py           # 공통 클라이언트
│   │   ├── wake_up.py          # 기상 기록 관리
│   │   ├── work_log_agent.py   # 업무일지 피드백 생성
│   │   ├── weekly_report_agent.py   # 주간 리포트 생성 (마크다운)
│   │   ├── monthly_report_agent.py  # 월간 리포트 생성 (마크다운)
│   │   ├── db_schema.py        # 데이터베이스 스키마 정의
│   │   └── db_initializer.py   # 데이터베이스 초기화 (뷰 지원)
│   ├── analyzers/              # AI 분석 모듈
│   │   ├── weekly_analyzer.py  # 주간 분석 (이력서 연동)
│   │   ├── monthly_analyzer.py # 월간 분석 (이력서 연동)
│   │   └── achievement_extractor.py  # 성과 추출 (STAR)
│   ├── ai/                     # AI 제공자 (Gemini, Claude, Ollama)
│   ├── common/                 # 공통 유틸리티
│   │   ├── types.py            # 타입 정의
│   │   └── notion_blocks.py    # Notion 블록 변환
│   └── prompts/                # AI 프롬프트 템플릿
│       ├── weekly_report_analysis.txt    # 주간 리포트 프롬프트
│       └── monthly_report_analysis.txt   # 월간 리포트 프롬프트
├── scripts/                    # 유틸리티 스크립트
│   ├── batch_generate_weekly_reports.py  # 주간 리포트 배치 생성
│   ├── batch_generate_monthly_reports.py # 월간 리포트 배치 생성
│   ├── test_weekly_report.py   # 주간 리포트 테스트
│   └── test_monthly_report.py  # 월간 리포트 테스트
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
