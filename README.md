# 김비서 (Kim Secretary) - Slack Bot

노션 연동 Slack 비서 봇

## 기능

- ✅ 기상 시간 기록 및 추적
- 🤖 자동 응답 및 인터랙티브 버튼
- 📊 기상 통계 조회

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
SLACK_SIGNING_SECRET=...
SLACK_CHANNEL_ID=...

# Notion Configuration
NOTION_API_KEY=...
NOTION_WAKE_UP_DATABASE_ID=...
NOTION_TASK_DATABASE_ID=...
NOTION_ROUTINE_DATABASE_ID=...

# Gemini (Optional)
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
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
├── app.py                 # 메인 애플리케이션
├── src/
│   ├── chat/             # 채팅 핸들러
│   ├── qa/               # Q&A 핸들러
│   ├── commands/         # 슬래시 커맨드
│   └── notion/           # Notion API 클라이언트
│       ├── client.py     # 공통 클라이언트
│       ├── wake_up.py    # 기상 기록 관리
│       ├── tasks.py      # 할 일 관리
│       └── routines.py   # 루틴 관리
├── scripts/              # 유틸리티 스크립트
└── Dockerfile            # Docker 이미지 정의
```

### 코드 스타일

- Python 3.13+ 타입 힌트 사용
- 비동기 함수 (`async/await`) 활용
- 한글 주석 및 docstring
