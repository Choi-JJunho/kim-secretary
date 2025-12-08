# 업무일지 자동 발행 설정 가이드

Notion에서 업무일지를 작성하고 "발행" 체크박스를 클릭하면 자동으로 junogarden-web 블로그에 발행되는 시스템입니다.

## 아키텍처 개요

```
Notion (발행 체크)
    ↓ Automation
Slack Webhook
    ↓ Socket Mode
Secretary Bot
    ↓ Git Push
GitHub (junogarden-web)
    ↓ Vercel Deploy
블로그 사이트
```

---

## 1. Notion Database 설정

### 필요한 Property 추가

Daily Work Log 데이터베이스에 다음 속성을 추가합니다:

| Property | Type | 용도 |
|----------|------|------|
| `발행` | Checkbox | 체크 시 발행 트리거 |
| `발행완료` | Checkbox | 발행 성공 시 자동 체크 |
| `발행일시` | Date | 발행 시각 자동 기록 |

### 기존 필수 Property

| Property | Type | 용도 |
|----------|------|------|
| `제목` 또는 `Title` | Title | 업무일지 제목 |
| `작성일` 또는 `Date` | Date | 업무일지 날짜 |
| `기술스택` 또는 `Tags` | Multi-select | 태그 (선택) |

---

## 2. Notion Automation 설정

### Step 1: Automation 생성

1. Notion 데이터베이스 우측 상단의 `⚡ Automations` 클릭
2. `+ New automation` 클릭

### Step 2: Trigger 설정

- **When**: Property changes
- **Property**: `발행`
- **Condition**: Is checked

### Step 3: Action 설정

- **Action**: Send to webhook
- **URL**: Slack Incoming Webhook URL
  ```
  https://hooks.slack.com/services/T.../B.../xxx
  ```
- **Body** (JSON):
  ```json
  {
    "text": "{\"action\":\"publish_work_log\",\"date\":\"{{작성일}}\",\"page_id\":\"{{ID}}\",\"user_id\":\"YOUR_SLACK_USER_ID\",\"update_portfolio\":false}"
  }
  ```

### 주의사항

- `{{작성일}}`은 Notion의 Date 속성 이름과 일치해야 합니다
- `{{ID}}`는 Notion 내장 변수로 페이지 ID를 자동으로 가져옵니다
- `YOUR_SLACK_USER_ID`는 실제 Slack User ID로 교체 (예: `U12345678`)
- `update_portfolio`는 포트폴리오 자동 업데이트 여부 (현재 미구현)

---

## 3. Slack Incoming Webhook 설정

### Step 1: Slack App 설정

1. https://api.slack.com/apps 접속
2. Secretary Bot 앱 선택
3. `Incoming Webhooks` 메뉴 클릭
4. `Add New Webhook to Workspace` 클릭
5. 웹훅 채널 선택 (SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID와 동일해야 함)

### Step 2: Webhook URL 복사

생성된 URL을 Notion Automation의 Webhook URL에 입력합니다.

---

## 4. 서버 환경 변수 설정

### 필수 환경 변수

```bash
# .env 파일에 추가

# GitHub Configuration
GITHUB_TOKEN=ghp_xxxxxxxxxxxx  # Personal Access Token (repo 권한)
GITHUB_REPO_URL=https://github.com/junotech-labs/junogarden.git
GIT_AUTHOR_NAME=Secretary Bot
GIT_AUTHOR_EMAIL=secretary@junogarden.com

# Slack Webhook Channel (Notion Automation이 메시지를 보내는 채널)
SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID=C12345678

# Slack Report Channel (결과 알림을 받을 채널)
SLACK_WORK_LOG_REPORT_CHANNEL_ID=C87654321
```

### GitHub Personal Access Token 발급

1. GitHub Settings → Developer settings → Personal access tokens
2. `Generate new token (classic)` 클릭
3. 필요한 권한:
   - `repo` (전체 repo 접근 권한)
4. 토큰 복사 후 `.env` 파일에 저장

---

## 5. 서버 배포

### Docker Compose로 배포

```bash
# 서버에서 junogarden-web 저장소 클론
git clone https://github.com/junotech-labs/junogarden.git /root/junogarden-web

# Secretary Bot 재배포
cd /path/to/secretary
docker compose pull
docker compose up -d
```

### 첫 실행 시 Git 설정

컨테이너 내부에서 Git 저장소가 자동으로 설정됩니다:
- 저장소가 없으면: 자동 클론
- 저장소가 있으면: 자동 pull

---

## 6. 사용 방법

### 업무일지 발행

1. Notion에서 업무일지 작성
2. 작성 완료 후 `발행` 체크박스 클릭
3. 자동으로:
   - Slack에 진행 상황 알림
   - GitHub에 마크다운 파일 생성
   - Vercel에서 자동 배포
   - Notion `발행완료` 체크 및 `발행일시` 기록

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

---

## 7. 트러블슈팅

### "page_id가 필요합니다" 오류

- Notion Automation의 JSON에서 `{{ID}}`가 올바르게 설정되었는지 확인

### "저장소 준비 실패" 오류

- `GITHUB_TOKEN`이 올바른지 확인
- 토큰에 `repo` 권한이 있는지 확인
- Docker 볼륨 마운트가 올바른지 확인

### "Git push 실패" 오류

- GitHub 토큰이 만료되었을 수 있음
- 저장소에 쓰기 권한이 있는지 확인
- 로컬 저장소와 원격 저장소의 충돌 여부 확인

### Slack 메시지가 오지 않음

- Incoming Webhook URL이 올바른지 확인
- 웹훅 채널이 `SLACK_WORK_LOG_WEBHOOK_CHANNEL_ID`와 일치하는지 확인
- Notion Automation이 활성화되어 있는지 확인

---

## 8. 파일 구조

발행된 업무일지는 다음 경로에 저장됩니다:

```
junogarden-web/
├── content/
│   └── work-logs/
│       └── daily/
│           ├── 2025-12-01.md
│           ├── 2025-12-02.md
│           └── ...
```

### Frontmatter 형식

```yaml
---
title: "2025-12-08 업무일지"
date: 2025-12-08
description: "2025-12-08 업무일지"
tags: ["Kotlin", "Spring"]
---

## 오늘 한 일

- 기능 개발
- 버그 수정
```
