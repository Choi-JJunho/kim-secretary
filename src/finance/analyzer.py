"""재무 분석기 - AI를 사용한 재무 상담 및 분석"""

import json
import logging
import re
from datetime import date, datetime
from typing import Optional

from ..ai.gemini import GeminiProvider
from ..ai.claude import ClaudeProvider
from .models import (
    Transaction,
    TransactionType,
    PaymentMethod,
    ExpenseCategory,
)
from .state_manager import FinanceStateManager
from .prompts import (
    get_cfo_system_prompt,
    get_message_analysis_prompt,
    get_expense_extraction_prompt,
)

logger = logging.getLogger(__name__)


class FinanceAnalyzer:
    """AI 기반 재무 분석기"""

    def __init__(
        self,
        ai_provider: str = "gemini",
        data_dir: str = "data/finance"
    ):
        self.state_manager = FinanceStateManager(data_dir)
        self.ai_provider_name = ai_provider
        self._ai_provider = None

    def _get_ai_provider(self):
        """AI 제공자 지연 초기화"""
        if self._ai_provider is None:
            if self.ai_provider_name == "gemini":
                try:
                    self._ai_provider = GeminiProvider()
                except Exception as e:
                    logger.warning(f"Gemini 초기화 실패, Claude로 전환: {e}")
                    self._ai_provider = ClaudeProvider()
            else:
                self._ai_provider = ClaudeProvider()
        return self._ai_provider

    async def process_message(self, message: str) -> str:
        """사용자 메시지 처리 및 CFO 응답 생성"""
        try:
            # 1. 메시지 의도 분석
            intent_data = await self._analyze_intent(message)
            logger.info(f"분석된 의도: {intent_data}")

            # 2. 의도에 따른 처리
            if intent_data.get("intent") == "expense":
                await self._process_expense(message, intent_data)
            elif intent_data.get("intent") == "income":
                await self._process_income(message, intent_data)
            elif intent_data.get("intent") == "event":
                await self._process_event(message, intent_data)

            # 3. CFO 응답 생성
            response = await self._generate_cfo_response(message)

            return response

        except Exception as e:
            logger.error(f"메시지 처리 실패: {e}")
            # 에러 발생 시에도 기본 응답 제공
            dashboard_summary = self.state_manager.get_dashboard_summary()
            return f"처리 중 오류가 발생했습니다: {str(e)}\n\n현재 상태:\n{dashboard_summary}"

    async def _analyze_intent(self, message: str) -> dict:
        """메시지 의도 분석"""
        try:
            prompt = get_message_analysis_prompt(message)
            ai = self._get_ai_provider()
            response = await ai.generate(prompt)

            # JSON 추출
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # JSON 블록 없이 직접 파싱 시도
            return json.loads(response)

        except Exception as e:
            logger.warning(f"의도 분석 실패: {e}")
            return {"intent": "question", "confidence": 0.5}

    async def _process_expense(self, message: str, intent_data: dict) -> None:
        """지출 처리"""
        try:
            prompt = get_expense_extraction_prompt(message)
            ai = self._get_ai_provider()
            response = await ai.generate(prompt)

            # JSON 추출
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                expense_data = json.loads(json_match.group(1))
            else:
                expense_data = json.loads(response)

            # Transaction 생성
            txn_date = date.today()
            if expense_data.get("date"):
                try:
                    txn_date = date.fromisoformat(expense_data["date"])
                except:
                    pass

            payment_method = None
            if expense_data.get("payment_method"):
                try:
                    payment_method = PaymentMethod(expense_data["payment_method"])
                except:
                    pass

            category = ExpenseCategory.OTHER
            if expense_data.get("category"):
                try:
                    category = ExpenseCategory(expense_data["category"])
                except:
                    pass

            transaction = Transaction(
                date=txn_date,
                amount=int(expense_data.get("amount", 0)),
                transaction_type=TransactionType.EXPENSE,
                category=category,
                payment_method=payment_method,
                description=expense_data.get("description", ""),
            )

            # 상태 업데이트
            result = self.state_manager.add_transaction(transaction)
            logger.info(f"지출 기록 완료: {result}")

        except Exception as e:
            logger.error(f"지출 처리 실패: {e}")

    async def _process_income(self, message: str, intent_data: dict) -> None:
        """수입 처리"""
        try:
            extracted = intent_data.get("extracted_data", {})
            amount = extracted.get("amount", 0)

            if amount > 0:
                transaction = Transaction(
                    date=date.today(),
                    amount=amount,
                    transaction_type=TransactionType.INCOME,
                    category=ExpenseCategory.OTHER,
                    description=extracted.get("description", "수입"),
                )
                self.state_manager.add_transaction(transaction)
                logger.info(f"수입 기록 완료: {amount}원")

        except Exception as e:
            logger.error(f"수입 처리 실패: {e}")

    async def _process_event(self, message: str, intent_data: dict) -> None:
        """이벤트 처리 (이사, 연봉 변경 등)"""
        try:
            sub_intent = intent_data.get("sub_intent", "")
            extracted = intent_data.get("extracted_data", {})

            if sub_intent == "moving":
                logger.info("이사 이벤트 감지 - 수동 처리 필요")
                # 이사는 복잡한 데이터가 필요하므로 별도 명령어로 처리

            elif sub_intent == "salary_change":
                new_salary = extracted.get("new_salary")
                if new_salary:
                    self.state_manager.update_income(new_salary, "연봉 변경")
                    logger.info(f"연봉 변경 완료: {new_salary}")

        except Exception as e:
            logger.error(f"이벤트 처리 실패: {e}")

    async def _generate_cfo_response(self, message: str) -> str:
        """CFO 응답 생성"""
        dashboard_state = self.state_manager.get_dashboard_summary()
        system_prompt = get_cfo_system_prompt(dashboard_state)

        ai = self._get_ai_provider()
        response = await ai.generate(
            prompt=message,
            system_prompt=system_prompt
        )

        # 응답에 Dashboard가 없으면 추가
        if "[Updated Dashboard]" not in response:
            response += f"\n\n{dashboard_state}"

        return response

    async def get_deduction_status(self) -> str:
        """공제 현황 조회"""
        dashboard = self.state_manager.load_dashboard()
        status = dashboard.get_credit_card_deduction_status()

        result = f"""## 💳 신용카드 공제 현황

- **총 사용액**: {status['total_usage']:,}원
- **최소 사용 기준** (총급여 25%): {status['minimum_threshold']:,}원
- **공제 대상 금액**: {status['excess_usage']:,}원
- **예상 공제액**: {status['deductible_amount']:,}원
- **공제 한도**: {status['limit']:,}원
- **상태**: {'✅ 공제한도 도달' if status['limit_reached'] else f'⏳ 한도까지 {status["remaining_to_limit"]:,}원 남음'}

{self.state_manager.get_dashboard_summary()}"""

        return result

    async def get_monthly_summary(self, year: int = None, month: int = None) -> str:
        """월간 요약 조회"""
        dashboard = self.state_manager.load_dashboard()

        if not year:
            year = dashboard.current_date.year
        if not month:
            month = dashboard.current_date.month

        # 해당 월 거래 필터링
        transactions = [
            t for t in dashboard.recent_transactions
            if t.date.year == year and t.date.month == month
        ]

        total_expense = sum(t.amount for t in transactions if t.transaction_type == TransactionType.EXPENSE)
        total_income = sum(t.amount for t in transactions if t.transaction_type == TransactionType.INCOME)

        # 카테고리별 집계
        category_totals = {}
        for t in transactions:
            if t.transaction_type == TransactionType.EXPENSE:
                cat = t.category.value
                category_totals[cat] = category_totals.get(cat, 0) + t.amount

        result = f"""## 📊 {year}년 {month}월 요약

### 수입/지출
- **총 수입**: {total_income:,}원
- **총 지출**: {total_expense:,}원
- **수지**: {total_income - total_expense:,}원

### 카테고리별 지출
"""
        for cat, amount in sorted(category_totals.items(), key=lambda x: -x[1]):
            result += f"- {cat}: {amount:,}원\n"

        result += f"\n{self.state_manager.get_dashboard_summary()}"
        return result

    def reset_state(self) -> str:
        """상태 초기화"""
        self.state_manager.reset_dashboard()
        return "대시보드가 초기화되었습니다.\n\n" + self.state_manager.get_dashboard_summary()
