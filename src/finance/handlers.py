"""재무관리 Slack 핸들러"""

import logging
import os
import re

from .analyzer import FinanceAnalyzer
from .state_manager import FinanceStateManager
from ..common.slack_utils import split_text_for_slack

logger = logging.getLogger(__name__)

# 재무관리 채널 ID
FINANCE_CHANNEL_ID = os.getenv("SLACK_FINANCE_CHANNEL_ID", "C0A31MH0EHM")

# 전역 분석기 인스턴스
_finance_analyzer = None


def get_finance_analyzer() -> FinanceAnalyzer:
    """재무 분석기 싱글톤"""
    global _finance_analyzer
    if _finance_analyzer is None:
        _finance_analyzer = FinanceAnalyzer()
    return _finance_analyzer


def register_finance_handlers(app):
    """재무관리 핸들러 등록"""

    @app.event("app_mention")
    async def handle_finance_mention(event, say, client, logger):
        """봇 멘션 시 CFO 응답 (재무관리 채널에서만)"""
        channel_id = event.get("channel")

        # 재무관리 채널에서만 처리
        if channel_id != FINANCE_CHANNEL_ID:
            return

        user_id = event.get("user")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")

        # 봇 멘션 제거
        text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()

        if not text:
            # 빈 멘션이면 현재 상태 표시
            text = "현재 재무 상태를 알려줘"

        logger.info(f"📊 Finance mention from {user_id}: {text}")

        try:
            # 처리 중 메시지
            processing_msg = await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="💰 재무 상담 중..."
            )

            # CFO 응답 생성
            analyzer = get_finance_analyzer()
            response = await analyzer.process_message(text)

            # 응답 업데이트
            await client.chat_update(
                channel=channel_id,
                ts=processing_msg["ts"],
                text=response
            )

            # 긴 응답은 스레드에 분할 전송
            if len(response) > 3000:
                chunks = split_text_for_slack(response)
                for i, chunk in enumerate(chunks[1:], 1):  # 첫 번째는 이미 전송됨
                    await client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text=f"(계속 {i + 1}/{len(chunks)})\n\n{chunk}"
                    )

        except Exception as e:
            logger.error(f"❌ Finance handler error: {e}", exc_info=True)
            await say(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"❌ 처리 중 오류가 발생했습니다: {str(e)}"
            )

    @app.command("/재무상태")
    async def handle_finance_status(ack, respond, command, client, logger):
        """재무 상태 조회 슬래시 명령어"""
        await ack()

        user_id = command.get("user_id")
        channel_id = command.get("channel_id")

        logger.info(f"📊 Finance status requested by {user_id}")

        try:
            state_manager = FinanceStateManager()
            dashboard_summary = state_manager.get_dashboard_summary()

            await respond(
                text=f"💰 현재 재무 상태\n\n{dashboard_summary}",
                response_type="in_channel" if channel_id == FINANCE_CHANNEL_ID else "ephemeral"
            )

        except Exception as e:
            logger.error(f"❌ Finance status error: {e}", exc_info=True)
            await respond(
                text=f"❌ 조회 실패: {str(e)}",
                response_type="ephemeral"
            )

    @app.command("/공제현황")
    async def handle_deduction_status(ack, respond, command, client, logger):
        """공제 현황 조회 슬래시 명령어"""
        await ack()

        user_id = command.get("user_id")
        channel_id = command.get("channel_id")

        logger.info(f"💳 Deduction status requested by {user_id}")

        try:
            analyzer = get_finance_analyzer()
            status = await analyzer.get_deduction_status()

            await respond(
                text=status,
                response_type="in_channel" if channel_id == FINANCE_CHANNEL_ID else "ephemeral"
            )

        except Exception as e:
            logger.error(f"❌ Deduction status error: {e}", exc_info=True)
            await respond(
                text=f"❌ 조회 실패: {str(e)}",
                response_type="ephemeral"
            )

    @app.command("/월간요약")
    async def handle_monthly_summary(ack, respond, command, client, logger):
        """월간 요약 조회 슬래시 명령어"""
        await ack()

        user_id = command.get("user_id")
        channel_id = command.get("channel_id")
        text = command.get("text", "").strip()

        logger.info(f"📊 Monthly summary requested by {user_id}: {text}")

        try:
            # 년/월 파싱 (예: "2024 12" 또는 "2024-12")
            year, month = None, None
            if text:
                parts = re.split(r'[\s\-/]', text)
                if len(parts) >= 2:
                    year = int(parts[0])
                    month = int(parts[1])
                elif len(parts) == 1 and len(parts[0]) == 6:
                    # "202412" 형식
                    year = int(parts[0][:4])
                    month = int(parts[0][4:])

            analyzer = get_finance_analyzer()
            summary = await analyzer.get_monthly_summary(year, month)

            await respond(
                text=summary,
                response_type="in_channel" if channel_id == FINANCE_CHANNEL_ID else "ephemeral"
            )

        except Exception as e:
            logger.error(f"❌ Monthly summary error: {e}", exc_info=True)
            await respond(
                text=f"❌ 조회 실패: {str(e)}\n\n사용법: /월간요약 [년 월] (예: /월간요약 2024 12)",
                response_type="ephemeral"
            )

    @app.command("/재무초기화")
    async def handle_finance_reset(ack, respond, command, client, logger):
        """재무 상태 초기화 (관리자용)"""
        await ack()

        user_id = command.get("user_id")
        text = command.get("text", "").strip()

        logger.info(f"🔄 Finance reset requested by {user_id}")

        # 확인 문구 필요
        if text != "확인":
            await respond(
                text="⚠️ 재무 상태를 초기화하려면 `/재무초기화 확인`을 입력하세요.\n"
                     "모든 거래 기록과 설정이 초기화됩니다.",
                response_type="ephemeral"
            )
            return

        try:
            analyzer = get_finance_analyzer()
            result = analyzer.reset_state()

            await respond(
                text=f"✅ 재무 상태가 초기화되었습니다.\n\n{result}",
                response_type="ephemeral"
            )

        except Exception as e:
            logger.error(f"❌ Finance reset error: {e}", exc_info=True)
            await respond(
                text=f"❌ 초기화 실패: {str(e)}",
                response_type="ephemeral"
            )

    # 재무관리 채널 메시지 리스너 (봇 멘션 없이도 특정 패턴 감지)
    @app.message(re.compile(r'^(지출|수입|소비|결제|구매|쇼핑)'))
    async def handle_finance_keywords(message, say, client, logger):
        """재무 관련 키워드 감지 (재무관리 채널에서만)"""
        channel_id = message.get("channel")

        # 재무관리 채널에서만 처리
        if channel_id != FINANCE_CHANNEL_ID:
            return

        # 봇 자신의 메시지는 무시
        if message.get("bot_id"):
            return

        text = message.get("text", "")
        user_id = message.get("user")
        thread_ts = message.get("thread_ts") or message.get("ts")

        logger.info(f"📊 Finance keyword detected from {user_id}: {text}")

        # 금액이 포함된 경우에만 처리
        if not re.search(r'\d+', text):
            return

        try:
            analyzer = get_finance_analyzer()
            response = await analyzer.process_message(text)

            # 스레드로 응답
            await say(
                channel=channel_id,
                thread_ts=thread_ts,
                text=response
            )

        except Exception as e:
            logger.error(f"❌ Finance keyword handler error: {e}", exc_info=True)

    logger.info("✅ Finance handlers registered")
