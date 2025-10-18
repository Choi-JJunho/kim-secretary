"""프로젝트 전역에서 사용하는 타입 정의"""

from typing import Literal, Optional, TypedDict


# 지원하는 AI 제공자 타입
ProviderType = Literal["gemini", "claude", "ollama", "codex"]


class WorkLogProcessResult(TypedDict, total=False):
  """업무일지 피드백 처리 결과 타입"""

  success: bool
  date: str
  page_id: str
  feedback_length: int
  used_ai_provider: str
  feedback: str


class WorkLogRequest(TypedDict, total=False):
  """웹훅/모달에서 수신하는 업무일지 피드백 요청 파라미터 타입"""

  action: str
  date: str
  database_id: str
  ai_provider: ProviderType
  flavor: Literal["spicy", "normal", "mild"]
  user_id: Optional[str]
