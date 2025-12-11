"""카페24 PM/기획자 이력서 평가 워크플로우"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import ScrapedData, GeneratedPrompt, EvaluationResult, Cafe24JobCategory
from .scraper_cafe24 import Cafe24JobScraper
from .prompt_generator_cafe24 import Cafe24PromptGenerator
from .evaluator import ResumeEvaluator

logger = logging.getLogger(__name__)


@dataclass
class Cafe24WorkflowConfig:
    """카페24 워크플로우 설정"""
    data_dir: str = "data/resume_evaluator/cafe24"
    ai_provider: str = "claude"
    target_position: str = "PM"
    headless: bool = True
    force_scrape: bool = False
    force_regenerate: bool = False


class Cafe24EvaluationWorkflow:
    """카페24 PM/기획자 이력서 평가 워크플로우

    워크플로우:
    1. 스크래핑: 기획/운영 직군의 카페24 채용공고에서 인재상 수집
    2. 프롬프트 생성: 인재상 기반 PM 평가용 시스템 프롬프트 생성 (변경 시에만)
    3. 평가: AI Agent가 이력서 평가
    """

    def __init__(self, config: Optional[Cafe24WorkflowConfig] = None):
        """
        Args:
            config: 워크플로우 설정
        """
        self.config = config or Cafe24WorkflowConfig()
        self.data_dir = Path(self.config.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 컴포넌트 초기화
        self.scraper = Cafe24JobScraper(data_dir=self.config.data_dir)
        self.prompt_generator = Cafe24PromptGenerator(data_dir=self.config.data_dir)
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
        logger.info("🚀 카페24 PM 평가 워크플로우 초기화 시작...")

        try:
            # Step 1: 스크래핑
            scraped_data = await self._run_scraping()

            # Step 2: 프롬프트 생성 (필요 시)
            generated_prompt = self._run_prompt_generation(scraped_data)

            # Step 3: Evaluator에 프롬프트 로드
            self.evaluator.load_system_prompt(generated_prompt)

            self._initialized = True
            logger.info("✅ 카페24 PM 평가 워크플로우 초기화 완료")
            return True

        except Exception as e:
            logger.error(f"❌ 워크플로우 초기화 실패: {e}")
            return False

    async def _run_scraping(self) -> ScrapedData:
        """스크래핑 단계 실행"""
        logger.info("📡 스크래핑 단계 시작...")

        # 기존 데이터 확인
        existing_data = self.scraper.load_scraped_data()

        if existing_data and not self.config.force_scrape:
            logger.info("📦 기존 스크래핑 데이터 사용")
            self._scraped_data = existing_data
            return existing_data

        # 새로 스크래핑 (기획/운영 직군)
        logger.info("🔄 새로운 스크래핑 수행...")
        scraped_data = await self.scraper.scrape_positions_by_category(
            Cafe24JobCategory.PLANNING,
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
        """프롬프트 생성 단계 실행"""
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
        position: str = "PM"
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
        position: str = "PM"
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
        """평가 결과 포맷팅"""
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
        """워크플로우 상태 조회"""
        status = {
            "initialized": self._initialized,
            "data_dir": str(self.data_dir),
            "ai_provider": self.config.ai_provider,
            "target_position": self.config.target_position,
            "company": "카페24",
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


async def run_cafe24_workflow(
    resume_path: str,
    position: str = "PM",
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
    config = Cafe24WorkflowConfig(
        ai_provider=ai_provider,
        target_position=position,
        force_scrape=force_scrape,
        force_regenerate=force_regenerate,
        headless=headless,
    )

    workflow = Cafe24EvaluationWorkflow(config)
    await workflow.initialize()

    result = await workflow.evaluate_resume_file(resume_path, position)
    print(workflow.format_result(result))

    return result


async def main():
    """테스트용 메인 함수"""
    import sys
    logging.basicConfig(level=logging.INFO)

    # 워크플로우 초기화만 테스트
    config = Cafe24WorkflowConfig(
        ai_provider="claude",
        force_scrape=False,
        force_regenerate=False,
        headless=True,
    )

    workflow = Cafe24EvaluationWorkflow(config)
    success = await workflow.initialize()

    if success:
        print("\n📊 워크플로우 상태:")
        status = workflow.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")

        # 이력서 파일이 주어진 경우 평가 실행
        if len(sys.argv) > 1:
            resume_path = sys.argv[1]
            print(f"\n📄 이력서 평가: {resume_path}")
            result = await workflow.evaluate_resume_file(resume_path)
            print(workflow.format_result(result))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
