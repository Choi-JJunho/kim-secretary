# Python 3.13 slim 이미지 사용
FROM python:3.13-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
# Node.js와 npm 추가 (Claude Code CLI 설치용)
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI 설치
RUN npm install -g @anthropic-ai/claude-code

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium 의존성 먼저 설치 (apt 캐시 정리 후 Chromium 다운로드)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libnss3 \
        libnspr4 \
        libdbus-1-3 \
        libatk1.0-0t64 \
        libatk-bridge2.0-0t64 \
        libcups2t64 \
        libxcb1 \
        libxkbcommon0 \
        libatspi2.0-0t64 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libasound2t64 \
        libcairo2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* \
    && playwright install chromium

# 애플리케이션 코드 복사
COPY . .

# 환경 변수 설정 (기본값, .env 파일로 오버라이드 가능)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 애플리케이션 실행
CMD ["python", "app.py"]
