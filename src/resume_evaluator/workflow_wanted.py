"""원티드 이력서 평가 워크플로우

플로우:
1. 원티드 채용공고 스크래핑 (직군별/기업별)
2. 스크래핑 데이터 기반 평가 프롬프트 생성
3. AI Agent가 이력서 평가
4. 매칭되는 채용공고 URL 제공
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .models import (
    ScrapedData,
    GeneratedPrompt,
    EvaluationResult,
    WantedJobCategory,
    WANTED_TO_POSITION_MAPPING,
)
from .scraper_wanted import WantedJobScraper
from .prompt_generator_wanted import WantedPromptGenerator
from .evaluator import ResumeEvaluator

logger = logging.getLogger(__name__)


@dataclass
class WantedWorkflowConfig:
    """원티드 워크플로우 설정"""
    data_dir: str = "data/resume_evaluator/wanted"
    ai_provider: str = "claude"
    headless: bool = True
    force_scrape: bool = False
    force_regenerate: bool = False
    max_jobs: int = 15  # 최대 스크래핑할 공고 수
    years_min: int = 0  # 최소 경력 (0=신입)
    years_max: int = 3  # 최대 경력


@dataclass
class WantedEvaluationResult:
    """원티드 평가 결과"""
    evaluation: EvaluationResult
    matched_jobs: list[dict] = field(default_factory=list)  # 매칭된 채용공고 정보
    target_company: Optional[str] = None
    target_categories: list[WantedJobCategory] = field(default_factory=list)


class WantedEvaluationWorkflow:
    """원티드 이력서 평가 워크플로우

    원티드 플랫폼의 채용공고를 활용한 이력서 평가 워크플로우입니다.
    다양한 기업의 채용공고를 기반으로 범용적인 평가를 수행합니다.
    """

    def __init__(self, config: Optional[WantedWorkflowConfig] = None):
        """
        Args:
            config: 워크플로우 설정
        """
        self.config = config or WantedWorkflowConfig()
        self.data_dir = Path(self.config.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 컴포넌트 초기화
        self.scraper = WantedJobScraper(data_dir=self.config.data_dir)
        self.prompt_generator = WantedPromptGenerator(data_dir=self.config.data_dir)
        self.evaluator = ResumeEvaluator(
            ai_provider=self.config.ai_provider,
            data_dir=self.config.data_dir
        )

        # 상태
        self._scraped_data: Optional[ScrapedData] = None
        self._generated_prompt: Optional[GeneratedPrompt] = None
        self._initialized = False

    async def initialize(
        self,
        categories: list[WantedJobCategory] | None = None,
        target_company: Optional[str] = None,
    ) -> bool:
        """워크플로우 초기화 (스크래핑 + 프롬프트 생성)

        Args:
            categories: 스크래핑할 직군 카테고리 목록
            target_company: 특정 기업명 (프롬프트 생성 시 필터링)

        Returns:
            성공 여부
        """
        logger.info("🚀 원티드 워크플로우 초기화 시작...")

        if categories is None:
            categories = [WantedJobCategory.BACKEND, WantedJobCategory.JAVA]

        try:
            # Step 1: 스크래핑
            scraped_data = await self._run_scraping(categories)

            # Step 2: 프롬프트 생성 (필요 시)
            target_position = self._get_position_name(categories[0]) if categories else "개발자"
            generated_prompt = self._run_prompt_generation(
                scraped_data,
                target_position=target_position,
                target_company=target_company
            )

            # Step 3: Evaluator에 프롬프트 로드
            self.evaluator.load_system_prompt(generated_prompt)

            self._initialized = True
            logger.info("✅ 원티드 워크플로우 초기화 완료")
            return True

        except Exception as e:
            logger.error(f"❌ 워크플로우 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _run_scraping(
        self,
        categories: list[WantedJobCategory]
    ) -> ScrapedData:
        """스크래핑 단계 실행"""
        logger.info("📡 원티드 스크래핑 단계 시작...")

        # 캐시 파일명 생성
        category_key = "_".join(c.name.lower() for c in categories[:3])
        cache_filename = f"scraped_{category_key}.json"

        # 기존 데이터 확인
        existing_data = self.scraper.load_scraped_data(cache_filename)

        if existing_data and not self.config.force_scrape:
            logger.info(f"📦 기존 스크래핑 데이터 사용 ({len(existing_data.positions)}개 포지션)")
            self._scraped_data = existing_data
            return existing_data

        # 새로 스크래핑
        logger.info("🔄 새로운 스크래핑 수행...")
        scraped_data = await self.scraper.scrape_positions_by_category(
            categories=categories,
            headless=self.config.headless,
            max_jobs=self.config.max_jobs,
            years_min=self.config.years_min,
            years_max=self.config.years_max,
        )

        # 저장
        if scraped_data.positions:
            self.scraper.save_scraped_data(scraped_data, cache_filename)

        self._scraped_data = scraped_data
        return scraped_data

    def _run_prompt_generation(
        self,
        scraped_data: ScrapedData,
        target_position: str = "개발자",
        target_company: Optional[str] = None,
    ) -> GeneratedPrompt:
        """프롬프트 생성 단계 실행"""
        logger.info("📝 프롬프트 생성 단계 시작...")

        # 재생성 필요 여부 확인
        needs_regen = self.prompt_generator.needs_regeneration(scraped_data.content_hash)

        if not needs_regen and not self.config.force_regenerate:
            existing_prompt = self.prompt_generator.load_prompt()
            if existing_prompt:
                logger.info("📦 기존 시스템 프롬프트 사용")
                self._generated_prompt = existing_prompt
                return existing_prompt

        # 프롬프트 생성
        logger.info("🔄 새로운 시스템 프롬프트 생성...")
        generated_prompt = self.prompt_generator.generate_system_prompt(
            scraped_data=scraped_data,
            target_position=target_position,
            target_company=target_company,
        )

        # 저장
        self.prompt_generator.save_prompt(generated_prompt)
        self._generated_prompt = generated_prompt

        return generated_prompt

    async def evaluate_resume(
        self,
        resume_text: str,
        position: str = "개발자"
    ) -> EvaluationResult:
        """이력서 평가

        Args:
            resume_text: 이력서 텍스트
            position: 지원 포지션

        Returns:
            EvaluationResult
        """
        if not self._initialized:
            logger.info("⚠️ 워크플로우가 초기화되지 않았습니다. 초기화 먼저 수행...")
            await self.initialize()

        return await self.evaluator.evaluate(resume_text, position)

    async def evaluate_resume_file(
        self,
        file_path: str,
        position: str = "개발자"
    ) -> EvaluationResult:
        """파일에서 이력서를 읽어 평가

        Args:
            file_path: 이력서 파일 경로
            position: 지원 포지션

        Returns:
            EvaluationResult
        """
        if not self._initialized:
            logger.info("⚠️ 워크플로우가 초기화되지 않았습니다. 초기화 먼저 수행...")
            await self.initialize()

        return await self.evaluator.evaluate_from_file(file_path, position)

    async def evaluate_for_company(
        self,
        file_path: str,
        company_name: str,
        categories: list[WantedJobCategory] | None = None,
    ) -> WantedEvaluationResult:
        """특정 기업 기준으로 이력서 평가

        해당 기업의 채용공고를 기반으로 맞춤형 평가를 수행합니다.

        Args:
            file_path: 이력서 파일 경로
            company_name: 기업명
            categories: 직군 카테고리 (없으면 Backend/Java)

        Returns:
            WantedEvaluationResult
        """
        if categories is None:
            categories = [WantedJobCategory.BACKEND, WantedJobCategory.JAVA]

        logger.info(f"🏢 {company_name} 기준 이력서 평가 시작...")

        # 워크플로우 초기화 (해당 기업 프롬프트 생성)
        await self.initialize(categories=categories, target_company=company_name)

        # 평가 수행
        position = self._get_position_name(categories[0])
        evaluation = await self.evaluator.evaluate_from_file(file_path, position)

        # 매칭된 채용공고 정보 추출
        matched_jobs = self._get_matched_jobs(company_name)

        return WantedEvaluationResult(
            evaluation=evaluation,
            matched_jobs=matched_jobs,
            target_company=company_name,
            target_categories=categories,
        )

    async def evaluate_for_categories(
        self,
        file_path: str,
        categories: list[WantedJobCategory],
    ) -> WantedEvaluationResult:
        """특정 직군들 기준으로 이력서 평가

        Args:
            file_path: 이력서 파일 경로
            categories: 직군 카테고리 목록

        Returns:
            WantedEvaluationResult
        """
        logger.info(f"📋 {', '.join(c.value for c in categories)} 기준 이력서 평가 시작...")

        # 워크플로우 초기화
        await self.initialize(categories=categories)

        # 평가 수행
        position = self._get_position_name(categories[0])
        evaluation = await self.evaluator.evaluate_from_file(file_path, position)

        # 매칭된 채용공고 정보 추출
        matched_jobs = self._get_matched_jobs_for_score(evaluation.total_score)

        return WantedEvaluationResult(
            evaluation=evaluation,
            matched_jobs=matched_jobs,
            target_categories=categories,
        )

    def _get_position_name(self, category: WantedJobCategory) -> str:
        """직군 카테고리에서 포지션명 생성"""
        mapping = {
            WantedJobCategory.BACKEND: "Backend Developer",
            WantedJobCategory.FRONTEND: "Frontend Developer",
            WantedJobCategory.FULLSTACK: "Full Stack Developer",
            WantedJobCategory.APP_IOS: "iOS Developer",
            WantedJobCategory.APP_ANDROID: "Android Developer",
            WantedJobCategory.DEVOPS: "DevOps Engineer",
            WantedJobCategory.DATA_ENGINEER: "Data Engineer",
            WantedJobCategory.ML_ENGINEER: "ML Engineer",
            WantedJobCategory.JAVA: "Java Developer",
            WantedJobCategory.PYTHON: "Python Developer",
            WantedJobCategory.DBA: "Database Administrator",
            WantedJobCategory.SECURITY: "Security Engineer",
            WantedJobCategory.QA: "QA Engineer",
            WantedJobCategory.PM: "Product Manager",
        }
        return mapping.get(category, "Developer")

    def _get_matched_jobs(self, company_name: str) -> list[dict]:
        """특정 기업의 매칭된 채용공고 목록"""
        if not self._scraped_data:
            return []

        matched = []
        for pos in self._scraped_data.positions:
            if company_name.lower() in pos.company.lower():
                matched.append({
                    "title": pos.title,
                    "company": pos.company,
                    "url": pos.detail_url,
                    "requirements_count": len(pos.requirements),
                })

        return matched[:5]  # 최대 5개

    def _get_matched_jobs_for_score(self, score: int) -> list[dict]:
        """점수에 맞는 채용공고 추천"""
        if not self._scraped_data:
            return []

        # 점수에 따라 공고 추천 (예: 높은 점수면 요구사항 많은 공고 추천)
        sorted_positions = sorted(
            self._scraped_data.positions,
            key=lambda p: len(p.requirements),
            reverse=(score >= 70)  # 높은 점수면 요구사항 많은 것부터
        )

        matched = []
        for pos in sorted_positions[:5]:
            matched.append({
                "title": pos.title,
                "company": pos.company,
                "url": pos.detail_url,
                "requirements_count": len(pos.requirements),
            })

        return matched

    def format_result(self, result: EvaluationResult) -> str:
        """평가 결과 포맷팅"""
        return self.evaluator.format_result(result)

    def format_wanted_result(self, result: WantedEvaluationResult) -> str:
        """원티드 평가 결과 포맷팅"""
        output = self.format_result(result.evaluation)

        if result.target_company:
            output += f"\n\n🏢 평가 대상 기업: {result.target_company}"

        if result.matched_jobs:
            output += "\n\n📋 추천 채용공고:"
            for job in result.matched_jobs:
                output += f"\n  - {job['title']} ({job['company']})"
                output += f"\n    URL: {job['url']}"

        return output

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부"""
        return self._initialized

    @property
    def scraped_data(self) -> Optional[ScrapedData]:
        """스크래핑된 데이터"""
        return self._scraped_data

    def get_status(self) -> dict:
        """워크플로우 상태 조회"""
        status = {
            "initialized": self._initialized,
            "data_dir": str(self.data_dir),
            "ai_provider": self.config.ai_provider,
            "max_jobs": self.config.max_jobs,
        }

        if self._scraped_data:
            companies = set(p.company for p in self._scraped_data.positions if p.company)
            status["scraped_data"] = {
                "positions_count": len(self._scraped_data.positions),
                "companies_count": len(companies),
                "scraped_at": self._scraped_data.scraped_at.isoformat(),
            }

        if self._generated_prompt:
            status["generated_prompt"] = {
                "source_hash": self._generated_prompt.source_hash,
                "generated_at": self._generated_prompt.generated_at.isoformat(),
            }

        return status


async def evaluate_resume_from_wanted(
    resume_path: str,
    categories: list[WantedJobCategory] | None = None,
    company_name: Optional[str] = None,
    ai_provider: str = "claude",
    headless: bool = True,
    force_scrape: bool = False,
) -> WantedEvaluationResult:
    """원티드 기반 이력서 평가 편의 함수

    Args:
        resume_path: 이력서 파일 경로
        categories: 직군 카테고리 목록
        company_name: 특정 기업명 (선택)
        ai_provider: AI 제공자
        headless: 헤드리스 모드
        force_scrape: 강제 재스크래핑

    Returns:
        WantedEvaluationResult
    """
    config = WantedWorkflowConfig(
        ai_provider=ai_provider,
        headless=headless,
        force_scrape=force_scrape,
    )

    workflow = WantedEvaluationWorkflow(config)

    if company_name:
        return await workflow.evaluate_for_company(
            resume_path,
            company_name,
            categories
        )
    else:
        if categories is None:
            categories = [WantedJobCategory.BACKEND, WantedJobCategory.JAVA]
        return await workflow.evaluate_for_categories(resume_path, categories)


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    config = WantedWorkflowConfig(
        ai_provider="claude",
        force_scrape=False,
        headless=True,
        max_jobs=5,
    )

    workflow = WantedEvaluationWorkflow(config)

    # 초기화 테스트
    success = await workflow.initialize(
        categories=[WantedJobCategory.BACKEND, WantedJobCategory.JAVA]
    )

    if success:
        print("\n📊 워크플로우 상태:")
        status = workflow.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
