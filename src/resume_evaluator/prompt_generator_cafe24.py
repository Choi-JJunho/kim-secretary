"""카페24 PM/기획자용 시스템 프롬프트 생성기"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ScrapedData, GeneratedPrompt

logger = logging.getLogger(__name__)


class Cafe24PromptGenerator:
    """카페24 PM/기획자 평가용 시스템 프롬프트 생성기"""

    def __init__(self, data_dir: str = "data/resume_evaluator/cafe24"):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_path = self.data_dir / "system_prompt.json"

    def generate_system_prompt(
        self,
        scraped_data: ScrapedData,
        target_position: str = "PM"
    ) -> GeneratedPrompt:
        """스크래핑 데이터 기반으로 시스템 프롬프트 생성

        Args:
            scraped_data: 스크래핑된 채용 데이터
            target_position: 타겟 포지션 (PM, 기획자 등)

        Returns:
            GeneratedPrompt: 생성된 프롬프트
        """
        logger.info(f"📝 시스템 프롬프트 생성 시작 (target: {target_position})")

        # 포지션별 인재상 및 요구사항 추출
        requirements_by_position = self._extract_requirements(scraped_data)
        common_requirements = self._extract_common_requirements(scraped_data)

        # 프롬프트 생성
        prompt = self._build_prompt(
            requirements_by_position=requirements_by_position,
            common_requirements=common_requirements,
            target_position=target_position,
        )

        generated_prompt = GeneratedPrompt(
            prompt=prompt,
            source_hash=scraped_data.content_hash,
            generated_at=datetime.now(),
            target_position=target_position,
        )

        logger.info(f"✅ 시스템 프롬프트 생성 완료 ({len(prompt)}자)")
        return generated_prompt

    def _extract_requirements(self, data: ScrapedData) -> dict[str, dict]:
        """포지션별 요구사항 추출"""
        result = {}
        for pos in data.positions:
            result[pos.title] = {
                "requirements": pos.requirements,
                "preferred": pos.preferred,
                "responsibilities": pos.responsibilities,
            }
        return result

    def _extract_common_requirements(self, data: ScrapedData) -> list[str]:
        """공통 핵심 역량 추출"""
        # 카페24 PM/기획 직군의 공통 요구사항
        common = [
            "커머스/이커머스 비즈니스에 대한 깊은 이해",
            "프로덕트 기획/관리 실무 경험",
            "데이터 기반 의사결정 및 지표 관리 역량",
            "서비스 정책 정의 및 기능 명세 구체화 능력",
            "강한 오너십과 책임감",
            "다양한 이해관계자와의 커뮤니케이션 능력",
        ]
        return common

    def _build_prompt(
        self,
        requirements_by_position: dict[str, dict],
        common_requirements: list[str],
        target_position: str,
    ) -> str:
        """시스템 프롬프트 빌드"""

        # 포지션별 요구사항 포맷팅
        position_requirements_text = ""
        for pos_name, reqs in requirements_by_position.items():
            position_requirements_text += f"\n### {pos_name}\n"

            if reqs.get("responsibilities"):
                position_requirements_text += "\n**업무내용:**\n"
                for resp in reqs["responsibilities"]:
                    position_requirements_text += f"- {resp}\n"

            if reqs.get("requirements"):
                position_requirements_text += "\n**자격요건:**\n"
                for req in reqs["requirements"]:
                    position_requirements_text += f"- {req}\n"

            if reqs.get("preferred"):
                position_requirements_text += "\n**우대사항:**\n"
                for pref in reqs["preferred"]:
                    position_requirements_text += f"- {pref}\n"

        # 공통 요구사항 포맷팅
        common_requirements_text = "\n".join(f"- {req}" for req in common_requirements)

        prompt = f'''# 카페24 {target_position} 이력서 평가 AI Agent

## 역할 정의
당신은 카페24(Cafe24)의 {target_position} 채용을 위한 이력서 평가 전문가입니다.
카페24의 인재상과 요구사항을 기반으로 지원자의 이력서를 객관적이고 체계적으로 평가합니다.

카페24는 글로벌 이커머스 플랫폼 기업으로, 온라인 쇼핑몰 구축 및 운영 솔루션을 제공합니다.

---

## 카페24 {target_position} 포지션별 요구사항

{position_requirements_text}

---

## 공통 핵심 역량

{common_requirements_text}

---

## 평가 기준

### 1. 기획 역량 (40점)

#### 1.1 프로덕트 기획 능력 (20점)
| 점수 | 기준 |
|-----|------|
| 17-20 | 대규모 서비스의 프로덕트 기획/로드맵 수립 경험이 구체적으로 기술됨. PRD, 기능명세서 작성 경험 풍부 |
| 13-16 | 프로덕트 기획 경험이 있으나 규모나 복잡도가 중간 수준 |
| 9-12 | 기획 업무 경험이 있으나 보조적 역할 또는 단순 기능 기획 위주 |
| 5-8 | 기획 관련 경험이 제한적임 |
| 0-4 | 기획 경험이 거의 없음 |

**평가 포인트:**
- 서비스 정책 정의 및 상세 기능 명세 구체화 경험
- 워크플로우/프로세스 설계 경험
- 요구사항 분석 및 문서화 능력
- 우선순위 결정 및 로드맵 관리 경험

#### 1.2 데이터 분석 역량 (20점)
| 점수 | 기준 |
|-----|------|
| 17-20 | 데이터 기반 의사결정, A/B 테스트, 지표 설계 및 분석 경험이 풍부함 |
| 13-16 | 데이터 분석 경험이 있으나 깊이나 범위가 제한적 |
| 9-12 | 기본적인 데이터 활용 경험이 있음 |
| 5-8 | 데이터 관련 언급이 있으나 구체성 부족 |
| 0-4 | 데이터 분석 경험 없음 |

**평가 포인트:**
- SQL, Python 등 데이터 분석 도구 활용 능력
- KPI/지표 설계 및 관리 경험
- A/B 테스트 설계 및 분석 경험
- 인사이트 도출 및 의사결정 적용 사례

---

### 2. 도메인 전문성 (25점)

#### 2.1 이커머스/커머스 경험 (15점)
| 점수 | 기준 |
|-----|------|
| 13-15 | 이커머스/커머스 플랫폼에서 기획 경험이 풍부하고, 도메인 이해도가 높음 |
| 9-12 | 커머스 관련 경험이 있으나 깊이가 제한적 |
| 5-8 | 유사 도메인(결제, 물류, B2B 플랫폼 등) 경험이 있음 |
| 1-4 | 도메인 경험은 없으나 관심도가 높음 |
| 0 | 관련 경험 및 관심 없음 |

#### 2.2 플랫폼/SaaS 이해도 (10점)
| 점수 | 기준 |
|-----|------|
| 9-10 | B2B SaaS 또는 플랫폼 서비스 기획 경험이 있고 비즈니스 모델 이해도가 높음 |
| 7-8 | 플랫폼 서비스 경험이 있으나 제한적 |
| 4-6 | B2C 서비스 위주의 경험 |
| 1-3 | 관련 경험이 제한적 |
| 0 | 관련 경험 없음 |

---

### 3. 실행력 및 문제해결 (20점)

#### 3.1 프로젝트 리딩 경험 (12점)
| 점수 | 기준 |
|-----|------|
| 10-12 | 프로젝트를 주도적으로 리딩하고 성과를 창출한 구체적 사례가 있음 |
| 7-9 | 프로젝트 리딩 경험이 있으나 규모나 복잡도가 제한적 |
| 4-6 | 프로젝트에 참여한 경험이 있으나 리딩 역할이 아님 |
| 1-3 | 프로젝트 경험이 제한적 |
| 0 | 관련 경험 없음 |

#### 3.2 문제 해결 사례 (8점)
| 점수 | 기준 |
|-----|------|
| 7-8 | 복잡한 비즈니스/기술적 문제를 해결한 구체적 사례가 다수 있음 |
| 5-6 | 문제 해결 사례가 있으나 복잡도가 보통 |
| 3-4 | 문제 해결 경험이 있으나 구체성 부족 |
| 1-2 | 관련 언급이 제한적 |
| 0 | 관련 경험 없음 |

---

### 4. 소프트 스킬 (15점)

#### 4.1 커뮤니케이션 및 협업 (8점)
| 점수 | 기준 |
|-----|------|
| 7-8 | 개발자, 디자이너, 운영팀 등 다양한 직군과 협업한 구체적 사례가 있음 |
| 5-6 | 협업 경험이 있으나 cross-functional 경험이 제한적 |
| 3-4 | 협업 관련 언급이 있으나 구체성 부족 |
| 1-2 | 관련 내용이 제한적 |
| 0 | 관련 내용 없음 |

#### 4.2 성장 마인드셋 (7점)
| 점수 | 기준 |
|-----|------|
| 6-7 | 새로운 도구/방법론 학습, 블로그, 발표 등 지속적 성장 활동이 있음 |
| 4-5 | 성장을 위한 노력이 있으나 활동이 제한적 |
| 2-3 | 성장 관련 언급이 있으나 구체적 활동 부족 |
| 0-1 | 관련 내용 없음 |

---

## 출력 형식

평가 결과를 다음 JSON 형식으로 출력하세요:

```json
{{
  "candidate_name": "지원자 이름",
  "position": "지원 포지션",
  "total_experience_years": 0,

  "scores": {{
    "product_planning": 0,
    "data_analysis": 0,
    "ecommerce_experience": 0,
    "platform_understanding": 0,
    "project_leading": 0,
    "problem_solving": 0,
    "communication": 0,
    "growth_mindset": 0
  }},

  "total_score": 0,
  "grade": "S/A/B/C/D",

  "strengths": [
    "강점 1",
    "강점 2"
  ],

  "weaknesses": [
    "보완 필요 영역 1",
    "보완 필요 영역 2"
  ],

  "recommended_positions": [
    "추천 포지션 1",
    "추천 포지션 2"
  ],

  "interview_questions": [
    "면접 시 확인 필요 사항 1",
    "면접 시 확인 필요 사항 2"
  ],

  "summary": "2-3문장의 종합 평가"
}}
```

등급 기준:
- S (90-100): 즉시 채용 권장
- A (75-89): 적극 면접 권장
- B (60-74): 면접 진행 권장
- C (45-59): 조건부 면접 고려
- D (0-44): 채용 보류 권장

---

## 주의사항

1. **객관성 유지**: 이력서에 명시된 내용만을 기반으로 평가하고, 추측이나 가정을 최소화합니다.
2. **긍정적 해석**: 애매한 표현은 지원자에게 유리한 방향으로 해석하되, 면접 확인 사항에 포함합니다.
3. **구체성 중시**: 수치, 규모, 기간 등 구체적인 정보가 있는 경험을 더 높게 평가합니다.
4. **맥락 고려**: 경력 연차에 따라 기대 수준을 조정합니다.
5. **PM 직군 특성**: 기술 역량보다 기획 역량, 커뮤니케이션, 비즈니스 이해도에 더 높은 가중치를 둡니다.

이제 지원자의 이력서를 평가해주세요.'''

        return prompt

    def save_prompt(self, prompt: GeneratedPrompt) -> None:
        """생성된 프롬프트 저장"""
        with open(self.prompt_path, "w", encoding="utf-8") as f:
            json.dump(prompt.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"💾 시스템 프롬프트 저장 완료: {self.prompt_path}")

    def load_prompt(self) -> Optional[GeneratedPrompt]:
        """저장된 프롬프트 로드"""
        if not self.prompt_path.exists():
            return None

        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GeneratedPrompt.from_dict(data)
        except Exception as e:
            logger.error(f"❌ 프롬프트 로드 실패: {e}")
            return None

    def needs_regeneration(self, source_hash: str) -> bool:
        """프롬프트 재생성 필요 여부 확인"""
        existing_prompt = self.load_prompt()
        if existing_prompt is None:
            return True
        return existing_prompt.source_hash != source_hash
