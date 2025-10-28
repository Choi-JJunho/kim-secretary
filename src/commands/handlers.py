"""Slash command handlers"""

import json
import logging
from datetime import datetime

import pytz

logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


def register_slash_commands(app):
  """Register all slash command handlers"""

  @app.command("/상태")
  async def handle_status_command(ack, respond):
    """Handle /status command"""
    await ack()
    await respond("저는 건강합니다! ✅")

  @app.command("/기상테스트")
  async def handle_morning_test_command(ack, respond, client, body, logger):
    """Handle /기상테스트 command - Send test morning message"""
    await ack()

    try:
      logger.info("🧪 Morning test message command triggered")

      blocks = [
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "좋은 아침이에요! 오늘도 화이팅! 💪"
          }
        },
        {
          "type": "actions",
          "elements": [
            {
              "type": "button",
              "text": {
                "type": "plain_text",
                "text": "기상 완료"
              },
              "action_id": "wake_up_complete",
              "style": "primary"
            }
          ]
        }
      ]

      # 채널에 public 메시지로 발송 (업데이트 가능하도록)
      channel_id = body.get("channel_id")
      await client.chat_postMessage(
          channel=channel_id,
          blocks=blocks,
          text="좋은 아침이에요! 오늘도 화이팅! 💪"
      )

      # 사용자에게는 확인 메시지만 ephemeral로
      await respond("✅ 테스트 메시지를 발송했습니다!", response_type="ephemeral")
      logger.info("✅ Morning test message sent")

    except Exception as e:
      logger.error(f"❌ Failed to send morning test message: {e}")
      await respond(f"❌ 메시지 발송 실패: {str(e)}")

  @app.command("/업무일지피드백")
  async def handle_work_log_feedback_command(ack, body, client):
    """Handle /업무일지피드백 command - Open modal for date selection"""
    try:
      logger.info("📝 Work log feedback command triggered")

      # Store channel_id in private_metadata to access it later
      import json
      private_metadata = json.dumps({
        "channel_id": body.get("channel_id"),
        "user_id": body.get("user_id")
      })

      # Open modal for date selection
      modal_view = {
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
              "initial_date": datetime.now().strftime("%Y-%m-%d"),
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
            "element": {
              "type": "static_select",
              "action_id": "feedback_flavor",
              "placeholder": {
                "type": "plain_text",
                "text": "피드백 맛 선택"
              },
              "initial_option": {
                "text": {
                  "type": "plain_text",
                  "text": "🌶️ 보통맛 (객관적)"
                },
                "value": "normal"
              },
              "options": [
                {
                  "text": {
                    "type": "plain_text",
                    "text": "🔥 매운맛 (비판적)"
                  },
                  "value": "spicy"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "🌶️ 보통맛 (객관적)"
                  },
                  "value": "normal"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "🍀 순한맛 (긍정적)"
                  },
                  "value": "mild"
                }
              ]
            },
            "label": {
              "type": "plain_text",
              "text": "피드백 맛"
            }
          },
          {
            "type": "input",
            "block_id": "ai_provider_block",
            "element": {
              "type": "static_select",
              "action_id": "ai_provider",
              "placeholder": {
                "type": "plain_text",
                "text": "AI 모델 선택"
              },
              "initial_option": {
                "text": {
                  "type": "plain_text",
                  "text": "Claude Code CLI"
                },
                "value": "claude"
              },
              "options": [
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Gemini"
                  },
                  "value": "gemini"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Claude Code CLI"
                  },
                  "value": "claude"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Codex CLI"
                  },
                  "value": "codex"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Ollama"
                  },
                  "value": "ollama"
                }
              ]
            },
            "label": {
              "type": "plain_text",
              "text": "AI 모델"
            }
          }
        ]
      }

      await client.views_open(
          trigger_id=body["trigger_id"],
          view=modal_view
      )

      # Acknowledge after modal is opened
      await ack()
      logger.info("✅ Work log feedback modal opened")

    except Exception as e:
      logger.error(f"❌ Failed to open modal: {e}")
      await ack(text=f"❌ 모달 열기 실패: {str(e)}")

  @app.command("/주간리포트")
  async def handle_weekly_report_command(ack, body, client):
    """Handle /주간리포트 command - Open modal for week selection"""
    try:
      logger.info("📅 Weekly report command triggered")

      # Get current week
      now = datetime.now(KST)
      current_year = now.year
      current_week = now.isocalendar()[1]

      # Store metadata
      private_metadata = json.dumps({
        "channel_id": body.get("channel_id"),
        "user_id": body.get("user_id")
      })

      # Open modal for week selection
      modal_view = {
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
              "initial_value": str(current_year),
              "min_value": str(current_year - 1),
              "max_value": str(current_year + 1),
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
              "initial_value": str(current_week),
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
              "text": f"현재 주차: {current_week}"
            }
          },
          {
            "type": "input",
            "block_id": "ai_provider_block",
            "element": {
              "type": "static_select",
              "action_id": "ai_provider",
              "placeholder": {
                "type": "plain_text",
                "text": "AI 모델 선택"
              },
              "initial_option": {
                "text": {
                  "type": "plain_text",
                  "text": "Claude Code CLI"
                },
                "value": "claude"
              },
              "options": [
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Gemini"
                  },
                  "value": "gemini"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Claude Code CLI"
                  },
                  "value": "claude"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Ollama"
                  },
                  "value": "ollama"
                }
              ]
            },
            "label": {
              "type": "plain_text",
              "text": "AI 모델"
            }
          }
        ]
      }

      await client.views_open(
          trigger_id=body["trigger_id"],
          view=modal_view
      )

      await ack()
      logger.info("✅ Weekly report modal opened")

    except Exception as e:
      logger.error(f"❌ Failed to open modal: {e}")
      await ack(text=f"❌ 모달 열기 실패: {str(e)}")

  @app.command("/월간리포트")
  async def handle_monthly_report_command(ack, body, client):
    """Handle /월간리포트 command - Open modal for month selection"""
    try:
      logger.info("📅 Monthly report command triggered")

      # Get current month
      now = datetime.now(KST)
      current_year = now.year
      current_month = now.month

      # Store metadata
      private_metadata = json.dumps({
        "channel_id": body.get("channel_id"),
        "user_id": body.get("user_id")
      })

      # Open modal for month selection
      modal_view = {
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
              "initial_value": str(current_year),
              "min_value": str(current_year - 1),
              "max_value": str(current_year + 1),
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
              "initial_value": str(current_month),
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
              "text": f"현재 월: {current_month}"
            }
          },
          {
            "type": "input",
            "block_id": "ai_provider_block",
            "element": {
              "type": "static_select",
              "action_id": "ai_provider",
              "placeholder": {
                "type": "plain_text",
                "text": "AI 모델 선택"
              },
              "initial_option": {
                "text": {
                  "type": "plain_text",
                  "text": "Claude Code CLI"
                },
                "value": "claude"
              },
              "options": [
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Gemini"
                  },
                  "value": "gemini"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Claude Code CLI"
                  },
                  "value": "claude"
                },
                {
                  "text": {
                    "type": "plain_text",
                    "text": "Ollama"
                  },
                  "value": "ollama"
                }
              ]
            },
            "label": {
              "type": "plain_text",
              "text": "AI 모델"
            }
          }
        ]
      }

      await client.views_open(
          trigger_id=body["trigger_id"],
          view=modal_view
      )

      await ack()
      logger.info("✅ Monthly report modal opened")

    except Exception as e:
      logger.error(f"❌ Failed to open modal: {e}")
      await ack(text=f"❌ 모달 열기 실패: {str(e)}")
