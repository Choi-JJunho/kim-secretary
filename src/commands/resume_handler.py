"""이력서 평가 Slack 핸들러"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import aiohttp

from ..resume_evaluator.workflow import ResumeEvaluationWorkflow, WorkflowConfig
from ..resume_evaluator.models import EvaluationResult, EvaluationGrade

logger = logging.getLogger(__name__)

# 이력서 평가 채널 ID (토스-이력서피드백)
RESUME_FEEDBACK_CHANNEL_ID = os.getenv("SLACK_RESUME_FEEDBACK_CHANNEL_ID", "C0A2TD94D8T")


def format_result_for_slack(result: EvaluationResult) -> list[dict]:
    """평가 결과를 Slack Block Kit 형식으로 포맷팅

    Args:
        result: 평가 결과

    Returns:
        Slack Block Kit 블록 리스트
    """
    grade_emoji = {
        EvaluationGrade.S: ":star2:",
        EvaluationGrade.A: ":sparkles:",
        EvaluationGrade.B: ":+1:",
        EvaluationGrade.C: ":memo:",
        EvaluationGrade.D: ":warning:",
    }

    grade_description = {
        EvaluationGrade.S: "즉시 채용 권장",
        EvaluationGrade.A: "적극 면접 권장",
        EvaluationGrade.B: "면접 진행 권장",
        EvaluationGrade.C: "조건부 면접 고려",
        EvaluationGrade.D: "채용 보류 권장",
    }

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "이력서 평가 결과",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*등급:* {grade_emoji[result.grade]} {result.grade.value} ({grade_description[result.grade]})"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*총점:* {result.total_score}/100점"
                }
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*세부 점수*"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f":computer: 핵심 기술 역량: *{result.technical_skills_score}/40점*"
                },
                {
                    "type": "mrkdwn",
                    "text": f":bulb: 문제 해결 능력: *{result.problem_solving_score}/25점*"
                },
                {
                    "type": "mrkdwn",
                    "text": f":handshake: 소프트 스킬: *{result.soft_skills_score}/20점*"
                },
                {
                    "type": "mrkdwn",
                    "text": f":dart: 도메인 적합성: *{result.domain_fit_score}/15점*"
                }
            ]
        },
    ]

    # 강점
    if result.strengths:
        strengths_text = "\n".join([f":white_check_mark: {s}" for s in result.strengths[:5]])
        blocks.extend([
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:muscle: 강점*\n{strengths_text}"
                }
            }
        ])

    # 보완 필요 영역
    if result.weaknesses:
        weaknesses_text = "\n".join([f":zap: {w}" for w in result.weaknesses[:5]])
        blocks.extend([
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:wrench: 보완 필요 영역*\n{weaknesses_text}"
                }
            }
        ])

    # 추천 포지션
    if result.recommended_positions:
        positions_text = ", ".join(result.recommended_positions)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:dart: 추천 포지션:* {positions_text}"
            }
        })

    # 면접 질문
    if result.interview_questions:
        questions_text = "\n".join([f"• {q}" for q in result.interview_questions[:3]])
        blocks.extend([
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:question: 면접 시 확인 필요 사항*\n{questions_text}"
                }
            }
        ])

    # 종합 평가
    if result.summary:
        # Slack 메시지 길이 제한을 위해 요약본 줄이기
        summary = result.summary[:500] + "..." if len(result.summary) > 500 else result.summary
        blocks.extend([
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:clipboard: 종합 평가*\n{summary}"
                }
            }
        ])

    # 메타정보
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f":robot_face: AI: {result.evaluator_model}"
            }
        ]
    })

    return blocks


async def download_file(url: str, token: str) -> bytes:
    """Slack 파일 다운로드

    Args:
        url: 파일 URL
        token: Slack Bot Token

    Returns:
        파일 바이트 데이터
    """
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"파일 다운로드 실패: HTTP {response.status}")
            return await response.read()


async def evaluate_resume_from_slack(
    file_url: str,
    file_name: str,
    token: str,
    position: str = "Server Developer",
    ai_provider: str = "claude"
) -> EvaluationResult:
    """Slack에서 업로드된 이력서 파일 평가

    Args:
        file_url: Slack 파일 URL
        file_name: 파일 이름
        token: Slack Bot Token
        position: 지원 포지션
        ai_provider: AI 제공자

    Returns:
        EvaluationResult: 평가 결과
    """
    # 파일 다운로드
    file_data = await download_file(file_url, token)

    # 임시 파일로 저장
    suffix = Path(file_name).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
        tmp_file.write(file_data)
        tmp_path = tmp_file.name

    try:
        # 워크플로우 설정
        config = WorkflowConfig(
            ai_provider=ai_provider,
        )

        workflow = ResumeEvaluationWorkflow(config)

        # 시스템 프롬프트 로드 시도 (없으면 초기화)
        try:
            workflow.evaluator.load_system_prompt_from_file()
            workflow._initialized = True
        except FileNotFoundError:
            logger.info("시스템 프롬프트가 없습니다. 워크플로우 초기화를 수행합니다...")
            await workflow.initialize()

        # 이력서 평가
        result = await workflow.evaluate_resume_file(tmp_path, position)
        return result

    finally:
        # 임시 파일 삭제
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def register_resume_handler(app):
    """이력서 평가 핸들러 등록"""

    @app.event("file_shared")
    async def handle_file_shared(event, client, logger):
        """파일 공유 이벤트 처리 - 토스-이력서피드백 채널에서만 동작"""
        try:
            file_id = event.get("file_id")
            channel_id = event.get("channel_id")

            # 토스-이력서피드백 채널에서만 동작
            if channel_id != RESUME_FEEDBACK_CHANNEL_ID:
                logger.debug(f"Skipping file in non-resume channel: {channel_id}")
                return

            logger.info(f"📎 File shared in resume feedback channel: {file_id}")

            # 파일 정보 조회
            file_info = await client.files_info(file=file_id)
            file_data = file_info.get("file", {})

            file_name = file_data.get("name", "")
            file_type = file_data.get("filetype", "")
            file_url = file_data.get("url_private", "")
            user_id = file_data.get("user", "")

            # PDF 파일만 처리
            if file_type != "pdf":
                logger.debug(f"Skipping non-PDF file: {file_name} ({file_type})")
                return

            logger.info(f"📄 Resume PDF detected: {file_name}")

            # 진행 메시지 발송
            progress_msg = await client.chat_postMessage(
                channel=channel_id,
                text=f"<@{user_id}>님이 업로드한 이력서를 분석 중입니다... :mag:",
                thread_ts=event.get("event_ts")  # 스레드에 답장
            )

            msg_ts = progress_msg["ts"]

            try:
                # 토큰 가져오기
                token = os.getenv("SLACK_BOT_TOKEN")

                # 이력서 평가
                result = await evaluate_resume_from_slack(
                    file_url=file_url,
                    file_name=file_name,
                    token=token,
                    position="Server Developer",
                    ai_provider="claude"
                )

                # 결과 포맷팅
                blocks = format_result_for_slack(result)

                # 결과 메시지 업데이트
                await client.chat_update(
                    channel=channel_id,
                    ts=msg_ts,
                    text=f"이력서 평가 완료! 등급: {result.grade.value} ({result.total_score}점)",
                    blocks=blocks
                )

                logger.info(f"✅ Resume evaluation completed: {file_name} - Grade {result.grade.value}")

            except Exception as e:
                logger.error(f"❌ Resume evaluation failed: {e}", exc_info=True)

                await client.chat_update(
                    channel=channel_id,
                    ts=msg_ts,
                    text=f":x: 이력서 평가 실패: {str(e)}\n\n로그를 확인해주세요."
                )

        except Exception as e:
            logger.error(f"❌ File shared handler error: {e}", exc_info=True)

    @app.command("/이력서평가")
    async def handle_resume_evaluation_command(ack, body, client):
        """Handle /이력서평가 command - Show instructions"""
        await ack()

        user_id = body.get("user_id")
        channel_id = body.get("channel_id")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "이력서 평가 안내",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "이 채널에 *PDF 형식의 이력서*를 업로드하면 "
                        "AI가 자동으로 분석하여 평가 결과를 제공합니다.\n\n"
                        "*평가 기준:*\n"
                        "• 핵심 기술 역량 (40점)\n"
                        "• 문제 해결 능력 (25점)\n"
                        "• 소프트 스킬 (20점)\n"
                        "• 도메인 적합성 (15점)\n\n"
                        "*등급:*\n"
                        ":star2: S등급 (90-100): 즉시 채용 권장\n"
                        ":sparkles: A등급 (75-89): 적극 면접 권장\n"
                        ":+1: B등급 (60-74): 면접 진행 권장\n"
                        ":memo: C등급 (45-59): 조건부 면접 고려\n"
                        ":warning: D등급 (0-44): 채용 보류 권장"
                    )
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":point_right: *지금 바로 PDF 이력서를 업로드해보세요!*"
                }
            }
        ]

        await client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="이력서 평가 안내"
        )

        logger.info(f"✅ Resume evaluation instructions sent to {user_id}")
