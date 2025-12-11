"""이력서 평가 Slack 핸들러

PDF 이력서 업로드 시 자동으로 직군 분류 및 평가를 수행합니다.

지원 채널:
- 토스-이력서피드백 (SLACK_RESUME_FEEDBACK_CHANNEL_ID): 토스 개발자 이력서 평가
- 카페24-이력서피드백 (CAFE24_RESUME_FEEDBACK_CHANNEL_ID): 카페24 PM/기획 이력서 평가
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Union

import aiohttp

from ..resume_evaluator.workflow import (
    ResumeEvaluationWorkflow,
    WorkflowConfig,
    EvaluationResultWithClassification,
)
from ..resume_evaluator.workflow_cafe24 import (
    Cafe24EvaluationWorkflow,
    Cafe24WorkflowConfig,
)
from ..resume_evaluator.models import EvaluationResult, EvaluationGrade, TossJobCategory
from ..resume_evaluator.job_classifier import ClassificationResult

logger = logging.getLogger(__name__)

# 채널별 회사 매핑
TOSS_RESUME_FEEDBACK_CHANNEL_ID = os.getenv("SLACK_RESUME_FEEDBACK_CHANNEL_ID", "C0A2TD94D8T")
CAFE24_RESUME_FEEDBACK_CHANNEL_ID = os.getenv("CAFE24_RESUME_FEEDBACK_CHANNEL_ID", "C0A3DBV0B4H")

# 지원되는 이력서 평가 채널 목록
RESUME_FEEDBACK_CHANNELS = {
    TOSS_RESUME_FEEDBACK_CHANNEL_ID: "toss",
    CAFE24_RESUME_FEEDBACK_CHANNEL_ID: "cafe24",
}

# 레거시 호환
RESUME_FEEDBACK_CHANNEL_ID = TOSS_RESUME_FEEDBACK_CHANNEL_ID


# 직군별 이모지 매핑
CATEGORY_EMOJI = {
    TossJobCategory.BACKEND: ":gear:",
    TossJobCategory.APP: ":iphone:",
    TossJobCategory.FRONTEND: ":computer:",
    TossJobCategory.FULLSTACK: ":tools:",
    TossJobCategory.INFRA: ":cloud:",
    TossJobCategory.QA: ":mag:",
    TossJobCategory.DEVICE: ":electric_plug:",
}


def format_classification_for_slack(classification: ClassificationResult) -> list[dict]:
    """직군 분류 결과를 Slack Block Kit 형식으로 포맷팅

    Args:
        classification: 직군 분류 결과

    Returns:
        Slack Block Kit 블록 리스트
    """
    primary = classification.primary_category
    emoji = CATEGORY_EMOJI.get(primary, ":briefcase:")

    # 신뢰도 표시
    confidence_bar = "●" * int(classification.confidence * 5) + "○" * (5 - int(classification.confidence * 5))

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "직군 분류 결과",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*추천 직군:* {emoji} *{primary.value}*"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*신뢰도:* {confidence_bar} ({classification.confidence:.0%})"
                }
            ]
        },
    ]

    # 추가 추천 직군
    if classification.secondary_categories:
        secondary_text = ", ".join([
            f"{CATEGORY_EMOJI.get(cat, ':briefcase:')} {cat.value}"
            for cat in classification.secondary_categories
        ])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*추가 추천 직군:* {secondary_text}"
            }
        })

    # 감지된 기술 스택
    if classification.skills_detected:
        skills_text = ", ".join(classification.skills_detected[:10])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*감지된 기술:* {skills_text}"
            }
        })

    # 분류 근거
    if classification.reasoning:
        reasoning = classification.reasoning[:300] + "..." if len(classification.reasoning) > 300 else classification.reasoning
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*분류 근거:* {reasoning}"
            }
        })

    return blocks


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


def format_full_result_for_slack(
    result: EvaluationResultWithClassification,
    recommended_urls: list[str] = None
) -> list[dict]:
    """직군 분류 + 평가 결과를 Slack Block Kit 형식으로 포맷팅

    Args:
        result: 분류 + 평가 결과
        recommended_urls: 추천 채용공고 URL 목록

    Returns:
        Slack Block Kit 블록 리스트
    """
    blocks = []

    # 1. 직군 분류 결과
    blocks.extend(format_classification_for_slack(result.classification))
    blocks.append({"type": "divider"})

    # 2. 추천 채용공고 URL
    if result.recommended_job_urls:
        url_links = "\n".join([f"• <{url}|채용공고 보기>" for url in result.recommended_job_urls[:3]])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:link: 추천 채용공고*\n{url_links}"
            }
        })
        blocks.append({"type": "divider"})

    # 3. 평가 결과
    blocks.extend(format_result_for_slack(result.evaluation))

    return blocks


def format_cafe24_result_for_slack(result: EvaluationResult) -> list[dict]:
    """카페24 PM 평가 결과를 Slack Block Kit 형식으로 포맷팅

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
                "text": ":office: 카페24 PM/기획 이력서 평가 결과",
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
                    "text": f":clipboard: 기획 역량: *{result.technical_skills_score}/40점*"
                },
                {
                    "type": "mrkdwn",
                    "text": f":shopping_trolley: 도메인 전문성: *{result.problem_solving_score}/25점*"
                },
                {
                    "type": "mrkdwn",
                    "text": f":rocket: 실행력/문제해결: *{result.soft_skills_score}/20점*"
                },
                {
                    "type": "mrkdwn",
                    "text": f":handshake: 소프트 스킬: *{result.domain_fit_score}/15점*"
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
                "text": f":robot_face: AI: {result.evaluator_model} | :office: 카페24 PM 평가 기준"
            }
        ]
    })

    return blocks


async def _download_slack_file(url: str, token: str) -> bytes:
    """Slack 파일 다운로드"""
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"파일 다운로드 실패: HTTP {response.status}")
            return await response.read()


async def evaluate_resume_with_classification(
    file_url: str,
    file_name: str,
    token: str,
    ai_provider: str = "claude"
) -> EvaluationResultWithClassification:
    """Slack에서 업로드된 이력서 파일을 직군 분류 후 평가 (토스용)

    플로우:
    1. 이력서에서 직군 자동 분류
    2. 해당 직군의 채용공고 스크래핑
    3. 이력서 평가

    Args:
        file_url: Slack 파일 URL
        file_name: 파일 이름
        token: Slack Bot Token
        ai_provider: AI 제공자

    Returns:
        EvaluationResultWithClassification: 분류 + 평가 결과
    """
    file_data = await _download_slack_file(file_url, token)

    # 임시 파일로 저장
    suffix = Path(file_name).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
        tmp_file.write(file_data)
        tmp_path = tmp_file.name

    try:
        # 데이터 디렉토리 미리 생성 (Docker 볼륨 마운트 대응)
        Path("data/resume_evaluator").mkdir(parents=True, exist_ok=True)

        # 워크플로우 설정
        config = WorkflowConfig(
            ai_provider=ai_provider,
            auto_classify=True,
        )

        workflow = ResumeEvaluationWorkflow(config)

        # 직군 분류 + 평가
        result = await workflow.evaluate_with_classification(tmp_path)
        return result

    finally:
        # 임시 파일 삭제
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


async def evaluate_resume_cafe24(
    file_url: str,
    file_name: str,
    token: str,
    ai_provider: str = "claude"
) -> EvaluationResult:
    """Slack에서 업로드된 이력서 파일을 카페24 PM 기준으로 평가

    Args:
        file_url: Slack 파일 URL
        file_name: 파일 이름
        token: Slack Bot Token
        ai_provider: AI 제공자

    Returns:
        EvaluationResult: 평가 결과
    """
    file_data = await _download_slack_file(file_url, token)

    # 임시 파일로 저장
    suffix = Path(file_name).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
        tmp_file.write(file_data)
        tmp_path = tmp_file.name

    try:
        # 데이터 디렉토리 미리 생성 (Docker 볼륨 마운트 대응)
        Path("data/resume_evaluator/cafe24").mkdir(parents=True, exist_ok=True)

        # 카페24 워크플로우 설정
        config = Cafe24WorkflowConfig(
            ai_provider=ai_provider,
            target_position="PM",
        )

        workflow = Cafe24EvaluationWorkflow(config)
        await workflow.initialize()

        # 이력서 평가 (직군 분류 없이 바로 PM 기준 평가)
        result = await workflow.evaluate_resume_file(tmp_path, "PM")
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
        """파일 공유 이벤트 처리 - 이력서 평가 채널에서만 동작

        지원 채널:
        - 토스-이력서피드백: 토스 개발자 이력서 평가 (직군 자동 분류)
        - 카페24-이력서피드백: 카페24 PM/기획 이력서 평가
        """
        try:
            file_id = event.get("file_id")
            channel_id = event.get("channel_id")

            # 지원되는 이력서 평가 채널인지 확인
            company = RESUME_FEEDBACK_CHANNELS.get(channel_id)
            if not company:
                logger.debug(f"Skipping file in non-resume channel: {channel_id}")
                return

            logger.info(f"📎 File shared in {company} resume feedback channel: {file_id}")

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

            logger.info(f"📄 Resume PDF detected: {file_name} (company: {company})")

            # 진행 메시지 발송
            company_label = "토스" if company == "toss" else "카페24 PM"
            progress_msg = await client.chat_postMessage(
                channel=channel_id,
                text=f"<@{user_id}>님이 업로드한 이력서를 {company_label} 기준으로 분석 중입니다... :mag:",
                thread_ts=event.get("event_ts")  # 스레드에 답장
            )

            msg_ts = progress_msg["ts"]

            try:
                # 토큰 가져오기
                token = os.getenv("SLACK_BOT_TOKEN")

                if company == "toss":
                    # 토스: 직군 분류 + 이력서 평가
                    await client.chat_update(
                        channel=channel_id,
                        ts=msg_ts,
                        text=f"<@{user_id}>님의 이력서 직군 분류 중... :mag:"
                    )

                    result = await evaluate_resume_with_classification(
                        file_url=file_url,
                        file_name=file_name,
                        token=token,
                        ai_provider="claude"
                    )

                    # 결과 포맷팅 (분류 + 평가 + 추천 URL)
                    blocks = format_full_result_for_slack(result)

                    classification = result.classification
                    evaluation = result.evaluation

                    await client.chat_update(
                        channel=channel_id,
                        ts=msg_ts,
                        text=f"이력서 분석 완료! 추천 직군: {classification.primary_category.value}, 등급: {evaluation.grade.value} ({evaluation.total_score}점)",
                        blocks=blocks
                    )

                    logger.info(
                        f"✅ Toss resume evaluation completed: {file_name} - "
                        f"Category: {classification.primary_category.value}, "
                        f"Grade: {evaluation.grade.value}"
                    )

                elif company == "cafe24":
                    # 카페24: PM 기준 이력서 평가 (직군 분류 없음)
                    await client.chat_update(
                        channel=channel_id,
                        ts=msg_ts,
                        text=f"<@{user_id}>님의 이력서를 카페24 PM 기준으로 평가 중... :clipboard:"
                    )

                    result = await evaluate_resume_cafe24(
                        file_url=file_url,
                        file_name=file_name,
                        token=token,
                        ai_provider="claude"
                    )

                    # 결과 포맷팅 (카페24 PM 전용)
                    blocks = format_cafe24_result_for_slack(result)

                    await client.chat_update(
                        channel=channel_id,
                        ts=msg_ts,
                        text=f"카페24 PM 이력서 평가 완료! 등급: {result.grade.value} ({result.total_score}점)",
                        blocks=blocks
                    )

                    logger.info(
                        f"✅ Cafe24 PM resume evaluation completed: {file_name} - "
                        f"Grade: {result.grade.value}"
                    )

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
