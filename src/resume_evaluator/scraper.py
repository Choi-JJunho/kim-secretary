"""토스 채용공고 스크래퍼 (Playwright 기반) - 동적 job_id 탐색"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser

from .models import JobRequirement, ScrapedData, PositionCategory, TossJobCategory

logger = logging.getLogger(__name__)


@dataclass
class JobListItem:
    """채용 목록에서 가져온 공고 정보"""
    job_id: str
    title: str
    tags: str  # 태그 문자열 (직군 분류용)
    companies: list[str]  # 계열사 목록


class TossJobScraper:
    """토스 채용공고 스크래퍼 - 동적 job_id 탐색"""

    BASE_URL = "https://toss.im/career/jobs"
    JOB_DETAIL_URL = "https://toss.im/career/job-detail"

    # 직군별 키워드 매핑 (제목과 태그에서 매칭)
    CATEGORY_KEYWORDS: dict[TossJobCategory, list[str]] = {
        TossJobCategory.BACKEND: [
            "server developer", "backend", "node.js developer", "python developer",
            "서버 개발", "백엔드", "server", "java developer", "go developer",
        ],
        TossJobCategory.FRONTEND: [
            "frontend developer", "frontend engineer", "frontend ux",
            "프론트엔드", "frontend ops", "frontend platform",
        ],
        TossJobCategory.APP: [
            "ios developer", "android developer", "android platform", "ios platform",
            "ios engineer", "android engineer", "앱 개발", "모바일",
        ],
        TossJobCategory.INFRA: [
            "devops", "sre", "site reliability", "system engineer", "cloud engineer",
            "infrastructure", "인프라", "시스템 엔지니어", "network engineer",
        ],
        TossJobCategory.QA: [
            "qa engineer", "qa manager", "qa specialist", "test automation",
            "quality assurance", "테스트", "품질",
        ],
        TossJobCategory.DEVICE: [
            "device software", "embedded", "임베디드", "device engineer",
        ],
        TossJobCategory.FULLSTACK: [
            "full stack", "fullstack", "풀스택",
        ],
        TossJobCategory.MILITARY: [
            "산업기능요원", "전문연구요원", "병역특례",
        ],
    }

    def __init__(self, data_dir: str = "data/resume_evaluator"):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_data_path = self.data_dir / "scraped_positions.json"
        self._job_list_cache: dict[str, list[JobListItem]] = {}

    async def discover_jobs_by_category(
        self,
        category: TossJobCategory,
        page: Page,
        max_jobs: int = 10
    ) -> list[JobListItem]:
        """채용 목록 페이지에서 특정 직군의 job_id들을 동적으로 탐색

        Args:
            category: 직군 카테고리
            page: Playwright Page 객체
            max_jobs: 최대 수집할 공고 수

        Returns:
            list[JobListItem]: 발견된 채용 공고 목록
        """
        cache_key = category.value
        if cache_key in self._job_list_cache:
            return self._job_list_cache[cache_key][:max_jobs]

        logger.info(f"🔍 토스 {category.value} 직군 채용공고 탐색 중...")

        # 채용 목록 페이지로 이동
        await page.goto(self.BASE_URL)
        await page.wait_for_timeout(3000)

        # 모든 채용공고 목록 가져오기
        all_jobs = await self._fetch_all_job_listings(page)
        logger.info(f"📋 총 {len(all_jobs)}개의 채용공고 발견")

        # 직군별로 필터링
        keywords = self.CATEGORY_KEYWORDS.get(category, [])
        matched_jobs = []

        for job in all_jobs:
            search_text = f"{job.title} {job.tags}".lower()

            # 병역특례 공고는 MILITARY 카테고리에서만 매칭
            is_military = any(kw in search_text for kw in ["산업기능요원", "전문연구요원", "병역특례"])

            if category == TossJobCategory.MILITARY:
                if is_military:
                    matched_jobs.append(job)
            else:
                # 병역특례가 아닌 공고만 일반 카테고리에서 매칭
                # (또는 해당 카테고리 키워드와 병역특례가 동시에 매칭되면 포함)
                if any(kw in search_text for kw in keywords):
                    matched_jobs.append(job)

        logger.info(f"✅ {category.value} 직군: {len(matched_jobs)}개 매칭")

        # 캐시 저장
        self._job_list_cache[cache_key] = matched_jobs

        return matched_jobs[:max_jobs]

    async def _fetch_all_job_listings(self, page: Page) -> list[JobListItem]:
        """채용 목록 페이지에서 모든 공고 정보를 가져옴"""

        # 스크롤하여 모든 공고 로드 (lazy loading 대응)
        await self._scroll_to_load_all(page)

        # JavaScript로 모든 채용공고 정보 추출
        jobs_data = await page.evaluate("""
            () => {
                // 알려진 계열사 목록
                const knownCompanies = [
                    '토스', '뱅크', '증권', '페이먼츠', '플레이스', '인슈어런스',
                    '씨엑스', '인컴', '인사이트', '모바일'
                ];

                const links = Array.from(document.querySelectorAll('a[href*="job-detail?job_id="]'));
                return links.map(link => {
                    const url = link.getAttribute('href');
                    const jobIdMatch = url.match(/job_id=(\\d+)/);
                    const jobId = jobIdMatch ? jobIdMatch[1] : '';

                    // 제목 추출
                    const titleEl = link.querySelector('p');
                    const title = titleEl ? titleEl.textContent.trim() : '';

                    // 태그 추출 (제목 아래의 텍스트)
                    const listItem = link.querySelector('li') || link;
                    const allText = listItem.textContent || '';
                    const tags = allText.replace(title, '').trim();

                    // 계열사 목록 추출 - 마지막 div들에서 알려진 계열사명만 필터링
                    const companyDivs = link.querySelectorAll('div > div:last-child > div');
                    const companies = Array.from(companyDivs)
                        .map(d => d.textContent.trim())
                        .filter(t => t && knownCompanies.some(c => t.includes(c)) && !t.includes('외'));

                    return { jobId, title, tags, companies };
                }).filter(job => job.jobId && job.title);
            }
        """)

        return [
            JobListItem(
                job_id=j["jobId"],
                title=j["title"],
                tags=j["tags"],
                companies=j["companies"]
            )
            for j in jobs_data
        ]

    async def _scroll_to_load_all(self, page: Page, max_scrolls: int = 10):
        """페이지를 스크롤하여 모든 콘텐츠 로드"""
        prev_count = 0

        for _ in range(max_scrolls):
            # 현재 공고 수 확인
            count = await page.evaluate("""
                () => document.querySelectorAll('a[href*="job-detail?job_id="]').length
            """)

            if count == prev_count:
                break  # 더 이상 새로운 콘텐츠가 없음

            prev_count = count

            # 페이지 끝까지 스크롤
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

    async def scrape_positions_by_category(
        self,
        category: TossJobCategory,
        headless: bool = True,
        max_jobs: int = 5
    ) -> ScrapedData:
        """특정 직군의 포지션 스크래핑 (동적 탐색)

        Args:
            category: 직군 카테고리
            headless: 헤드리스 모드 여부
            max_jobs: 최대 스크래핑할 공고 수

        Returns:
            ScrapedData: 스크래핑된 데이터
        """
        logger.info(f"🚀 토스 {category.value} 포지션 스크래핑 시작...")

        positions = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            # 1. 동적으로 job_id 탐색
            job_list = await self.discover_jobs_by_category(category, page, max_jobs)

            if not job_list:
                logger.warning(f"⚠️ {category.value} 직군의 채용공고를 찾을 수 없습니다.")
                await browser.close()
                return ScrapedData(positions=[], source_url=self.BASE_URL)

            logger.info(f"📋 {len(job_list)}개 공고 스크래핑 시작...")

            # 2. 각 공고 상세 페이지 스크래핑
            for job_item in job_list:
                try:
                    position = await self._scrape_position(page, job_item.job_id, category)
                    if position:
                        positions.append(position)
                        logger.info(f"✅ {position.title} ({position.company}) 스크래핑 완료")
                    await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"❌ job_id={job_item.job_id} 스크래핑 실패: {e}")

            await browser.close()

        scraped_data = ScrapedData(
            positions=positions,
            scraped_at=datetime.now(),
            source_url=f"{self.BASE_URL}?category={category.value}",
        )

        logger.info(f"✅ 총 {len(positions)}개 {category.value} 포지션 스크래핑 완료")
        return scraped_data

    async def scrape_all_server_positions(self, headless: bool = True) -> ScrapedData:
        """모든 Server 포지션 스크래핑 (레거시 호환)

        Args:
            headless: 헤드리스 모드 여부

        Returns:
            ScrapedData: 스크래핑된 데이터
        """
        return await self.scrape_positions_by_category(TossJobCategory.BACKEND, headless)

    def get_available_categories(self) -> list[TossJobCategory]:
        """스크래핑 가능한 직군 목록 반환"""
        return list(self.CATEGORY_KEYWORDS.keys())

    def get_job_url(self, job_id: str, company: Optional[str] = None) -> str:
        """job_id로 채용공고 URL 생성

        Args:
            job_id: 채용공고 ID
            company: 계열사명 (지정시 상세 페이지로 바로 이동)

        Returns:
            채용공고 URL
        """
        from urllib.parse import quote
        base_url = f"{self.JOB_DETAIL_URL}?job_id={job_id}"
        if company:
            # sub_position_id와 company 파라미터를 추가하면 상세 페이지로 바로 이동
            return f"{base_url}&sub_position_id={job_id}&company={quote(company)}"
        return base_url

    def get_first_job_url_for_category(self, category: TossJobCategory) -> Optional[str]:
        """직군의 첫 번째 채용공고 URL 반환 (캐시된 데이터에서)

        Note: 동적 스크래핑 방식으로 변경되어, 캐시된 데이터가 있어야 URL을 반환합니다.
        캐시가 없으면 None을 반환합니다.
        """
        cache_key = category.value
        if cache_key in self._job_list_cache and self._job_list_cache[cache_key]:
            job = self._job_list_cache[cache_key][0]
            # 첫 번째 계열사 정보가 있으면 상세 페이지 URL 반환
            company = job.companies[0] if job.companies else None
            return self.get_job_url(job.job_id, company)
        return None

    async def _scrape_position(
        self,
        page: Page,
        job_id: str,
        category: Optional[TossJobCategory] = None
    ) -> Optional[JobRequirement]:
        """개별 포지션 상세 페이지 스크래핑

        Args:
            page: Playwright Page 객체
            job_id: 채용공고 ID
            category: 직군 카테고리 (optional)

        Returns:
            JobRequirement 또는 None
        """
        url = f"{self.JOB_DETAIL_URL}?job_id={job_id}"
        logger.debug(f"📄 스크래핑: {url}")

        await page.goto(url)
        await page.wait_for_timeout(3000)  # 페이지 로딩 대기

        # "공고 보기" 버튼이 있으면 클릭 (여러 계열사가 묶인 경우)
        detail_url = url  # 기본값은 원래 URL
        button_clicked = False
        try:
            clicked = await page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        if (btn.textContent.includes('공고 보기')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if clicked:
                button_clicked = True
                await page.wait_for_timeout(2000)
                # 클릭 후 변경된 URL 저장 (sub_position_id, company 파라미터 포함)
                detail_url = page.url
                logger.debug(f"📌 상세 URL: {detail_url}")
        except Exception:
            pass  # 버튼이 없는 경우 무시

        # 페이지에서 데이터 추출
        data = await page.evaluate("""
            () => {
                const result = {
                    title: document.querySelector('h1')?.textContent?.trim() || '',
                    company: '',
                    requirements: [],
                    preferred: [],
                    tech_stack: [],
                    responsibilities: [],
                };

                // 회사 정보 추출 (h5 태그 또는 "소속" 텍스트 근처)
                const h5 = document.querySelector('h5');
                if (h5) {
                    const h5Text = h5.textContent?.trim() || '';
                    // "토스 소속" 형태에서 회사명 추출
                    result.company = h5Text.replace('소속', '').trim() || h5Text;
                }

                // 섹션별 데이터 추출 (p + ul 구조)
                const paragraphs = document.querySelectorAll('p');

                for (const p of paragraphs) {
                    const text = p.textContent?.trim() || '';
                    let sibling = p.nextElementSibling;

                    // 인재상 / 자격요건
                    if (text.includes('이런 분과 함께하고 싶어요') ||
                        text.includes('이런 분을 찾고 있어요') ||
                        text.includes('이런 분을 기다리고 있어요') ||
                        text.includes('자격요건')) {
                        while (sibling && sibling.tagName === 'UL') {
                            const items = sibling.querySelectorAll('li');
                            items.forEach(item => {
                                const itemText = item.textContent?.trim()?.replace(/^•\\s*/, '');
                                if (itemText) result.requirements.push(itemText);
                            });
                            sibling = sibling.nextElementSibling;
                        }
                    }

                    // 우대사항
                    if (text.includes('이런 분이면 더 좋아요') || text.includes('우대')) {
                        while (sibling && sibling.tagName === 'UL') {
                            const items = sibling.querySelectorAll('li');
                            items.forEach(item => {
                                const itemText = item.textContent?.trim()?.replace(/^•\\s*/, '');
                                if (itemText) result.preferred.push(itemText);
                            });
                            sibling = sibling.nextElementSibling;
                        }
                    }

                    // 기술 스택
                    if (text.includes('사용하는 기술') || text.includes('기술 스택') || text.includes('기술을')) {
                        while (sibling && sibling.tagName === 'UL') {
                            const items = sibling.querySelectorAll('li');
                            items.forEach(item => {
                                const itemText = item.textContent?.trim()?.replace(/^•\\s*/, '');
                                if (itemText) result.tech_stack.push(itemText);
                            });
                            sibling = sibling.nextElementSibling;
                        }
                    }

                    // 주요 업무
                    if (text.includes('합류하면 함께') || text.includes('주요 업무') || text.includes('업무예요')) {
                        while (sibling && sibling.tagName === 'UL') {
                            const items = sibling.querySelectorAll('li');
                            items.forEach(item => {
                                const itemText = item.textContent?.trim()?.replace(/^•\\s*/, '');
                                if (itemText) result.responsibilities.push(itemText);
                            });
                            sibling = sibling.nextElementSibling;
                        }
                    }
                }

                return result;
            }
        """)

        if not data.get("title") or not data.get("requirements"):
            logger.warning(f"⚠️ job_id={job_id}: 필수 데이터 누락 (이미지 전용 공고일 수 있음)")
            return None

        # TossJobCategory -> PositionCategory 매핑
        from .models import TOSS_TO_POSITION_MAPPING
        position_category = TOSS_TO_POSITION_MAPPING.get(
            category, PositionCategory.BACKEND
        ) if category else PositionCategory.BACKEND

        # 버튼 클릭 없이 단일 계열사 공고인 경우, 회사 정보로 상세 URL 구성
        company = data.get("company", "토스")
        if not button_clicked and company:
            from urllib.parse import quote
            detail_url = f"{self.JOB_DETAIL_URL}?job_id={job_id}&sub_position_id={job_id}&company={quote(company)}"

        return JobRequirement(
            title=data["title"],
            company=company,
            requirements=data.get("requirements", []),
            preferred=data.get("preferred", []),
            tech_stack=data.get("tech_stack", []),
            responsibilities=data.get("responsibilities", []),
            job_id=job_id,
            detail_url=detail_url,
            category=position_category,
            scraped_at=datetime.now(),
        )

    def save_scraped_data(self, data: ScrapedData) -> None:
        """스크래핑 데이터 저장

        Args:
            data: 저장할 ScrapedData
        """
        with open(self.scraped_data_path, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"💾 스크래핑 데이터 저장 완료: {self.scraped_data_path}")

    def load_scraped_data(self) -> Optional[ScrapedData]:
        """저장된 스크래핑 데이터 로드

        Returns:
            ScrapedData 또는 None
        """
        if not self.scraped_data_path.exists():
            return None

        try:
            with open(self.scraped_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ScrapedData.from_dict(data)
        except Exception as e:
            logger.error(f"❌ 스크래핑 데이터 로드 실패: {e}")
            return None

    def get_content_hash(self) -> Optional[str]:
        """저장된 데이터의 content_hash 반환

        Returns:
            content_hash 또는 None
        """
        data = self.load_scraped_data()
        return data.content_hash if data else None

    def has_changes(self, new_data: ScrapedData) -> bool:
        """데이터 변경 여부 확인

        Args:
            new_data: 새로 스크래핑한 데이터

        Returns:
            변경 여부
        """
        old_hash = self.get_content_hash()
        if old_hash is None:
            return True
        return old_hash != new_data.content_hash


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    scraper = TossJobScraper()

    # Frontend 직군 스크래핑 테스트
    print("\n🧪 Frontend 직군 동적 스크래핑 테스트")
    data = await scraper.scrape_positions_by_category(
        TossJobCategory.FRONTEND,
        headless=True,
        max_jobs=3
    )

    print(f"\n📊 스크래핑 결과: {len(data.positions)}개 포지션")
    for pos in data.positions:
        print(f"  - {pos.title} ({pos.company})")
        print(f"    인재상: {len(pos.requirements)}개 항목")
        print(f"    기술스택: {len(pos.tech_stack)}개 항목")

    scraper.save_scraped_data(data)


if __name__ == "__main__":
    asyncio.run(main())
