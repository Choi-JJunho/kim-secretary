"""Slack 메시지 포맷터 & 라벨 유틸리티"""

from typing import Optional


def flavor_emoji(flavor: str) -> str:
  mapping = {
    "spicy": "🔥",
    "normal": "🌶️",
    "mild": "🍀",
  }
  return mapping.get(flavor, "🌶️")


def flavor_label(flavor: str) -> str:
  mapping = {
    "spicy": "매운맛",
    "normal": "보통맛",
    "mild": "순한맛",
  }
  return mapping.get(flavor, flavor)


def get_used_ai_label(work_log_mgr: Optional[object], requested: str) -> str:
  """WorkLogManager의 실제 사용된 AI 제공자를 대문자 라벨로 반환"""
  used = (getattr(work_log_mgr, "last_used_ai_provider", None) or requested or "").upper()
  return used


def build_initial_text(user_mention: str, date: str, ai_label: str, flavor_line: str) -> str:
  """초기 안내 메시지 포맷"""
  return (
    f"🚀 {user_mention}업무일지 AI 피드백 생성을 시작합니다.\n\n"
    f"📅 날짜: {date}\n"
    f"🤖 AI: {ai_label}\n"
    f"{flavor_line}\n\n"
    f"⏳ 처리 중..."
  )


def build_progress_text(user_mention: str, date: str, ai_label: str, flavor_line: str, status: str) -> str:
  """진행 메시지 포맷"""
  return (
    f"🚀 {user_mention}업무일지 AI 피드백 생성 중...\n\n"
    f"📅 날짜: {date}\n"
    f"🤖 AI: {ai_label}\n"
    f"{flavor_line}\n\n"
    f"{status}"
  )

