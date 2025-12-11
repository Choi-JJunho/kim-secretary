"""데이터 모델 정의"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TossJobCategory(str, Enum):
    """토스 채용공고 직군 카테고리 (토스 채용페이지 기준)"""
    ALL = "전체"
    BACKEND = "Backend"
    APP = "App"
    DEVICE = "Device"
    FRONTEND = "Frontend"
    FULLSTACK = "Full Stack"
    INFRA = "Infra"
    QA = "QA"
    MILITARY = "병역특례"


class Cafe24JobCategory(str, Enum):
    """카페24 채용공고 직군 카테고리"""
    ALL = "전체직군"
    PLANNING = "기획/운영"  # PM, 기획자, 운영
    DEVELOPMENT = "개발/시스템"
    DESIGN = "디자인"
    MARKETING = "마케팅"
    MANAGEMENT = "경영지원"
    PARTNERSHIP = "제휴/영업"
    CUSTOMER_SUPPORT = "고객지원"
    OTHER = "기타"


class PositionCategory(str, Enum):
    """포지션 카테고리 (레거시 호환용)"""
    BACKEND = "Backend"
    FRONTEND = "Frontend"
    APP = "App"
    DEVOPS = "DevOps"
    DATA = "Data"
    ML = "ML"
    SECURITY = "Security"
    QA = "QA"
    INFRA = "Infra"
    OTHER = "Other"


# TossJobCategory -> PositionCategory 매핑
TOSS_TO_POSITION_MAPPING = {
    TossJobCategory.BACKEND: PositionCategory.BACKEND,
    TossJobCategory.APP: PositionCategory.APP,
    TossJobCategory.DEVICE: PositionCategory.OTHER,  # Device는 별도 카테고리 없음
    TossJobCategory.FRONTEND: PositionCategory.FRONTEND,
    TossJobCategory.FULLSTACK: PositionCategory.BACKEND,  # Full Stack은 Backend로 분류
    TossJobCategory.INFRA: PositionCategory.INFRA,
    TossJobCategory.QA: PositionCategory.QA,
    TossJobCategory.MILITARY: PositionCategory.OTHER,  # 병역특례는 별도 처리
}


class EvaluationGrade(str, Enum):
    """평가 등급"""
    S = "S"  # 90-100: 즉시 채용 권장
    A = "A"  # 75-89: 적극 면접 권장
    B = "B"  # 60-74: 면접 진행 권장
    C = "C"  # 45-59: 조건부 면접 고려
    D = "D"  # 0-44: 채용 보류 권장


@dataclass
class JobRequirement:
    """채용 공고의 인재상/자격요건"""
    title: str
    company: str
    requirements: list[str]
    preferred: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    job_id: str = ""
    detail_url: str = ""  # 상세 페이지 URL (공고 보기 클릭 후의 URL)
    category: PositionCategory = PositionCategory.OTHER
    scraped_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "title": self.title,
            "company": self.company,
            "requirements": self.requirements,
            "preferred": self.preferred,
            "tech_stack": self.tech_stack,
            "responsibilities": self.responsibilities,
            "job_id": self.job_id,
            "detail_url": self.detail_url,
            "category": self.category.value,
            "scraped_at": self.scraped_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JobRequirement":
        """딕셔너리에서 생성"""
        return cls(
            title=data["title"],
            company=data["company"],
            requirements=data["requirements"],
            preferred=data.get("preferred", []),
            tech_stack=data.get("tech_stack", []),
            responsibilities=data.get("responsibilities", []),
            job_id=data.get("job_id", ""),
            detail_url=data.get("detail_url", ""),
            category=PositionCategory(data.get("category", "Other")),
            scraped_at=datetime.fromisoformat(data["scraped_at"]) if "scraped_at" in data else datetime.now(),
        )


@dataclass
class ScrapedData:
    """스크래핑된 데이터 전체"""
    positions: list[JobRequirement]
    scraped_at: datetime = field(default_factory=datetime.now)
    source_url: str = ""

    @property
    def content_hash(self) -> str:
        """콘텐츠 해시 (변경 감지용)"""
        content = json.dumps(
            [p.to_dict() for p in self.positions],
            sort_keys=True,
            ensure_ascii=False
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "positions": [p.to_dict() for p in self.positions],
            "scraped_at": self.scraped_at.isoformat(),
            "source_url": self.source_url,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScrapedData":
        """딕셔너리에서 생성"""
        return cls(
            positions=[JobRequirement.from_dict(p) for p in data["positions"]],
            scraped_at=datetime.fromisoformat(data["scraped_at"]) if "scraped_at" in data else datetime.now(),
            source_url=data.get("source_url", ""),
        )


@dataclass
class GeneratedPrompt:
    """생성된 시스템 프롬프트"""
    prompt: str
    source_hash: str  # 소스 데이터의 content_hash
    generated_at: datetime = field(default_factory=datetime.now)
    target_position: str = ""  # e.g., "Backend", "Frontend"

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "prompt": self.prompt,
            "source_hash": self.source_hash,
            "generated_at": self.generated_at.isoformat(),
            "target_position": self.target_position,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeneratedPrompt":
        """딕셔너리에서 생성"""
        return cls(
            prompt=data["prompt"],
            source_hash=data["source_hash"],
            generated_at=datetime.fromisoformat(data["generated_at"]) if "generated_at" in data else datetime.now(),
            target_position=data.get("target_position", ""),
        )


@dataclass
class EvaluationResult:
    """이력서 평가 결과"""
    total_score: int
    grade: EvaluationGrade

    # 세부 점수
    technical_skills_score: int  # 40점 만점
    problem_solving_score: int   # 25점 만점
    soft_skills_score: int       # 20점 만점
    domain_fit_score: int        # 15점 만점

    # 상세 분석
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommended_positions: list[str] = field(default_factory=list)
    interview_questions: list[str] = field(default_factory=list)
    summary: str = ""

    # 메타데이터
    evaluated_at: datetime = field(default_factory=datetime.now)
    evaluator_model: str = ""
    raw_response: str = ""

    @classmethod
    def grade_from_score(cls, score: int) -> EvaluationGrade:
        """점수에서 등급 계산"""
        if score >= 90:
            return EvaluationGrade.S
        elif score >= 75:
            return EvaluationGrade.A
        elif score >= 60:
            return EvaluationGrade.B
        elif score >= 45:
            return EvaluationGrade.C
        else:
            return EvaluationGrade.D

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "total_score": self.total_score,
            "grade": self.grade.value,
            "technical_skills_score": self.technical_skills_score,
            "problem_solving_score": self.problem_solving_score,
            "soft_skills_score": self.soft_skills_score,
            "domain_fit_score": self.domain_fit_score,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommended_positions": self.recommended_positions,
            "interview_questions": self.interview_questions,
            "summary": self.summary,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluator_model": self.evaluator_model,
        }
