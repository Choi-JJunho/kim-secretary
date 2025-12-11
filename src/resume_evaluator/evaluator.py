"""이력서 평가 AI Agent"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from ..ai import get_ai_provider, generate_with_gemini_fallback
from .models import EvaluationResult, EvaluationGrade, GeneratedPrompt

logger = logging.getLogger(__name__)


class ResumeEvaluator:
    """이력서 평가 AI Agent"""

    def __init__(
        self,
        ai_provider: str = "claude",
        data_dir: str = "data/resume_evaluator"
    ):
        """
        Args:
            ai_provider: AI 제공자 (claude, gemini, ollama)
            data_dir: 데이터 디렉토리
        """
        self.ai_provider = ai_provider
        self.data_dir = Path(data_dir)
        self.system_prompt: Optional[str] = None

    def load_system_prompt(self, prompt: GeneratedPrompt) -> None:
        """시스템 프롬프트 로드

        Args:
            prompt: GeneratedPrompt 객체
        """
        self.system_prompt = prompt.prompt
        logger.info(f"✅ 시스템 프롬프트 로드 완료 ({len(self.system_prompt)}자)")

    def load_system_prompt_from_file(self, path: Optional[str] = None) -> None:
        """파일에서 시스템 프롬프트 로드

        Args:
            path: 프롬프트 파일 경로 (없으면 기본 경로 사용)
        """
        if path is None:
            path = self.data_dir / "system_prompt.json"
        else:
            path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"시스템 프롬프트 파일을 찾을 수 없습니다: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        prompt = GeneratedPrompt.from_dict(data)
        self.load_system_prompt(prompt)

    async def evaluate(
        self,
        resume_text: str,
        position: str = "Server Developer"
    ) -> EvaluationResult:
        """이력서 평가 수행

        Args:
            resume_text: 이력서 텍스트
            position: 지원 포지션

        Returns:
            EvaluationResult: 평가 결과
        """
        if not self.system_prompt:
            raise ValueError("시스템 프롬프트가 로드되지 않았습니다. load_system_prompt()를 먼저 호출하세요.")

        logger.info(f"🔍 이력서 평가 시작 (포지션: {position})")

        # 사용자 프롬프트 구성
        user_prompt = f"""다음 이력서를 토스 {position} 포지션 기준으로 평가해주세요.

## 이력서 내용

{resume_text}

---

위의 평가 기준에 따라 JSON 형식으로 평가 결과를 출력해주세요."""

        # AI 응답 생성
        try:
            response, used_provider = await generate_with_gemini_fallback(
                provider_type=self.ai_provider,
                prompt=user_prompt,
                system_prompt=self.system_prompt,
            )
            logger.info(f"✅ AI 응답 생성 완료 (provider: {used_provider})")
        except Exception as e:
            logger.error(f"❌ AI 응답 생성 실패: {e}")
            raise

        # 응답 파싱
        result = self._parse_response(response, used_provider)
        return result

    def _parse_response(self, response: str, provider: str) -> EvaluationResult:
        """AI 응답 파싱

        Args:
            response: AI 응답 텍스트
            provider: 사용된 AI 제공자

        Returns:
            EvaluationResult: 파싱된 평가 결과
        """
        logger.debug(f"📄 응답 파싱 중... ({len(response)}자)")

        # JSON 추출
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # JSON 블록이 없으면 전체 응답에서 JSON 찾기
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning("⚠️ JSON 형식 응답을 찾을 수 없습니다. 기본값으로 반환합니다.")
                return self._create_default_result(response, provider)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON 파싱 실패: {e}")
            return self._create_default_result(response, provider)

        # 점수 추출
        scores = data.get("scores", {})
        total_score = data.get("total_score", 0)

        # 세부 점수 합산
        technical_skills = (
            scores.get("system_design", 0) +
            scores.get("traffic_handling", 0) +
            scores.get("tech_stack_fit", 0)
        )
        problem_solving = (
            scores.get("incident_response", 0) +
            scores.get("problem_solving", 0)
        )
        soft_skills = (
            scores.get("ownership", 0) +
            scores.get("collaboration", 0) +
            scores.get("growth_mindset", 0)
        )
        domain_fit = (
            scores.get("domain_experience", 0) +
            scores.get("b2c_experience", 0)
        )

        # total_score가 없으면 계산
        if total_score == 0:
            total_score = technical_skills + problem_solving + soft_skills + domain_fit

        # 등급 결정
        grade_str = data.get("grade", "")
        try:
            grade = EvaluationGrade(grade_str)
        except ValueError:
            grade = EvaluationResult.grade_from_score(total_score)

        return EvaluationResult(
            total_score=total_score,
            grade=grade,
            technical_skills_score=technical_skills,
            problem_solving_score=problem_solving,
            soft_skills_score=soft_skills,
            domain_fit_score=domain_fit,
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            recommended_positions=data.get("recommended_positions", []),
            interview_questions=data.get("interview_questions", []),
            summary=data.get("summary", ""),
            evaluator_model=provider,
            raw_response=response,
        )

    def _create_default_result(self, response: str, provider: str) -> EvaluationResult:
        """기본 평가 결과 생성 (파싱 실패 시)

        Args:
            response: 원본 AI 응답
            provider: AI 제공자

        Returns:
            EvaluationResult: 기본 평가 결과
        """
        return EvaluationResult(
            total_score=0,
            grade=EvaluationGrade.D,
            technical_skills_score=0,
            problem_solving_score=0,
            soft_skills_score=0,
            domain_fit_score=0,
            strengths=[],
            weaknesses=["평가 결과 파싱 실패"],
            recommended_positions=[],
            interview_questions=[],
            summary="AI 응답 파싱에 실패했습니다. 원본 응답을 확인해주세요.",
            evaluator_model=provider,
            raw_response=response,
        )

    async def evaluate_from_file(
        self,
        file_path: str,
        position: str = "Server Developer"
    ) -> EvaluationResult:
        """파일에서 이력서를 읽어 평가

        Args:
            file_path: 이력서 파일 경로
            position: 지원 포지션

        Returns:
            EvaluationResult: 평가 결과
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"이력서 파일을 찾을 수 없습니다: {path}")

        # 파일 확장자에 따라 처리
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            resume_text = self._read_pdf(path)
        elif suffix in [".md", ".txt"]:
            with open(path, "r", encoding="utf-8") as f:
                resume_text = f.read()
        elif suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                resume_text = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"지원하지 않는 파일 형식입니다: {suffix}")

        logger.info(f"📄 이력서 파일 로드 완료: {path} ({len(resume_text)}자)")
        return await self.evaluate(resume_text, position)

    def _read_pdf(self, path: Path) -> str:
        """PDF 파일 읽기

        Args:
            path: PDF 파일 경로

        Returns:
            추출된 텍스트
        """
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except ImportError:
            raise ImportError("PDF 파일을 읽으려면 pypdf 패키지가 필요합니다: pip install pypdf")

    def format_result(self, result: EvaluationResult) -> str:
        """평가 결과를 읽기 좋은 형식으로 포맷팅

        Args:
            result: 평가 결과

        Returns:
            포맷팅된 문자열
        """
        grade_emoji = {
            EvaluationGrade.S: "🌟",
            EvaluationGrade.A: "✨",
            EvaluationGrade.B: "👍",
            EvaluationGrade.C: "📝",
            EvaluationGrade.D: "⚠️",
        }

        grade_description = {
            EvaluationGrade.S: "즉시 채용 권장",
            EvaluationGrade.A: "적극 면접 권장",
            EvaluationGrade.B: "면접 진행 권장",
            EvaluationGrade.C: "조건부 면접 고려",
            EvaluationGrade.D: "채용 보류 권장",
        }

        output = f"""
{'='*60}
📋 이력서 평가 결과
{'='*60}

{grade_emoji[result.grade]} 등급: {result.grade.value} ({grade_description[result.grade]})
📊 총점: {result.total_score}/100점

{'─'*60}
📈 세부 점수
{'─'*60}
  • 핵심 기술 역량: {result.technical_skills_score}/40점
  • 문제 해결 능력: {result.problem_solving_score}/25점
  • 소프트 스킬:    {result.soft_skills_score}/20점
  • 도메인 적합성:  {result.domain_fit_score}/15점

{'─'*60}
💪 강점
{'─'*60}
"""
        for strength in result.strengths:
            output += f"  ✅ {strength}\n"

        output += f"""
{'─'*60}
🔧 보완 필요 영역
{'─'*60}
"""
        for weakness in result.weaknesses:
            output += f"  ⚡ {weakness}\n"

        if result.recommended_positions:
            output += f"""
{'─'*60}
🎯 추천 포지션
{'─'*60}
"""
            for pos in result.recommended_positions:
                output += f"  • {pos}\n"

        if result.interview_questions:
            output += f"""
{'─'*60}
❓ 면접 시 확인 필요 사항
{'─'*60}
"""
            for q in result.interview_questions:
                output += f"  • {q}\n"

        output += f"""
{'─'*60}
📝 종합 평가
{'─'*60}
{result.summary}

{'='*60}
"""
        return output
