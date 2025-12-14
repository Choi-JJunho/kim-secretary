#!/usr/bin/env python3
"""재무관리 모듈 테스트 스크립트

finance 모듈만 독립적으로 테스트합니다.
다른 모듈(resume_evaluator 등)의 의존성을 피하기 위해 직접 임포트합니다.
"""

import asyncio
import sys
from pathlib import Path
from datetime import date

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 직접 finance 모듈만 임포트 (src/__init__.py 피하기)
# src.finance.models 대신 직접 경로 지정
import importlib.util

def load_module_directly(module_name: str, file_path: str):
    """직접 모듈 로드 (의존성 순환 방지)"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# models 로드
models = load_module_directly(
    "src.finance.models",
    str(project_root / "src" / "finance" / "models.py")
)
create_default_dashboard = models.create_default_dashboard
Transaction = models.Transaction
TransactionType = models.TransactionType
PaymentMethod = models.PaymentMethod
ExpenseCategory = models.ExpenseCategory

# state_manager 로드
state_manager_module = load_module_directly(
    "src.finance.state_manager",
    str(project_root / "src" / "finance" / "state_manager.py")
)
FinanceStateManager = state_manager_module.FinanceStateManager


def test_models():
    """모델 테스트"""
    print("\n=== 모델 테스트 ===")

    # 기본 대시보드 생성
    dashboard = create_default_dashboard()
    print(f"✅ 기본 대시보드 생성 완료")
    print(f"  - 사용자: {dashboard.user_info.name}")
    print(f"  - 나이: {dashboard.user_info.age}세")
    print(f"  - 연봉: {dashboard.user_info.salary:,}원")
    print(f"  - 주거: {dashboard.housing.housing_type.value}")
    print(f"  - 월세: {dashboard.housing.monthly_rent:,}원")
    print(f"  - 저축 계좌: {len(dashboard.savings_accounts)}개")

    # 공제 상태 확인
    deduction = dashboard.get_credit_card_deduction_status()
    print(f"\n💳 신용카드 공제 상태:")
    print(f"  - 사용액: {deduction['total_usage']:,}원")
    print(f"  - 공제한도 도달: {'예' if deduction['limit_reached'] else '아니오'}")

    # JSON 직렬화/역직렬화
    json_str = dashboard.to_json()
    restored = dashboard.from_json(json_str)
    print(f"\n✅ JSON 직렬화/역직렬화 성공")
    assert restored.user_info.name == dashboard.user_info.name


def test_state_manager():
    """상태 관리자 테스트"""
    print("\n=== 상태 관리자 테스트 ===")

    # 테스트용 임시 디렉토리
    test_dir = "data/finance_test"
    manager = FinanceStateManager(data_dir=test_dir)

    # 대시보드 로드
    dashboard = manager.load_dashboard()
    print(f"✅ 대시보드 로드 완료")

    # 요약 생성
    summary = manager.get_dashboard_summary()
    print(f"\n📊 대시보드 요약 (일부):")
    print(summary[:500] + "...")

    # 거래 추가
    txn = Transaction(
        date=date.today(),
        amount=15000,
        transaction_type=TransactionType.EXPENSE,
        category=ExpenseCategory.FOOD,
        payment_method=PaymentMethod.CREDIT_CARD,
        description="점심 식사",
    )
    result = manager.add_transaction(txn)
    print(f"\n✅ 거래 추가 완료: {result['transaction_id']}")
    print(f"  - 신용카드 누적: {result['deduction_status']['total_usage']:,}원")

    # 정리
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)
    print(f"\n✅ 테스트 데이터 정리 완료")


async def test_analyzer():
    """분석기 테스트 (AI 호출 없이)"""
    print("\n=== 분석기 테스트 ===")

    try:
        from src.finance.analyzer import FinanceAnalyzer
    except ImportError as e:
        print(f"⚠️ 분석기 임포트 실패 (의존성 누락): {e}")
        return

    test_dir = "data/finance_test2"
    analyzer = FinanceAnalyzer(data_dir=test_dir)

    # 공제 현황 조회 (AI 호출 없음)
    try:
        status = await analyzer.get_deduction_status()
        print(f"✅ 공제 현황 조회 완료")
        print(status[:300] + "...")
    except Exception as e:
        print(f"⚠️ 공제 현황 조회 실패 (AI 미설정): {e}")

    # 정리
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)
    print(f"\n✅ 테스트 데이터 정리 완료")


async def test_ai_response():
    """AI 응답 테스트 (실제 AI 호출)"""
    print("\n=== AI 응답 테스트 ===")
    print("⚠️ 이 테스트는 Gemini/Claude CLI가 설정되어 있어야 합니다.")

    try:
        from src.finance.analyzer import FinanceAnalyzer
    except ImportError as e:
        print(f"⚠️ 분석기 임포트 실패 (의존성 누락): {e}")
        return

    test_dir = "data/finance_test3"
    analyzer = FinanceAnalyzer(data_dir=test_dir)

    try:
        # 간단한 질문
        response = await analyzer.process_message("현재 신용카드 공제 현황을 알려줘")
        print(f"✅ AI 응답 생성 완료")
        print(f"\n응답:\n{response[:1000]}...")
    except Exception as e:
        print(f"❌ AI 응답 실패: {e}")
    finally:
        # 정리
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)


def main():
    """메인 테스트 실행"""
    print("=" * 50)
    print("재무관리 모듈 테스트")
    print("=" * 50)

    # 모델 테스트
    test_models()

    # 상태 관리자 테스트
    test_state_manager()

    # 분석기 테스트 (비동기)
    asyncio.run(test_analyzer())

    # AI 응답 테스트 (선택적)
    if "--with-ai" in sys.argv:
        asyncio.run(test_ai_response())
    else:
        print("\n💡 AI 응답 테스트를 실행하려면: python scripts/test_finance.py --with-ai")

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 완료!")
    print("=" * 50)


if __name__ == "__main__":
    main()
