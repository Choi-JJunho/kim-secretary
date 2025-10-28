"""프로젝트 전역에서 사용하는 타입 정의"""

from typing import Any, Dict, List, Literal, Optional, TypedDict


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


# ===== Weekly/Monthly Report Types =====


class WeeklyReportRequest(TypedDict, total=False):
  """주간 리포트 생성 요청 타입"""

  year: int  # 연도
  week: int  # 주차 (ISO week number)
  work_log_database_id: str  # 일일 업무일지 DB ID (필수, 유저별 가변)
  weekly_report_database_id: str  # 주간 리포트 DB ID (필수, 유저별 가변)
  ai_provider: ProviderType  # AI 제공자
  user_id: Optional[str]  # 요청 사용자 ID


class MonthlyReportRequest(TypedDict, total=False):
  """월간 리포트 생성 요청 타입"""

  year: int  # 연도
  month: int  # 월 (1-12)
  weekly_report_database_id: str  # 주간 리포트 DB ID (필수, 유저별 가변)
  monthly_report_database_id: str  # 월간 리포트 DB ID (필수, 유저별 가변)
  ai_provider: ProviderType  # AI 제공자
  user_id: Optional[str]  # 요청 사용자 ID


class ReportProcessResult(TypedDict, total=False):
  """리포트 생성 처리 결과 타입"""

  success: bool
  report_type: Literal["weekly", "monthly"]  # 리포트 타입
  year: int
  period: int  # week number or month number
  page_id: str  # 생성된 Notion 페이지 ID
  page_url: str  # Notion 페이지 URL
  used_ai_provider: str  # 사용된 AI 제공자
  daily_logs_count: Optional[int]  # 일일 업무일지 개수 (주간)
  weekly_reports_count: Optional[int]  # 주간 리포트 개수 (월간)
  analysis: Optional[str]  # AI 분석 결과 (마크다운 텍스트)
