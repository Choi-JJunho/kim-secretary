"""이력서 평가 워크플로우 오케스트레이터"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ScrapedData, GeneratedPrompt, EvaluationResult
from .scraper import TossJobScraper
from .prompt_generator import PromptGenerator
from .evaluator import ResumeEvaluator

logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    """워크플로우 설정"""
    data_dir: str = "data/resume_evaluator"
    ai_provider: str = "claude"
    target_position: str = "Backend"
    headless: bool = True
    force_scrape: bool = False
    force_regenerate: bool = False


class ResumeEvaluationWorkflow:
    """이력서 평가 워크플로우 오케스트레이터

    워크플로우:
    1. 스크래핑: 토스 채용공고에서 인재상 수집
    2. 프롬프트 생성: 인재상 기반 시스템 프롬프트 생성 (변경 시에만)
    3. 평가: AI Agent가 이력서 평가
    """

    def __init__(self, config: Optional[WorkflowConfig] = None):
        """
        Args:
            config: 워크플로우 설정
        """
        self.config = config or WorkflowConfig()
        self.data_dir = Path(self.config.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 컴포넌트 초기화
        self.scraper = TossJobScraper(data_dir=self.config.data_dir)
        self.prompt_generator = PromptGenerator(data_dir=self.config.data_dir)
        self.evaluator = ResumeEvaluator(
            ai_provider=self.config.ai_provider,
            data_dir=self.config.data_dir
        )

        # 상태
        self._scraped_data: Optional[ScrapedData] = None
        self._generated_prompt: Optional[GeneratedPrompt] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """워크플로우 초기화 (스크래핑 + 프롬프트 생성)

        Returns:
            성공 여부
        """
        logger.info("🚀 워크플로우 초기화 시작...")

        try:
            # Step 1: 스크래핑
            scraped_data = await self._run_scraping()

            # Step 2: 프롬프트 생성 (필요 시)
            generated_prompt = self._run_prompt_generation(scraped_data)

            # Step 3: Evaluator에 프롬프트 로드
            self.evaluator.load_system_prompt(generated_prompt)

            self._initialized = True
            logger.info("✅ 워크플로우 초기화 완료")
            return True

        except Exception as e:
            logger.error(f"❌ 워크플로우 초기화 실패: {e}")
            return False

    async def _run_scraping(self) -> ScrapedData:
        """스크래핑 단계 실행

        Returns:
            ScrapedData: 스크래핑된 데이터
        """
        logger.info("📡 스크래핑 단계 시작...")

        # 기존 데이터 확인
        existing_data = self.scraper.load_scraped_data()

        if existing_data and not self.config.force_scrape:
            logger.info("📦 기존 스크래핑 데이터 사용")
            self._scraped_data = existing_data
            return existing_data

        # 새로 스크래핑
        logger.info("🔄 새로운 스크래핑 수행...")
        scraped_data = await self.scraper.scrape_all_server_positions(
            headless=self.config.headless
        )

        # 변경 여부 확인
        if existing_data:
            if self.scraper.has_changes(scraped_data):
                logger.info("🆕 스크래핑 데이터가 변경되었습니다.")
            else:
                logger.info("✅ 스크래핑 데이터 변경 없음")

        # 저장
        self.scraper.save_scraped_data(scraped_data)
        self._scraped_data = scraped_data

        return scraped_data

    def _run_prompt_generation(self, scraped_data: ScrapedData) -> GeneratedPrompt:
        """프롬프트 생성 단계 실행

        Args:
            scraped_data: 스크래핑된 데이터

        Returns:
            GeneratedPrompt: 생성된 프롬프트
        """
        logger.info("📝 프롬프트 생성 단계 시작...")

        # 재생성 필요 여부 확인
        needs_regen = self.prompt_generator.needs_regeneration(scraped_data.content_hash)

        if not needs_regen and not self.config.force_regenerate:
            existing_prompt = self.prompt_generator.load_prompt()
            if existing_prompt:
                logger.info("📦 기존 시스템 프롬프트 사용 (데이터 변경 없음)")
                self._generated_prompt = existing_prompt
                return existing_prompt

        # 프롬프트 생성
        logger.info("🔄 새로운 시스템 프롬프트 생성...")
        generated_prompt = self.prompt_generator.generate_system_prompt(
            scraped_data=scraped_data,
            target_position=self.config.target_position
        )

        # 저장
        self.prompt_generator.save_prompt(generated_prompt)
        self._generated_prompt = generated_prompt

        return generated_prompt

    async def evaluate_resume(
        self,
        resume_text: str,
        position: str = "Server Developer"
    ) -> EvaluationResult:
        """이력서 평가

        Args:
            resume_text: 이력서 텍스트
            position: 지원 포지션

        Returns:
            EvaluationResult: 평가 결과
        """
        if not self._initialized:
            logger.info("⚠️ 워크플로우가 초기화되지 않았습니다. 초기화를 먼저 수행합니다...")
            await self.initialize()

        return await self.evaluator.evaluate(resume_text, position)

    async def evaluate_resume_file(
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
        if not self._initialized:
            logger.info("⚠️ 워크플로우가 초기화되지 않았습니다. 초기화를 먼저 수행합니다...")
            await self.initialize()

        return await self.evaluator.evaluate_from_file(file_path, position)

    def format_result(self, result: EvaluationResult) -> str:
        """평가 결과 포맷팅

        Args:
            result: 평가 결과

        Returns:
            포맷팅된 문자열
        """
        return self.evaluator.format_result(result)

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부"""
        return self._initialized

    @property
    def scraped_data(self) -> Optional[ScrapedData]:
        """스크래핑된 데이터"""
        return self._scraped_data

    @property
    def generated_prompt(self) -> Optional[GeneratedPrompt]:
        """생성된 프롬프트"""
        return self._generated_prompt

    def get_status(self) -> dict:
        """워크플로우 상태 조회

        Returns:
            상태 정보 딕셔너리
        """
        status = {
            "initialized": self._initialized,
            "data_dir": str(self.data_dir),
            "ai_provider": self.config.ai_provider,
            "target_position": self.config.target_position,
        }

        if self._scraped_data:
            status["scraped_data"] = {
                "positions_count": len(self._scraped_data.positions),
                "scraped_at": self._scraped_data.scraped_at.isoformat(),
                "content_hash": self._scraped_data.content_hash,
            }

        if self._generated_prompt:
            status["generated_prompt"] = {
                "source_hash": self._generated_prompt.source_hash,
                "generated_at": self._generated_prompt.generated_at.isoformat(),
                "prompt_length": len(self._generated_prompt.prompt),
            }

        return status


async def run_workflow(
    resume_path: str,
    position: str = "Server Developer",
    ai_provider: str = "claude",
    force_scrape: bool = False,
    force_regenerate: bool = False,
    headless: bool = True,
) -> EvaluationResult:
    """워크플로우 실행 편의 함수

    Args:
        resume_path: 이력서 파일 경로
        position: 지원 포지션
        ai_provider: AI 제공자
        force_scrape: 강제 스크래핑 여부
        force_regenerate: 강제 프롬프트 재생성 여부
        headless: 헤드리스 모드 여부

    Returns:
        EvaluationResult: 평가 결과
    """
    config = WorkflowConfig(
        ai_provider=ai_provider,
        force_scrape=force_scrape,
        force_regenerate=force_regenerate,
        headless=headless,
    )

    workflow = ResumeEvaluationWorkflow(config)
    await workflow.initialize()

    result = await workflow.evaluate_resume_file(resume_path, position)
    print(workflow.format_result(result))

    return result


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    # 워크플로우 초기화만 테스트
    config = WorkflowConfig(
        ai_provider="claude",
        force_scrape=False,
        force_regenerate=False,
        headless=True,
    )

    workflow = ResumeEvaluationWorkflow(config)
    success = await workflow.initialize()

    if success:
        print("\n📊 워크플로우 상태:")
        status = workflow.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
