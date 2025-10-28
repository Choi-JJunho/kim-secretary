"""진행 상태 업데이트 관련 유틸리티"""

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


async def safe_progress_update(
    progress_callback: Optional[Callable[[str], None]],
    status: str
) -> None:
  """
  진행 상태 콜백을 안전하게 호출합니다.

  콜백 실행 중 에러가 발생해도 메인 플로우에 영향을 주지 않습니다.

  Args:
      progress_callback: 진행 상태를 받는 비동기 콜백 함수
      status: 현재 상태 메시지

  Example:
      >>> async def my_callback(status: str):
      >>>     await slack_client.update_message(status)
      >>> await safe_progress_update(my_callback, "처리 중...")
  """
  if not progress_callback:
    return

  try:
    await progress_callback(status)
  except Exception as e:
    logger.warning(f"⚠️ Progress callback failed: {e}")
    # Do not fail the main flow due to progress notification issues


def create_progress_updater(
    progress_callback: Optional[Callable[[str], None]]
) -> Callable[[str], None]:
  """
  진행 상태 업데이트 함수를 생성합니다.

  Returns:
      진행 상태를 안전하게 업데이트하는 async 함수

  Example:
      >>> update_progress = create_progress_updater(callback)
      >>> await update_progress("단계 1 완료")
      >>> await update_progress("단계 2 시작")
  """
  async def update_progress(status: str) -> None:
    await safe_progress_update(progress_callback, status)

  return update_progress
