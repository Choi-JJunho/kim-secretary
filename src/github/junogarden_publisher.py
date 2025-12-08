"""junogarden-web GitHub 저장소 관리

업무일지를 junogarden-web 블로그에 발행하는 기능을 제공합니다.
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TypedDict

logger = logging.getLogger(__name__)


class PublishResult(TypedDict, total=False):
  """발행 결과 타입"""
  success: bool
  file_path: str
  commit_sha: str
  message: str
  error: str


class JunogardenPublisher:
  """junogarden-web 저장소에 콘텐츠 발행

  업무일지를 Markdown 파일로 변환하여 Git 저장소에 커밋하고 푸시합니다.

  환경 변수:
    - JUNOGARDEN_REPO_PATH: 로컬 저장소 경로 (기본값: /app/junogarden-web)
    - GITHUB_TOKEN: GitHub Personal Access Token (repo 권한 필요)
    - GITHUB_REPO_URL: GitHub 저장소 URL

  사용 예시:
    >>> publisher = JunogardenPublisher()
    >>> result = await publisher.publish_work_log(
    ...     date="2025-12-08",
    ...     content="## 오늘 한 일\\n- 기능 개발",
    ...     title="2025-12-08 업무일지"
    ... )
    >>> if result["success"]:
    ...     print(f"Published: {result['commit_sha']}")
  """

  def __init__(self):
    """환경 변수에서 설정을 읽어 초기화"""
    self.repo_path = Path(
      os.getenv("JUNOGARDEN_REPO_PATH", "/app/junogarden-web")
    )
    self.github_token = os.getenv("GITHUB_TOKEN")
    self.repo_url = os.getenv(
      "GITHUB_REPO_URL",
      "https://github.com/junotech-labs/junogarden.git"
    )
    self.git_author_name = os.getenv("GIT_AUTHOR_NAME", "Secretary Bot")
    self.git_author_email = os.getenv(
      "GIT_AUTHOR_EMAIL",
      "secretary@junogarden.com"
    )

    if not self.github_token:
      logger.warning("⚠️ GITHUB_TOKEN이 설정되지 않았습니다. Git push가 실패할 수 있습니다.")

  async def ensure_repo(self) -> bool:
    """저장소가 존재하고 최신 상태인지 확인

    저장소가 없으면 clone하고, 있으면 pull합니다.

    Returns:
      성공 여부
    """
    if not self.repo_path.exists():
      logger.info(f"📥 저장소 클론 시작: {self.repo_url}")
      return await self._git_clone()
    else:
      logger.info(f"📥 저장소 업데이트: {self.repo_path}")
      return await self._git_pull()

  async def _run_command(
    self,
    cmd: List[str],
    cwd: Optional[Path] = None,
    timeout: int = 120
  ) -> tuple[bool, str]:
    """명령어 비동기 실행

    Args:
      cmd: 실행할 명령어 리스트
      cwd: 작업 디렉토리 (기본값: repo_path)
      timeout: 타임아웃 (초)

    Returns:
      (성공 여부, 출력 메시지)
    """
    work_dir = cwd or self.repo_path

    def run_sync():
      try:
        result = subprocess.run(
          cmd,
          cwd=str(work_dir),
          capture_output=True,
          text=True,
          timeout=timeout,
          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
      except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s"
      except Exception as e:
        return False, str(e)

    return await asyncio.to_thread(run_sync)

  async def _run_git(self, *args: str) -> tuple[bool, str]:
    """Git 명령어 실행

    Args:
      *args: git 명령어 인자들

    Returns:
      (성공 여부, 출력 메시지)
    """
    cmd = ["git"] + list(args)
    return await self._run_command(cmd)

  async def _git_clone(self) -> bool:
    """저장소 클론

    Returns:
      성공 여부
    """
    if not self.github_token:
      logger.error("❌ GITHUB_TOKEN이 없어 클론할 수 없습니다")
      return False

    # Token을 URL에 포함 (인증용)
    auth_url = self.repo_url.replace(
      "https://",
      f"https://{self.github_token}@"
    )

    # 부모 디렉토리 생성
    self.repo_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone", auth_url, str(self.repo_path)]
    success, output = await self._run_command(cmd, cwd=self.repo_path.parent)

    if success:
      logger.info(f"✅ 저장소 클론 완료: {self.repo_path}")
      # Git config 설정
      await self._configure_git()
    else:
      logger.error(f"❌ 저장소 클론 실패: {output}")

    return success

  async def _git_pull(self) -> bool:
    """최신 변경사항 Pull

    Returns:
      성공 여부
    """
    # 먼저 현재 브랜치 확인
    success, branch = await self._run_git("branch", "--show-current")
    if not success:
      logger.warning("⚠️ 현재 브랜치 확인 실패, main으로 시도")
      branch = "main"
    else:
      branch = branch.strip() or "main"

    success, output = await self._run_git("pull", "origin", branch)

    if success:
      logger.info(f"✅ 저장소 업데이트 완료: {branch}")
    else:
      # Pull 실패 시 강제 리셋 시도
      logger.warning(f"⚠️ Pull 실패, 강제 리셋 시도: {output}")
      await self._run_git("fetch", "origin")
      success, output = await self._run_git("reset", "--hard", f"origin/{branch}")
      if success:
        logger.info("✅ 강제 리셋으로 복구 완료")
      else:
        logger.error(f"❌ 저장소 업데이트 실패: {output}")

    return success

  async def _configure_git(self) -> None:
    """Git 설정 (user.name, user.email)"""
    await self._run_git("config", "user.name", self.git_author_name)
    await self._run_git("config", "user.email", self.git_author_email)
    logger.info(f"✅ Git 설정 완료: {self.git_author_name} <{self.git_author_email}>")

  def _generate_frontmatter(
    self,
    title: str,
    date: str,
    description: str,
    tags: Optional[List[str]] = None
  ) -> str:
    """YAML Frontmatter 생성

    Args:
      title: 제목
      date: 날짜 (YYYY-MM-DD)
      description: 설명
      tags: 태그 목록

    Returns:
      Frontmatter 문자열
    """
    tags_str = str(tags or [])
    return f"""---
title: "{title}"
date: {date}
description: "{description}"
tags: {tags_str}
---

"""

  async def publish_work_log(
    self,
    date: str,
    content: str,
    title: str,
    tags: Optional[List[str]] = None,
    description: Optional[str] = None
  ) -> PublishResult:
    """업무일지를 블로그에 발행

    Args:
      date: 날짜 (YYYY-MM-DD 형식)
      content: 마크다운 내용
      title: 제목
      tags: 태그 목록
      description: 설명 (기본값: "{date} 업무일지")

    Returns:
      PublishResult: {
        "success": bool,
        "file_path": str (성공 시),
        "commit_sha": str (성공 시),
        "message": str (변경 없을 때),
        "error": str (실패 시)
      }

    Example:
      >>> result = await publisher.publish_work_log(
      ...     date="2025-12-08",
      ...     content="## 오늘 한 일\\n- 기능 개발",
      ...     title="2025-12-08 업무일지",
      ...     tags=["개발", "Kotlin"]
      ... )
    """
    logger.info(f"📤 업무일지 발행 시작: {date}")

    # 1. 저장소 준비
    if not await self.ensure_repo():
      return PublishResult(
        success=False,
        error="저장소 준비 실패"
      )

    # 2. 파일 경로 생성
    file_path = self.repo_path / "content" / "work-logs" / "daily" / f"{date}.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 3. Frontmatter + 내용 생성
    desc = description or f"{date} 업무일지"
    frontmatter = self._generate_frontmatter(
      title=title,
      date=date,
      description=desc,
      tags=tags
    )
    full_content = frontmatter + content

    # 4. 파일 쓰기
    try:
      file_path.write_text(full_content, encoding="utf-8")
      logger.info(f"📝 파일 생성: {file_path}")
    except Exception as e:
      logger.error(f"❌ 파일 쓰기 실패: {e}")
      return PublishResult(
        success=False,
        error=f"파일 쓰기 실패: {e}"
      )

    # 5. Git add
    relative_path = file_path.relative_to(self.repo_path)
    success, output = await self._run_git("add", str(relative_path))
    if not success:
      logger.error(f"❌ Git add 실패: {output}")
      return PublishResult(
        success=False,
        error=f"Git add 실패: {output}"
      )

    # 6. Git commit
    commit_msg = f"docs: Add work log for {date}"
    success, output = await self._run_git(
      "commit",
      "-m", commit_msg,
      "--author", f"{self.git_author_name} <{self.git_author_email}>"
    )

    if not success:
      if "nothing to commit" in output.lower():
        logger.info(f"ℹ️ 변경 사항 없음: {date}")
        return PublishResult(
          success=True,
          file_path=str(file_path),
          message="변경 사항 없음"
        )
      else:
        logger.error(f"❌ Git commit 실패: {output}")
        return PublishResult(
          success=False,
          error=f"Git commit 실패: {output}"
        )

    logger.info(f"✅ Git commit 완료: {commit_msg}")

    # 7. Git push
    success, output = await self._run_git("push", "origin", "main")

    if not success:
      logger.error(f"❌ Git push 실패: {output}")
      return PublishResult(
        success=False,
        error=f"Git push 실패: {output}"
      )

    # 8. 커밋 SHA 가져오기
    _, sha_output = await self._run_git("rev-parse", "HEAD")
    commit_sha = sha_output.strip()[:7] if sha_output else "unknown"

    logger.info(f"✅ 발행 완료: {date} (commit: {commit_sha})")

    return PublishResult(
      success=True,
      file_path=str(relative_path),
      commit_sha=commit_sha
    )

  async def update_portfolio_stats(
    self,
    stats: dict
  ) -> PublishResult:
    """포트폴리오 페이지의 통계 수치 업데이트

    TODO: 구현 예정 - portfolio/page.tsx의 수치를 파싱하고 업데이트

    Args:
      stats: 업데이트할 통계 데이터
        예: {"total_tasks": 5000, "deployments": 480, "projects": 10}

    Returns:
      PublishResult
    """
    logger.warning("⚠️ update_portfolio_stats는 아직 구현되지 않았습니다")
    return PublishResult(
      success=False,
      error="기능 미구현"
    )

  async def get_work_log_count(self) -> int:
    """현재 발행된 업무일지 개수 조회

    Returns:
      업무일지 파일 개수
    """
    work_logs_dir = self.repo_path / "content" / "work-logs" / "daily"
    if not work_logs_dir.exists():
      return 0

    return len(list(work_logs_dir.glob("*.md")))
