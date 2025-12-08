"""포트폴리오 자동 업데이트 모듈

Claude Code CLI를 호출하여 업무일지 기반으로 about/portfolio 페이지를 업데이트합니다.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class UpdateResult(TypedDict, total=False):
  """업데이트 결과 타입"""
  success: bool
  message: str
  error: str
  commit_sha: str


# Claude Code 프롬프트 템플릿
PORTFOLIO_UPDATE_PROMPT = """
새로 추가된 업무일지를 기반으로 about 페이지와 portfolio 페이지를 업데이트해주세요.

## 새로운 업무일지 내용
날짜: {date}
제목: {title}
내용:
{content}

## 업데이트 규칙

### 1. 형식 유지 (매우 중요)
- `app/about/page.tsx`와 `app/portfolio/page.tsx`의 기존 React/TSX 구조를 **절대 변경하지 마세요**
- 기존 컴포넌트 구조, className, 스타일링을 그대로 유지하세요
- 새로운 섹션을 추가하지 말고 기존 섹션 내의 데이터만 업데이트하세요

### 2. about/page.tsx 업데이트 대상
- **주요 성과** 섹션의 숫자(배포 횟수, 프로젝트 수 등)가 증가했다면 업데이트
- **경력** 섹션의 프로젝트 설명이 더 구체화되었다면 업데이트
- 새로운 기술 스택이 있으면 **기술 스택** 섹션에 추가

### 3. portfolio/page.tsx 업데이트 대상
- **6개월 성과 요약**의 총 업무 항목, 배포 횟수 등 숫자 업데이트
- 기존 프로젝트의 **작업 건수** 증가 (예: "204건 작업" → "205건 작업")
- 새로운 **기술적 해결** 사례가 있으면 해당 프로젝트 섹션에 추가
- 새로운 **주요 성과** 항목이 있으면 해당 프로젝트 섹션에 추가

### 4. 업데이트 판단 기준
- 단순한 일상 업무(회의, 리뷰 등)는 업데이트하지 않음
- 다음 경우에만 업데이트:
  - 새로운 기술적 성과 (성능 개선, 버그 수정, 신규 기능)
  - 프로젝트 완료 또는 마일스톤 달성
  - 새로운 기술 스택 도입
  - 정량적 지표가 있는 성과 (예: "API 응답 시간 50% 개선")

### 5. 업데이트하지 않을 경우
- 업무일지 내용이 단순 업무라면 "변경 사항 없음"으로 응답하고 파일을 수정하지 마세요

## 수행할 작업
1. 위 업무일지 내용을 분석하여 포트폴리오에 반영할 가치가 있는지 판단
2. 가치가 있다면:
   - 해당 파일을 읽고 적절한 위치를 찾아 데이터만 업데이트
   - git add, commit, push 실행
3. 가치가 없다면:
   - 아무 파일도 수정하지 않고 종료

커밋 메시지 형식: "docs: Update portfolio with {date} work log"
"""


class PortfolioUpdater:
  """Claude Code를 사용한 포트폴리오 자동 업데이터

  업무일지가 발행될 때 Claude Code CLI를 호출하여
  about/portfolio 페이지의 내용을 자동으로 업데이트합니다.

  환경 변수:
    - JUNOGARDEN_REPO_PATH: junogarden-web 저장소 경로
    - CLAUDE_CODE_ENABLED: Claude Code 사용 여부 (기본값: false)
  """

  def __init__(self):
    self.repo_path = Path(
      os.getenv("JUNOGARDEN_REPO_PATH", "/app/junogarden-web")
    )
    self.enabled = os.getenv("CLAUDE_CODE_ENABLED", "true").lower() == "true"
    self.timeout = int(os.getenv("CLAUDE_CODE_TIMEOUT", "300"))  # 5분 기본값

  async def update_portfolio(
    self,
    date: str,
    title: str,
    content: str
  ) -> UpdateResult:
    """업무일지 기반으로 포트폴리오 업데이트

    Claude Code CLI를 호출하여 about/portfolio 페이지를 분석하고
    업무일지 내용을 바탕으로 적절히 업데이트합니다.

    Args:
      date: 업무일지 날짜 (YYYY-MM-DD)
      title: 업무일지 제목
      content: 업무일지 마크다운 내용

    Returns:
      UpdateResult: 업데이트 결과
    """
    if not self.enabled:
      logger.info("ℹ️ Claude Code 포트폴리오 업데이트가 비활성화되어 있습니다")
      return UpdateResult(
        success=True,
        message="Claude Code 비활성화 상태 (CLAUDE_CODE_ENABLED=false)"
      )

    if not self.repo_path.exists():
      logger.error(f"❌ 저장소 경로가 존재하지 않습니다: {self.repo_path}")
      return UpdateResult(
        success=False,
        error=f"저장소 경로 없음: {self.repo_path}"
      )

    logger.info(f"🤖 Claude Code 포트폴리오 업데이트 시작: {date}")

    # Git pull로 최신 상태 유지
    pull_success = await self._git_pull()
    if not pull_success:
      logger.warning("⚠️ Git pull 실패, 계속 진행합니다")

    # 프롬프트 생성
    prompt = PORTFOLIO_UPDATE_PROMPT.format(
      date=date,
      title=title,
      content=content[:5000]  # 내용이 너무 길면 자르기
    )

    # Claude Code CLI 실행
    result = await self._run_claude_code(prompt)

    if result["success"]:
      logger.info(f"✅ 포트폴리오 업데이트 완료: {date}")
    else:
      logger.warning(f"⚠️ 포트폴리오 업데이트 실패: {result.get('error', 'Unknown error')}")

    return result

  async def _run_claude_code(self, prompt: str) -> UpdateResult:
    """Claude Code CLI 실행

    Args:
      prompt: Claude Code에 전달할 프롬프트

    Returns:
      UpdateResult: 실행 결과
    """
    def run_sync():
      try:
        # Claude Code CLI 호출
        # --print: 결과만 출력 (인터랙티브 모드 비활성화)
        # --dangerously-skip-permissions: 권한 확인 건너뛰기 (자동화용)
        cmd = [
          "claude",
          "--print",
          "--dangerously-skip-permissions",
          prompt
        ]

        result = subprocess.run(
          cmd,
          cwd=str(self.repo_path),
          capture_output=True,
          text=True,
          timeout=self.timeout,
          env={
            **os.environ,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
          }
        )

        output = result.stdout + result.stderr

        if result.returncode == 0:
          # 커밋 SHA 추출 시도
          commit_sha = self._extract_commit_sha(output)

          # 변경 사항 없음 확인
          if "변경 사항 없음" in output or "nothing to commit" in output.lower():
            return UpdateResult(
              success=True,
              message="포트폴리오 업데이트 불필요 (단순 업무)"
            )

          return UpdateResult(
            success=True,
            message="포트폴리오 업데이트 완료",
            commit_sha=commit_sha or "unknown"
          )
        else:
          return UpdateResult(
            success=False,
            error=f"Claude Code 실행 실패: {output}"
          )

      except subprocess.TimeoutExpired:
        return UpdateResult(
          success=False,
          error=f"Claude Code 타임아웃 ({self.timeout}초)"
        )
      except FileNotFoundError:
        return UpdateResult(
          success=False,
          error="Claude Code CLI가 설치되어 있지 않습니다"
        )
      except Exception as e:
        return UpdateResult(
          success=False,
          error=f"실행 오류: {str(e)}"
        )

    return await asyncio.to_thread(run_sync)

  def _extract_commit_sha(self, output: str) -> Optional[str]:
    """출력에서 커밋 SHA 추출

    Args:
      output: Claude Code 출력

    Returns:
      커밋 SHA (7자리) 또는 None
    """
    import re
    # 일반적인 커밋 SHA 패턴 찾기
    patterns = [
      r'\[main [a-f0-9]{7}\]',  # [main abc1234]
      r'commit ([a-f0-9]{7,40})',  # commit abc1234...
      r'([a-f0-9]{7,40}) HEAD',  # abc1234 HEAD
    ]

    for pattern in patterns:
      match = re.search(pattern, output)
      if match:
        sha = match.group(1) if match.lastindex else match.group(0)
        # SHA만 추출
        sha_match = re.search(r'[a-f0-9]{7,40}', sha)
        if sha_match:
          return sha_match.group(0)[:7]

    return None


  async def _git_pull(self) -> bool:
    """Git pull로 저장소 최신화

    Returns:
      성공 여부
    """
    def run_sync():
      try:
        result = subprocess.run(
          ["git", "pull", "origin", "main"],
          cwd=str(self.repo_path),
          capture_output=True,
          text=True,
          timeout=60
        )
        if result.returncode == 0:
          logger.info("✅ Git pull 완료")
          return True
        else:
          logger.warning(f"⚠️ Git pull 실패: {result.stderr}")
          return False
      except Exception as e:
        logger.warning(f"⚠️ Git pull 예외: {e}")
        return False

    return await asyncio.to_thread(run_sync)


def get_portfolio_updater() -> PortfolioUpdater:
  """PortfolioUpdater 인스턴스 생성

  Returns:
    PortfolioUpdater 인스턴스
  """
  return PortfolioUpdater()
