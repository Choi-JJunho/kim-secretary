"""Slash command handlers"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


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
                  "text": "Gemini"
                },
                "value": "gemini"
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
