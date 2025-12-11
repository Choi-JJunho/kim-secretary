# 이력서 평가 시스템 개발 가이드

새로운 회사/직군의 이력서 평가 플로우를 개발할 때 참고하는 가이드입니다.

## 개요

이 시스템은 특정 회사의 채용공고를 스크래핑하여 인재상/요구사항을 추출하고, 이를 기반으로 AI가 이력서를 평가하는 워크플로우입니다.

### 플로우
1. **직군 분류**: 이력서를 분석하여 적합한 직군 추천
2. **스크래핑**: 해당 직군의 채용공고에서 인재상/요구사항 수집
3. **프롬프트 생성**: 인재상 기반 시스템 프롬프트 생성
4. **평가**: AI Agent가 이력서 평가

---

## 새 회사 추가 시 필요한 정보

사용자가 다음 정보를 제공해야 합니다:

1. **회사 정보**
   - 회사명 (영문, 한글)
   - 채용 사이트 URL
   - 채용공고 상세 페이지 URL 패턴

2. **직군 정보**
   - 직군 목록 (예: Backend, Frontend, App, DevOps 등)
   - 각 직군별 채용공고 ID 또는 URL

3. **Slack 채널 정보**
   - 이력서 피드백 채널 ID

4. **HTML 구조** (스크래핑용)
   - 채용공고 페이지의 HTML 샘플
   - 인재상/요구사항/기술스택 섹션의 선택자(selector)

---

## 개발 절차

### Step 1: 직군 Enum 정의 (`models.py`)

```python
# src/resume_evaluator/models.py에 추가

class {Company}JobCategory(str, Enum):
    """회사명 채용 직군 카테고리"""
    BACKEND = "Backend"
    FRONTEND = "Frontend"
    APP = "App"
    # ... 채용 사이트의 직군 필터 기준으로 추가

# 직군 매핑 (필요 시)
{COMPANY}_TO_POSITION_MAPPING = {
    {Company}JobCategory.BACKEND: PositionCategory.BACKEND,
    {Company}JobCategory.FRONTEND: PositionCategory.FRONTEND,
    # ...
}
```

### Step 2: 스크래퍼 구현 (`scraper_{company}.py`)

새 파일 `src/resume_evaluator/scraper_{company}.py` 생성:

> **권장**: 정적 job_id 대신 **동적 탐색 방식**을 사용하세요. 채용 사이트는 자주 변경되므로, 키워드 기반 동적 탐색이 유지보수에 유리합니다.

```python
"""회사명 채용공고 스크래퍼 (Playwright 기반) - 동적 탐색"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page
from .models import JobRequirement, ScrapedData, {Company}JobCategory

logger = logging.getLogger(__name__)


class {Company}JobScraper:
    """회사명 채용공고 스크래퍼 - 동적 탐색"""

    BASE_URL = "https://careers.{company}.com"

    # 직군별 키워드 매핑 (제목/태그에서 매칭)
    # 정적 job_id 대신 키워드로 동적 분류
    CATEGORY_KEYWORDS: dict[{Company}JobCategory, list[str]] = {
        {Company}JobCategory.BACKEND: [
            "server", "backend", "백엔드", "서버 개발",
        ],
        {Company}JobCategory.FRONTEND: [
            "frontend", "프론트엔드", "web developer",
        ],
        # ... 직군별 키워드 추가
    }

    def __init__(self, data_dir: str = "data/resume_evaluator/{company}"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_data_path = self.data_dir / "scraped_positions.json"

    async def scrape_positions_by_category(
        self,
        category: {Company}JobCategory,
        headless: bool = True,
        max_jobs: int = 10
    ) -> ScrapedData:
        """특정 직군의 포지션 스크래핑 (동적 탐색)"""
        positions = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            try:
                # 채용 목록 페이지로 이동
                await page.goto(self.BASE_URL)
                await page.wait_for_timeout(2000)

                # 페이지를 순회하며 스크래핑
                page_num = 1
                scraped_count = 0

                while scraped_count < max_jobs:
                    logger.info(f"📄 페이지 {page_num} 스크래핑 중...")

                    # 현재 페이지에서 해당 카테고리 공고 스크래핑
                    page_positions = await self._scrape_page_positions(
                        page, category, max_jobs - scraped_count
                    )
                    positions.extend(page_positions)
                    scraped_count += len(page_positions)

                    if scraped_count >= max_jobs:
                        break

                    # 다음 페이지로 이동 (사이트 구조에 맞게 구현)
                    if not await self._goto_next_page(page, page_num + 1):
                        break
                    page_num += 1
                    await page.wait_for_timeout(1000)

            except Exception as e:
                logger.error(f"❌ 스크래핑 실패: {e}")
            finally:
                await browser.close()

        return ScrapedData(
            positions=positions,
            scraped_at=datetime.now(),
            source_url=f"{self.BASE_URL}?category={category.value}",
        )

    async def _scrape_page_positions(
        self,
        page: Page,
        category: {Company}JobCategory,
        max_count: int
    ) -> list[JobRequirement]:
        """현재 페이지에서 공고 스크래핑 - 회사별 HTML 구조에 맞게 구현"""

        # JavaScript로 데이터 추출 (회사 페이지 구조에 맞게 수정)
        data = await page.evaluate("""
            (categoryKeywords) => {
                const jobs = [];

                // TODO: 회사 페이지의 HTML 구조에 맞게 선택자 수정
                const jobCards = document.querySelectorAll('.job-card');

                for (const card of jobCards) {
                    const title = card.querySelector('.job-title')?.textContent?.trim() || '';
                    const tags = card.querySelector('.job-tags')?.textContent?.toLowerCase() || '';

                    // 키워드 매칭으로 카테고리 필터링
                    const searchText = `${title} ${tags}`.toLowerCase();
                    const matches = categoryKeywords.some(kw => searchText.includes(kw));
                    if (!matches) continue;

                    // 상세 정보 추출 (사이트 구조에 따라 다름)
                    jobs.push({
                        title: title,
                        requirements: [],  // 상세 페이지에서 추출하거나 목록에서 추출
                        preferred: [],
                        tech_stack: [],
                        responsibilities: [],
                    });
                }

                return jobs;
            }
        """, self.CATEGORY_KEYWORDS.get(category, []))

        positions = []
        for item in data[:max_count]:
            if not item.get("title"):
                continue

            position = JobRequirement(
                title=item["title"],
                company="{Company}",
                requirements=item.get("requirements", []),
                preferred=item.get("preferred", []),
                tech_stack=item.get("tech_stack", []),
                responsibilities=item.get("responsibilities", []),
                job_id=f"{company}_{hash(item['title']) % 100000:05d}",
                category=category,
                scraped_at=datetime.now(),
            )
            positions.append(position)
            logger.info(f"✅ {position.title} 스크래핑 완료")

        return positions

    async def _goto_next_page(self, page: Page, next_page_num: int) -> bool:
        """다음 페이지로 이동 - 사이트 구조에 맞게 구현"""
        try:
            # TODO: 사이트의 페이지네이션 구조에 맞게 수정
            next_link = page.locator(f'a.pagination:has-text("{next_page_num}")')
            if await next_link.count() > 0:
                await next_link.click()
                await page.wait_for_timeout(1500)
                return True
            return False
        except Exception:
            return False
```

#### 동적 탐색 vs 정적 job_id

| 방식 | 장점 | 단점 |
|------|------|------|
| **동적 탐색 (권장)** | 사이트 변경에 유연, 새 공고 자동 감지 | 키워드 매핑 필요, 초기 구현 복잡 |
| **정적 job_id** | 구현 단순, 정확한 타겟팅 | 사이트 변경 시 수동 업데이트 필요 |

기존 토스/카페24 스크래퍼는 동적 탐색 방식으로 구현되어 있습니다. 참고: `scraper.py`, `scraper_cafe24.py`

### Step 3: 직군 분류기 확장 (`job_classifier.py`)

```python
# CATEGORY_KEYWORDS에 새 회사의 키워드 추가 (필요 시)
# 기존 키워드는 대부분 범용적이므로 재사용 가능

# _str_to_category 메서드에 새 회사 카테고리 매핑 추가
def _str_to_category(self, s: str, company: str = "toss") -> Optional[Enum]:
    if company == "{company}":
        mapping = {
            "backend": {Company}JobCategory.BACKEND,
            # ...
        }
    else:
        mapping = {
            "backend": TossJobCategory.BACKEND,
            # ...
        }
    return mapping.get(s.lower().strip())
```

### Step 4: 프롬프트 생성기 (`prompt_generator_{company}.py`)

회사별 도메인/인재상이 다르므로 별도 파일로 구현하거나, 기존 `PromptGenerator`를 상속:

```python
class {Company}PromptGenerator(PromptGenerator):
    """회사명 전용 프롬프트 생성기"""

    def _build_prompt(self, ...):
        # 회사 특성에 맞게 평가 기준 수정
        # 예: 금융 대신 이커머스 도메인 평가
        # 예: 기술 스택 우선순위 조정
        pass
```

### Step 5: 워크플로우 통합 (`workflow_{company}.py`)

```python
class {Company}EvaluationWorkflow(ResumeEvaluationWorkflow):
    """회사명 이력서 평가 워크플로우"""

    def __init__(self, config: WorkflowConfig):
        super().__init__(config)
        # 회사 전용 스크래퍼 사용
        self.scraper = {Company}JobScraper(data_dir=f"{self.config.data_dir}/{company}")
        self.prompt_generator = {Company}PromptGenerator(data_dir=f"{self.config.data_dir}/{company}")
```

### Step 6: Slack 핸들러 연동 (`resume_handler.py`)

```python
# 환경변수 추가
{COMPANY}_RESUME_FEEDBACK_CHANNEL_ID = os.getenv("{COMPANY}_RESUME_FEEDBACK_CHANNEL_ID")

# 채널별 회사 매핑
CHANNEL_COMPANY_MAP = {
    SLACK_RESUME_FEEDBACK_CHANNEL_ID: "toss",
    {COMPANY}_RESUME_FEEDBACK_CHANNEL_ID: "{company}",
}

# 핸들러에서 회사별 워크플로우 선택
async def handle_resume_evaluation(channel_id: str, file_path: str):
    company = CHANNEL_COMPANY_MAP.get(channel_id, "toss")

    if company == "toss":
        workflow = ResumeEvaluationWorkflow(config)
    elif company == "{company}":
        workflow = {Company}EvaluationWorkflow(config)

    return await workflow.evaluate_with_classification(file_path)
```

### Step 7: 환경변수 추가

`.env` 파일에 추가:
```
{COMPANY}_RESUME_FEEDBACK_CHANNEL_ID=C0XXXXXXX
```

---

## 기존 토스 구현 참고

현재 토스 이력서 평가 시스템의 구조:

```
src/resume_evaluator/
├── __init__.py           # 모듈 exports
├── models.py             # TossJobCategory, JobRequirement, ScrapedData 등
├── scraper.py            # TossJobScraper (Playwright 기반)
├── job_classifier.py     # JobClassifier (AI 분류)
├── prompt_generator.py   # PromptGenerator (평가 프롬프트)
├── evaluator.py          # ResumeEvaluator (AI 평가)
├── workflow.py           # ResumeEvaluationWorkflow (오케스트레이션)
└── cli.py                # CLI 인터페이스
```

### 핵심 데이터 모델

```python
@dataclass
class JobRequirement:
    title: str
    company: str
    requirements: list[str]    # 인재상/자격요건
    preferred: list[str]       # 우대사항
    tech_stack: list[str]      # 기술스택
    responsibilities: list[str]  # 주요업무
    job_id: str
    category: PositionCategory
    scraped_at: datetime

@dataclass
class ScrapedData:
    positions: list[JobRequirement]
    scraped_at: datetime
    source_url: str
    content_hash: str  # 변경 감지용

@dataclass
class ClassificationResult:
    primary_category: TossJobCategory
    secondary_categories: list[TossJobCategory]
    confidence: float
    reasoning: str
    skills_detected: list[str]
    experience_years: Optional[int]

@dataclass
class EvaluationResult:
    total_score: int  # 0-100
    grade: EvaluationGrade  # S/A/B/C/D
    scores: dict  # 세부 점수
    strengths: list[str]
    weaknesses: list[str]
    recommended_positions: list[str]
    interview_questions: list[str]
    summary: str
```

### 스크래핑 시 주의사항

1. **Rate Limiting**: 요청 사이 1초 이상 대기
2. **Headless 모드**: 프로덕션에서는 `headless=True`
3. **캐싱**: `scraped_{category}.json`으로 카테고리별 캐싱
4. **해시 기반 변경 감지**: `content_hash`로 불필요한 재생성 방지
5. **동적 탐색 권장**: 정적 job_id 대신 키워드 기반 동적 탐색 사용
6. **페이지네이션/무한스크롤**: 사이트 구조에 맞게 구현 필요

### 평가 기준 (토스 기준)

- 핵심 기술 역량: 40점 (시스템설계 15 + 트래픽처리 15 + 기술스택 10)
- 문제 해결 능력: 25점 (장애대응 15 + 문제해결 10)
- 소프트 스킬: 20점 (주도성 10 + 협업 5 + 성장 5)
- 도메인 적합성: 15점 (금융/핀테크 10 + B2C 5)

---

## 체크리스트

새 회사 추가 시 체크리스트:

- [ ] `models.py`에 `{Company}JobCategory` Enum 추가
- [ ] `scraper_{company}.py` 스크래퍼 구현 (동적 탐색 방식 권장)
- [ ] 채용공고 HTML 구조 분석 및 선택자 설정
- [ ] `CATEGORY_KEYWORDS` 직군별 키워드 매핑 (동적 탐색 시)
- [ ] `prompt_generator_{company}.py` (필요 시) 평가 기준 커스터마이징
- [ ] `workflow_{company}.py` 워크플로우 통합
- [ ] `resume_handler.py` Slack 핸들러 연동
- [ ] `.env`에 채널 ID 환경변수 추가
- [ ] `__init__.py` exports 추가
- [ ] 테스트 스크립트 작성 (`scripts/test_{company}_eval.py`)
- [ ] Docker 빌드 및 배포

---

## 예시: 카카오 추가 요청

사용자가 다음과 같이 요청할 수 있습니다:

> "카카오 Backend 개발자 이력서 평가 플로우를 추가해줘.
> - 채용 사이트: https://careers.kakao.com
> - 직군: Backend, Frontend, App, DevOps, Data
> - Slack 채널 ID: C05XXXXXX
> - (HTML 샘플 첨부)"

이 경우 위 절차에 따라:
1. `KakaoJobCategory` Enum 생성
2. `KakaoJobScraper` 구현 (HTML 구조 분석 필요)
3. `KakaoEvaluationWorkflow` 생성
4. Slack 핸들러 연동
