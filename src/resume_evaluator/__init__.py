"""이력서 평가 워크플로우 모듈

채용공고의 인재상을 스크래핑하고,
이를 기반으로 이력서를 평가하는 AI Agent 시스템입니다.

지원 회사:
- 토스 (Toss): 개발자 직군 (Backend, Frontend, App 등)
- 카페24 (Cafe24): PM/기획 직군

워크플로우:
1. 직군 분류: 이력서 분석하여 적합한 직군 추천 (토스만)
2. 스크래핑: 해당 직군의 채용공고에서 인재상 수집
3. 프롬프트 생성: 인재상 기반 시스템 프롬프트 생성 (변경 시에만)
4. 평가: AI Agent가 이력서 평가

사용 예시 (토스):
    >>> from src.resume_evaluator import ResumeEvaluationWorkflow, WorkflowConfig
    >>> config = WorkflowConfig(ai_provider="claude")
    >>> workflow = ResumeEvaluationWorkflow(config)
    >>> result = await workflow.evaluate_with_classification("resume.pdf")

사용 예시 (카페24):
    >>> from src.resume_evaluator import Cafe24EvaluationWorkflow, Cafe24WorkflowConfig
    >>> config = Cafe24WorkflowConfig(ai_provider="claude")
    >>> workflow = Cafe24EvaluationWorkflow(config)
    >>> await workflow.initialize()
    >>> result = await workflow.evaluate_resume_file("resume.pdf", "PM")
"""

from .models import (
    TossJobCategory,
    Cafe24JobCategory,
    PositionCategory,
    EvaluationGrade,
    JobRequirement,
    ScrapedData,
    GeneratedPrompt,
    EvaluationResult,
)
from .scraper import TossJobScraper
from .scraper_cafe24 import Cafe24JobScraper
from .prompt_generator import PromptGenerator
from .prompt_generator_cafe24 import Cafe24PromptGenerator
from .evaluator import ResumeEvaluator
from .job_classifier import JobClassifier, ClassificationResult
from .workflow import (
    WorkflowConfig,
    ResumeEvaluationWorkflow,
    EvaluationResultWithClassification,
    run_workflow,
)
from .workflow_cafe24 import (
    Cafe24WorkflowConfig,
    Cafe24EvaluationWorkflow,
    run_cafe24_workflow,
)

__all__ = [
    # Models
    "TossJobCategory",
    "Cafe24JobCategory",
    "PositionCategory",
    "EvaluationGrade",
    "JobRequirement",
    "ScrapedData",
    "GeneratedPrompt",
    "EvaluationResult",
    # Components - Toss
    "TossJobScraper",
    "PromptGenerator",
    "ResumeEvaluator",
    "JobClassifier",
    "ClassificationResult",
    # Components - Cafe24
    "Cafe24JobScraper",
    "Cafe24PromptGenerator",
    # Workflow - Toss
    "WorkflowConfig",
    "ResumeEvaluationWorkflow",
    "EvaluationResultWithClassification",
    "run_workflow",
    # Workflow - Cafe24
    "Cafe24WorkflowConfig",
    "Cafe24EvaluationWorkflow",
    "run_cafe24_workflow",
]
