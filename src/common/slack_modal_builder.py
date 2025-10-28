"""Slack 모달 생성 유틸리티"""

import json
from datetime import datetime
from typing import Dict, List, Optional

import pytz

KST = pytz.timezone('Asia/Seoul')


def create_ai_provider_select(
    initial_value: str = "claude",
    include_codex: bool = True
) -> Dict:
  """
  AI 제공자 선택 옵션을 생성합니다.

  Args:
      initial_value: 초기 선택값 (gemini, claude, ollama, codex)
      include_codex: Codex 옵션 포함 여부

  Returns:
      AI provider select element
  """
  options = [
    {
      "text": {"type": "plain_text", "text": "Gemini"},
      "value": "gemini"
    },
    {
      "text": {"type": "plain_text", "text": "Claude Code CLI"},
      "value": "claude"
    }
  ]

  if include_codex:
    options.append({
      "text": {"type": "plain_text", "text": "Codex CLI"},
      "value": "codex"
    })

  options.append({
    "text": {"type": "plain_text", "text": "Ollama"},
    "value": "ollama"
  })

  # Find initial option
  initial_option = next(
      (opt for opt in options if opt["value"] == initial_value),
      options[1]  # Default to Claude
  )

  return {
    "type": "static_select",
    "action_id": "ai_provider",
    "placeholder": {
      "type": "plain_text",
      "text": "AI 모델 선택"
    },
    "initial_option": initial_option,
    "options": options
  }


def create_feedback_flavor_select(initial_value: str = "normal") -> Dict:
  """
  피드백 맛(flavor) 선택 옵션을 생성합니다.

  Args:
      initial_value: 초기 선택값 (spicy, normal, mild)

  Returns:
      Feedback flavor select element
  """
  options = [
    {
      "text": {"type": "plain_text", "text": "🔥 매운맛 (비판적)"},
      "value": "spicy"
    },
    {
      "text": {"type": "plain_text", "text": "🌶️ 보통맛 (객관적)"},
      "value": "normal"
    },
    {
      "text": {"type": "plain_text", "text": "🍀 순한맛 (긍정적)"},
      "value": "mild"
    }
  ]

  # Find initial option
  initial_option = next(
      (opt for opt in options if opt["value"] == initial_value),
      options[1]  # Default to normal
  )

  return {
    "type": "static_select",
    "action_id": "feedback_flavor",
    "placeholder": {
      "type": "plain_text",
      "text": "피드백 맛 선택"
    },
    "initial_option": initial_option,
    "options": options
  }


def create_work_log_feedback_modal(
    channel_id: str,
    user_id: str,
    initial_date: Optional[str] = None
) -> Dict:
  """
  업무일지 AI 피드백 모달을 생성합니다.

  Args:
      channel_id: Slack 채널 ID
      user_id: Slack 유저 ID
      initial_date: 초기 날짜 (YYYY-MM-DD), None이면 오늘

  Returns:
      Modal view dictionary
  """
  if not initial_date:
    initial_date = datetime.now(KST).strftime("%Y-%m-%d")

  private_metadata = json.dumps({
    "channel_id": channel_id,
    "user_id": user_id
  })

  return {
    "type": "modal",
    "callback_id": "work_log_feedback_modal",
    "private_metadata": private_metadata,
    "title": {
      "type": "plain_text",
      "text": "업무일지 AI 피드백"
    },
    "submit": {
      "type": "plain_text",
      "text": "피드백 생성"
    },
    "close": {
      "type": "plain_text",
      "text": "취소"
    },
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "AI 피드백을 생성할 업무일지 날짜를 선택하세요."
        }
      },
      {
        "type": "input",
        "block_id": "date_block",
        "element": {
          "type": "datepicker",
          "action_id": "work_log_date",
          "initial_date": initial_date,
          "placeholder": {
            "type": "plain_text",
            "text": "날짜 선택"
          }
        },
        "label": {
          "type": "plain_text",
          "text": "작성일"
        }
      },
      {
        "type": "input",
        "block_id": "feedback_flavor_block",
        "element": create_feedback_flavor_select(),
        "label": {
          "type": "plain_text",
          "text": "피드백 맛"
        }
      },
      {
        "type": "input",
        "block_id": "ai_provider_block",
        "element": create_ai_provider_select(include_codex=True),
        "label": {
          "type": "plain_text",
          "text": "AI 모델"
        }
      }
    ]
  }


def create_weekly_report_modal(
    channel_id: str,
    user_id: str,
    initial_year: Optional[int] = None,
    initial_week: Optional[int] = None
) -> Dict:
  """
  주간 리포트 생성 모달을 생성합니다.

  Args:
      channel_id: Slack 채널 ID
      user_id: Slack 유저 ID
      initial_year: 초기 연도, None이면 현재 연도
      initial_week: 초기 주차, None이면 현재 주차

  Returns:
      Modal view dictionary
  """
  now = datetime.now(KST)
  if not initial_year:
    initial_year = now.year
  if not initial_week:
    initial_week = now.isocalendar()[1]

  private_metadata = json.dumps({
    "channel_id": channel_id,
    "user_id": user_id
  })

  return {
    "type": "modal",
    "callback_id": "weekly_report_modal",
    "private_metadata": private_metadata,
    "title": {
      "type": "plain_text",
      "text": "주간 리포트 생성"
    },
    "submit": {
      "type": "plain_text",
      "text": "리포트 생성"
    },
    "close": {
      "type": "plain_text",
      "text": "취소"
    },
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "주간 리포트를 생성할 주차를 선택하세요."
        }
      },
      {
        "type": "input",
        "block_id": "year_block",
        "element": {
          "type": "number_input",
          "action_id": "report_year",
          "is_decimal_allowed": False,
          "initial_value": str(initial_year),
          "min_value": str(initial_year - 1),
          "max_value": str(initial_year + 1),
          "placeholder": {
            "type": "plain_text",
            "text": "연도 입력"
          }
        },
        "label": {
          "type": "plain_text",
          "text": "연도"
        }
      },
      {
        "type": "input",
        "block_id": "week_block",
        "element": {
          "type": "number_input",
          "action_id": "report_week",
          "is_decimal_allowed": False,
          "initial_value": str(initial_week),
          "min_value": "1",
          "max_value": "53",
          "placeholder": {
            "type": "plain_text",
            "text": "주차 입력 (1-53)"
          }
        },
        "label": {
          "type": "plain_text",
          "text": "주차 (ISO Week)"
        },
        "hint": {
          "type": "plain_text",
          "text": f"현재 주차: {initial_week}"
        }
      },
      {
        "type": "input",
        "block_id": "ai_provider_block",
        "element": create_ai_provider_select(include_codex=False),
        "label": {
          "type": "plain_text",
          "text": "AI 모델"
        }
      }
    ]
  }


def create_monthly_report_modal(
    channel_id: str,
    user_id: str,
    initial_year: Optional[int] = None,
    initial_month: Optional[int] = None
) -> Dict:
  """
  월간 리포트 생성 모달을 생성합니다.

  Args:
      channel_id: Slack 채널 ID
      user_id: Slack 유저 ID
      initial_year: 초기 연도, None이면 현재 연도
      initial_month: 초기 월, None이면 현재 월

  Returns:
      Modal view dictionary
  """
  now = datetime.now(KST)
  if not initial_year:
    initial_year = now.year
  if not initial_month:
    initial_month = now.month

  private_metadata = json.dumps({
    "channel_id": channel_id,
    "user_id": user_id
  })

  return {
    "type": "modal",
    "callback_id": "monthly_report_modal",
    "private_metadata": private_metadata,
    "title": {
      "type": "plain_text",
      "text": "월간 리포트 생성"
    },
    "submit": {
      "type": "plain_text",
      "text": "리포트 생성"
    },
    "close": {
      "type": "plain_text",
      "text": "취소"
    },
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "월간 리포트를 생성할 연월을 선택하세요."
        }
      },
      {
        "type": "input",
        "block_id": "year_block",
        "element": {
          "type": "number_input",
          "action_id": "report_year",
          "is_decimal_allowed": False,
          "initial_value": str(initial_year),
          "min_value": str(initial_year - 1),
          "max_value": str(initial_year + 1),
          "placeholder": {
            "type": "plain_text",
            "text": "연도 입력"
          }
        },
        "label": {
          "type": "plain_text",
          "text": "연도"
        }
      },
      {
        "type": "input",
        "block_id": "month_block",
        "element": {
          "type": "number_input",
          "action_id": "report_month",
          "is_decimal_allowed": False,
          "initial_value": str(initial_month),
          "min_value": "1",
          "max_value": "12",
          "placeholder": {
            "type": "plain_text",
            "text": "월 입력 (1-12)"
          }
        },
        "label": {
          "type": "plain_text",
          "text": "월"
        },
        "hint": {
          "type": "plain_text",
          "text": f"현재 월: {initial_month}"
        }
      },
      {
        "type": "input",
        "block_id": "ai_provider_block",
        "element": create_ai_provider_select(include_codex=False),
        "label": {
          "type": "plain_text",
          "text": "AI 모델"
        }
      }
    ]
  }
