"""원티드 채용공고 스크래퍼 (Playwright 기반)

원티드는 여러 기업의 채용공고를 모아놓은 플랫폼입니다.
기업별/직군별로 채용공고를 스크래핑하여 이력서 평가에 활용합니다.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from playwright.async_api import async_playwright, Page

from .models import (
    JobRequirement,
    ScrapedData,
    PositionCategory,
    WantedJobCategory,
    WANTED_DUTY_ID_MAP,
    WANTED_TO_POSITION_MAPPING,
)

logger = logging.getLogger(__name__)


@dataclass
class WantedJobListItem:
    """원티드 채용 목록에서 가져온 공고 정보"""
    job_id: str
    title: str
    company: str
    location: str
    experience: str  # 예: "신입-경력 4년", "경력 3년 이상"


@dataclass
class WantedCompanyInfo:
    """원티드에서 스크래핑한 기업 정보"""
    company_id: str
    company_name: str
    industry: str = ""
    positions_count: int = 0


class WantedJobScraper:
    """원티드 채용공고 스크래퍼

    원티드 플랫폼에서 채용공고를 스크래핑합니다.
    - 직군별 필터링 (Backend, Frontend, DevOps 등)
    - 경력 필터링 (신입~3년, 3년 이상 등)
    - 지역 필터링 (서울, 판교 등)
    - 기업별 채용공고 수집
    """

    BASE_URL = "https://www.wanted.co.kr"
    JOB_LIST_URL = "https://www.wanted.co.kr/wdlist/518"  # 개발 직군 기본
    JOB_DETAIL_URL = "https://www.wanted.co.kr/wd"

    def __init__(self, data_dir: str = "data/resume_evaluator/wanted"):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_data_path = self.data_dir / "scraped_positions.json"
        self._job_list_cache: dict[str, list[WantedJobListItem]] = {}

    def _build_list_url(
        self,
        categories: list[WantedJobCategory] | None = None,
        years_min: int = 0,
        years_max: int = 10,
        locations: list[str] | None = None,
    ) -> str:
        """채용공고 목록 URL 생성

        Args:
            categories: 직군 카테고리 목록
            years_min: 최소 경력 (0=신입)
            years_max: 최대 경력
            locations: 지역 목록 (예: ["seoul.all", "gyeonggi.bundang"])

        Returns:
            완성된 URL
        """
        url = f"{self.JOB_LIST_URL}?"

        # 기본 파라미터
        url += "country=kr&job_sort=job.latest_order"

        # 경력 필터
        url += f"&years={years_min}&years={years_max}"

        # 지역 필터
        if locations:
            for loc in locations:
                url += f"&locations={loc}"
        else:
            url += "&locations=seoul.all"

        # 직군 필터 (selected 파라미터)
        if categories:
            for cat in categories:
                duty_id = WANTED_DUTY_ID_MAP.get(cat)
                if duty_id:
                    url += f"&selected={duty_id}"

        return url

    async def scrape_job_list(
        self,
        page: Page,
        categories: list[WantedJobCategory] | None = None,
        years_min: int = 0,
        years_max: int = 3,
        locations: list[str] | None = None,
        max_jobs: int = 20,
    ) -> list[WantedJobListItem]:
        """채용공고 목록 스크래핑

        Args:
            page: Playwright Page 객체
            categories: 직군 카테고리 목록
            years_min: 최소 경력
            years_max: 최대 경력
            locations: 지역 목록
            max_jobs: 최대 수집할 공고 수

        Returns:
            채용공고 목록
        """
        url = self._build_list_url(categories, years_min, years_max, locations)
        logger.info(f"🔍 원티드 채용공고 목록 스크래핑: {url}")

        await page.goto(url)
        await page.wait_for_timeout(3000)

        # 스크롤하여 더 많은 공고 로드
        await self._scroll_to_load_jobs(page, max_jobs)

        # 공고 목록 추출
        jobs_data = await page.evaluate("""
            (maxJobs) => {
                const jobs = [];
                // 공고 카드 선택 - listitem 내부의 link
                const jobCards = document.querySelectorAll('ul > li > a[href^="/wd/"]');

                for (const card of jobCards) {
                    if (jobs.length >= maxJobs) break;

                    const href = card.getAttribute('href') || '';
                    const jobIdMatch = href.match(/\\/wd\\/(\\d+)/);
                    if (!jobIdMatch) continue;

                    const jobId = jobIdMatch[1];

                    // 텍스트 정보 추출 (구조가 다를 수 있음)
                    const textContent = card.textContent || '';
                    const divs = card.querySelectorAll('div');

                    let title = '';
                    let company = '';
                    let locationExp = '';

                    // div 구조에서 정보 추출
                    for (const div of divs) {
                        const text = div.textContent?.trim() || '';
                        // 제목은 보통 가장 긴 텍스트
                        if (text.length > title.length && !text.includes('합격보상금') && !text.includes('·')) {
                            // 이미 회사명이 설정된 경우, 새 텍스트가 제목일 가능성
                            if (company && text !== company) {
                                title = text;
                            } else if (!company) {
                                title = text;
                            }
                        }
                        // 회사명 (제목 다음에 오는 짧은 텍스트)
                        if (text.length > 0 && text.length < 50 && !text.includes('합격보상금') &&
                            !text.includes('·') && text !== title) {
                            company = text;
                        }
                        // 위치·경력 정보
                        if (text.includes('·') && (text.includes('서울') || text.includes('경력') || text.includes('신입'))) {
                            locationExp = text;
                        }
                    }

                    // 위치와 경력 분리
                    const parts = locationExp.split('·').map(s => s.trim());
                    const location = parts[0] || '';
                    const experience = parts[1] || '';

                    if (jobId && title) {
                        jobs.push({
                            jobId,
                            title,
                            company,
                            location,
                            experience
                        });
                    }
                }

                return jobs;
            }
        """, max_jobs)

        result = [
            WantedJobListItem(
                job_id=j["jobId"],
                title=j["title"],
                company=j["company"],
                location=j["location"],
                experience=j["experience"]
            )
            for j in jobs_data
        ]

        logger.info(f"📋 {len(result)}개 채용공고 발견")
        return result

    async def _scroll_to_load_jobs(self, page: Page, target_count: int, max_scrolls: int = 10):
        """페이지 스크롤하여 더 많은 공고 로드"""
        prev_count = 0

        for _ in range(max_scrolls):
            count = await page.evaluate("""
                () => document.querySelectorAll('ul > li > a[href^="/wd/"]').length
            """)

            if count >= target_count or count == prev_count:
                break

            prev_count = count
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

    async def scrape_job_detail(
        self,
        page: Page,
        job_id: str,
        category: WantedJobCategory | None = None,
    ) -> Optional[JobRequirement]:
        """개별 채용공고 상세 페이지 스크래핑

        Args:
            page: Playwright Page 객체
            job_id: 채용공고 ID
            category: 직군 카테고리 (optional)

        Returns:
            JobRequirement 또는 None
        """
        url = f"{self.JOB_DETAIL_URL}/{job_id}"
        logger.debug(f"📄 스크래핑: {url}")

        await page.goto(url)
        await page.wait_for_timeout(2000)

        # "상세 정보 더 보기" 버튼 클릭 (있으면)
        try:
            clicked = await page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        if (btn.textContent.includes('상세 정보 더 보기')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if clicked:
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        # 상세 정보 추출
        data = await page.evaluate("""
            () => {
                const result = {
                    title: '',
                    company: '',
                    requirements: [],
                    preferred: [],
                    tech_stack: [],
                    responsibilities: [],
                    location: '',
                    deadline: '',
                };

                // 제목 (h1 태그)
                const h1 = document.querySelector('h1');
                if (h1) {
                    result.title = h1.textContent?.trim() || '';
                }

                // 회사명 (링크에서 추출)
                const companyLink = document.querySelector('a[href^="/company/"]');
                if (companyLink) {
                    result.company = companyLink.textContent?.trim() || '';
                }

                // 섹션별 정보 추출 (heading + 다음 요소)
                const headings = document.querySelectorAll('h2, h3');

                for (const heading of headings) {
                    const headingText = heading.textContent?.trim().toLowerCase() || '';
                    let nextEl = heading.nextElementSibling;

                    // 주요업무
                    if (headingText.includes('주요업무') || headingText.includes('포지션 상세')) {
                        while (nextEl && !['H2', 'H3'].includes(nextEl.tagName)) {
                            const text = nextEl.textContent?.trim() || '';
                            if (text && !text.includes('주요업무') && !text.includes('합류하면')) {
                                // 줄바꿈으로 분리된 항목들 처리
                                const lines = text.split(/[•\\n]/).filter(l => l.trim());
                                for (const line of lines) {
                                    const cleaned = line.trim();
                                    if (cleaned && cleaned.length > 5 && !result.responsibilities.includes(cleaned)) {
                                        result.responsibilities.push(cleaned);
                                    }
                                }
                            }
                            nextEl = nextEl.nextElementSibling;
                        }
                    }

                    // 자격요건
                    if (headingText.includes('자격요건') || headingText.includes('이런 분')) {
                        while (nextEl && !['H2', 'H3'].includes(nextEl.tagName)) {
                            const text = nextEl.textContent?.trim() || '';
                            if (text && !text.includes('자격요건') && !text.includes('이런 분')) {
                                const lines = text.split(/[•\\n]/).filter(l => l.trim());
                                for (const line of lines) {
                                    const cleaned = line.trim();
                                    if (cleaned && cleaned.length > 5 && !result.requirements.includes(cleaned)) {
                                        result.requirements.push(cleaned);
                                    }
                                }
                            }
                            nextEl = nextEl.nextElementSibling;
                        }
                    }

                    // 우대사항
                    if (headingText.includes('우대사항') || headingText.includes('우대')) {
                        while (nextEl && !['H2', 'H3'].includes(nextEl.tagName)) {
                            const text = nextEl.textContent?.trim() || '';
                            if (text && !text.includes('우대사항')) {
                                const lines = text.split(/[•\\n]/).filter(l => l.trim());
                                for (const line of lines) {
                                    const cleaned = line.trim();
                                    if (cleaned && cleaned.length > 5 && !result.preferred.includes(cleaned)) {
                                        result.preferred.push(cleaned);
                                    }
                                }
                            }
                            nextEl = nextEl.nextElementSibling;
                        }
                    }

                    // 기술스택 (텍스트에서 추출)
                    if (headingText.includes('기술') || headingText.includes('stack')) {
                        while (nextEl && !['H2', 'H3'].includes(nextEl.tagName)) {
                            const text = nextEl.textContent?.trim() || '';
                            if (text) {
                                const lines = text.split(/[•\\n,]/).filter(l => l.trim());
                                for (const line of lines) {
                                    const cleaned = line.trim();
                                    if (cleaned && cleaned.length > 1 && !result.tech_stack.includes(cleaned)) {
                                        result.tech_stack.push(cleaned);
                                    }
                                }
                            }
                            nextEl = nextEl.nextElementSibling;
                        }
                    }

                    // 마감일
                    if (headingText.includes('마감')) {
                        if (nextEl) {
                            result.deadline = nextEl.textContent?.trim() || '';
                        }
                    }

                    // 근무지역
                    if (headingText.includes('근무지역') || headingText.includes('위치')) {
                        if (nextEl) {
                            result.location = nextEl.textContent?.trim() || '';
                        }
                    }
                }

                // 기술스택이 비어있으면 본문에서 추출 시도
                if (result.tech_stack.length === 0) {
                    const bodyText = document.body.textContent || '';
                    const techPatterns = [
                        /Core:\\s*([^\\n]+)/i,
                        /Data.*?Messaging:\\s*([^\\n]+)/i,
                        /DevOps.*?Infra:\\s*([^\\n]+)/i,
                        /사용하는 기술[:\\s]*([^\\n]+)/i,
                    ];

                    for (const pattern of techPatterns) {
                        const match = bodyText.match(pattern);
                        if (match && match[1]) {
                            const techs = match[1].split(/[,、]/).map(t => t.trim()).filter(t => t);
                            result.tech_stack.push(...techs);
                        }
                    }
                }

                return result;
            }
        """)

        if not data.get("title"):
            logger.warning(f"⚠️ job_id={job_id}: 제목을 찾을 수 없음")
            return None

        # 카테고리 매핑
        position_category = WANTED_TO_POSITION_MAPPING.get(
            category, PositionCategory.OTHER
        ) if category else PositionCategory.OTHER

        return JobRequirement(
            title=data["title"],
            company=data.get("company", ""),
            requirements=data.get("requirements", []),
            preferred=data.get("preferred", []),
            tech_stack=data.get("tech_stack", []),
            responsibilities=data.get("responsibilities", []),
            job_id=job_id,
            detail_url=f"{self.JOB_DETAIL_URL}/{job_id}",
            category=position_category,
            scraped_at=datetime.now(),
        )

    async def scrape_positions_by_category(
        self,
        categories: list[WantedJobCategory],
        headless: bool = True,
        max_jobs: int = 10,
        years_min: int = 0,
        years_max: int = 3,
    ) -> ScrapedData:
        """특정 직군들의 포지션 스크래핑

        Args:
            categories: 직군 카테고리 목록
            headless: 헤드리스 모드 여부
            max_jobs: 최대 스크래핑할 공고 수
            years_min: 최소 경력
            years_max: 최대 경력

        Returns:
            ScrapedData
        """
        category_names = ", ".join(c.value for c in categories)
        logger.info(f"🚀 원티드 {category_names} 포지션 스크래핑 시작...")

        positions = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            # 1. 공고 목록 스크래핑
            job_list = await self.scrape_job_list(
                page,
                categories=categories,
                years_min=years_min,
                years_max=years_max,
                max_jobs=max_jobs,
            )

            if not job_list:
                logger.warning(f"⚠️ {category_names} 직군의 채용공고를 찾을 수 없습니다.")
                await browser.close()
                return ScrapedData(positions=[], source_url=self.JOB_LIST_URL)

            logger.info(f"📋 {len(job_list)}개 공고 상세 스크래핑 시작...")

            # 2. 각 공고 상세 페이지 스크래핑
            for job_item in job_list:
                try:
                    # 첫 번째 카테고리를 기본으로 사용
                    position = await self.scrape_job_detail(
                        page,
                        job_item.job_id,
                        categories[0] if categories else None
                    )
                    if position:
                        # 목록에서 가져온 회사명 보완
                        if not position.company and job_item.company:
                            position.company = job_item.company
                        positions.append(position)
                        logger.info(f"✅ {position.title} ({position.company}) 스크래핑 완료")
                    await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"❌ job_id={job_item.job_id} 스크래핑 실패: {e}")

            await browser.close()

        url = self._build_list_url(categories, years_min, years_max)
        scraped_data = ScrapedData(
            positions=positions,
            scraped_at=datetime.now(),
            source_url=url,
        )

        logger.info(f"✅ 총 {len(positions)}개 포지션 스크래핑 완료")
        return scraped_data

    async def scrape_all_dev_positions(
        self,
        headless: bool = True,
        max_jobs: int = 20,
    ) -> ScrapedData:
        """모든 개발 직군 포지션 스크래핑 (신입~3년)

        Args:
            headless: 헤드리스 모드 여부
            max_jobs: 최대 스크래핑할 공고 수

        Returns:
            ScrapedData
        """
        categories = [
            WantedJobCategory.BACKEND,
            WantedJobCategory.FRONTEND,
            WantedJobCategory.FULLSTACK,
            WantedJobCategory.DEVOPS,
        ]
        return await self.scrape_positions_by_category(
            categories,
            headless=headless,
            max_jobs=max_jobs
        )

    async def scrape_company_positions(
        self,
        company_name: str,
        headless: bool = True,
        max_jobs: int = 10,
    ) -> ScrapedData:
        """특정 기업의 채용공고 스크래핑

        Args:
            company_name: 기업명
            headless: 헤드리스 모드 여부
            max_jobs: 최대 스크래핑할 공고 수

        Returns:
            ScrapedData
        """
        logger.info(f"🏢 {company_name} 채용공고 스크래핑 시작...")

        # 먼저 전체 공고를 가져온 후 기업명으로 필터링
        all_data = await self.scrape_all_dev_positions(headless=headless, max_jobs=50)

        # 기업명으로 필터링
        company_positions = [
            p for p in all_data.positions
            if company_name.lower() in p.company.lower()
        ]

        logger.info(f"✅ {company_name}: {len(company_positions)}개 포지션 발견")

        return ScrapedData(
            positions=company_positions[:max_jobs],
            scraped_at=datetime.now(),
            source_url=f"{self.BASE_URL}/search?query={quote(company_name)}",
        )

    def save_scraped_data(self, data: ScrapedData, filename: str | None = None) -> Path:
        """스크래핑 데이터 저장

        Args:
            data: 저장할 ScrapedData
            filename: 파일명 (없으면 기본값 사용)

        Returns:
            저장된 파일 경로
        """
        filepath = self.data_dir / (filename or "scraped_positions.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"💾 스크래핑 데이터 저장 완료: {filepath}")
        return filepath

    def load_scraped_data(self, filename: str | None = None) -> Optional[ScrapedData]:
        """저장된 스크래핑 데이터 로드

        Args:
            filename: 파일명 (없으면 기본값 사용)

        Returns:
            ScrapedData 또는 None
        """
        filepath = self.data_dir / (filename or "scraped_positions.json")
        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ScrapedData.from_dict(data)
        except Exception as e:
            logger.error(f"❌ 스크래핑 데이터 로드 실패: {e}")
            return None

    def get_available_categories(self) -> list[WantedJobCategory]:
        """스크래핑 가능한 직군 목록 반환"""
        return list(WANTED_DUTY_ID_MAP.keys())


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    scraper = WantedJobScraper()

    # Backend 직군 스크래핑 테스트
    print("\n🧪 원티드 Backend 직군 스크래핑 테스트")
    data = await scraper.scrape_positions_by_category(
        [WantedJobCategory.BACKEND, WantedJobCategory.JAVA],
        headless=True,
        max_jobs=5
    )

    print(f"\n📊 스크래핑 결과: {len(data.positions)}개 포지션")
    for pos in data.positions:
        print(f"  - {pos.title} ({pos.company})")
        print(f"    자격요건: {len(pos.requirements)}개 항목")
        print(f"    기술스택: {pos.tech_stack[:5] if pos.tech_stack else '없음'}")

    scraper.save_scraped_data(data)


if __name__ == "__main__":
    asyncio.run(main())
