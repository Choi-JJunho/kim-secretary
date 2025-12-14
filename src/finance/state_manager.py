"""재무 상태 관리자 - Dashboard 저장/로드/갱신"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .models import (
    FinancialDashboard,
    Transaction,
    TransactionType,
    PaymentMethod,
    ExpenseCategory,
    HousingType,
    TaxDeductionType,
    YTDMetrics,
    TaxStrategy,
    Housing,
    Loan,
    create_default_dashboard,
)

logger = logging.getLogger(__name__)


class FinanceStateManager:
    """재무 상태 관리자"""

    def __init__(self, data_dir: str = "data/finance"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.dashboard_path = self.data_dir / "dashboard.json"
        self.transactions_path = self.data_dir / "transactions.json"
        self._dashboard: Optional[FinancialDashboard] = None

    def load_dashboard(self) -> FinancialDashboard:
        """대시보드 로드 (없으면 기본값 생성)"""
        if self._dashboard:
            return self._dashboard

        if self.dashboard_path.exists():
            try:
                with open(self.dashboard_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._dashboard = FinancialDashboard.from_dict(data)
                logger.info(f"Dashboard loaded: {self.dashboard_path}")
            except Exception as e:
                logger.error(f"Failed to load dashboard: {e}")
                self._dashboard = create_default_dashboard(str(self.data_dir))
        else:
            logger.info("Creating default dashboard")
            self._dashboard = create_default_dashboard(str(self.data_dir))
            self.save_dashboard()

        return self._dashboard

    def save_dashboard(self) -> None:
        """대시보드 저장"""
        if not self._dashboard:
            return

        self._dashboard.updated_at = datetime.now()

        with open(self.dashboard_path, "w", encoding="utf-8") as f:
            json.dump(self._dashboard.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Dashboard saved: {self.dashboard_path}")

    def update_date(self, new_date: date) -> dict:
        """날짜 업데이트 및 연도 변경 처리"""
        dashboard = self.load_dashboard()
        old_date = dashboard.current_date
        old_year = old_date.year
        new_year = new_date.year

        changes = {
            "date_changed": True,
            "old_date": old_date.isoformat(),
            "new_date": new_date.isoformat(),
            "year_changed": old_year != new_year,
            "resets": [],
        }

        dashboard.current_date = new_date

        # 연도 변경 시 Reset
        if old_year != new_year:
            changes["resets"] = self._handle_year_change(dashboard, old_year, new_year)

        self.save_dashboard()
        return changes

    def _handle_year_change(self, dashboard: FinancialDashboard, old_year: int, new_year: int) -> list[str]:
        """연도 변경 시 Reset 처리"""
        resets = []

        # 1. YTD 지표 초기화
        dashboard.ytd_metrics = YTDMetrics(year=new_year)
        resets.append(f"YTD_Metrics 초기화 (연도: {new_year})")

        # 2. 이사 완료 확인 및 세금 전략 변경
        if dashboard.housing.planned_move_date:
            if dashboard.housing.planned_move_date.year == new_year:
                # 전세로 전환 예정
                if dashboard.tax_strategy:
                    dashboard.tax_strategy.focus_items = [
                        "주택임차차입금 원리금 상환액 공제",
                        "청년도약계좌 납입액 공제",
                    ]
                    dashboard.tax_strategy.notes = "월세 → 전세 전환으로 공제 항목 변경"
                    resets.append("Tax_Strategy: 월세 세액공제 → 주택임차차입금 원리금 상환액 공제")

        # 3. 나이 갱신 (생일 로직은 단순화 - 연도 변경 시 +1)
        dashboard.user_info.age += 1
        resets.append(f"Age: {dashboard.user_info.age - 1} → {dashboard.user_info.age}")

        return resets

    def process_moving(self, move_date: date, new_housing: Housing) -> dict:
        """이사 이벤트 처리"""
        dashboard = self.load_dashboard()

        old_housing = dashboard.housing
        changes = {
            "event": "moving",
            "move_date": move_date.isoformat(),
            "old_housing": old_housing.to_dict(),
            "new_housing": new_housing.to_dict(),
            "tax_changes": [],
        }

        # 주거 정보 업데이트
        dashboard.housing = new_housing
        dashboard.housing.move_in_date = move_date

        # 월세 → 전세 전환 시 세금 전략 변경
        if old_housing.housing_type == HousingType.MONTHLY_RENT and new_housing.housing_type == HousingType.JEONSE:
            if dashboard.tax_strategy:
                # 월세 세액공제 제거, 주택임차차입금 공제 추가
                if "월세 세액공제" in dashboard.tax_strategy.focus_items:
                    dashboard.tax_strategy.focus_items.remove("월세 세액공제")
                if "주택임차차입금 원리금 상환액 공제" not in dashboard.tax_strategy.focus_items:
                    dashboard.tax_strategy.focus_items.append("주택임차차입금 원리금 상환액 공제")
                changes["tax_changes"].append("월세 세액공제 → 주택임차차입금 원리금 상환액 공제")

        # 전세대출 정보가 있으면 Loan 추가
        if new_housing.loan_amount > 0:
            loan = Loan(
                name="전세대출 (HUG 버팀목)",
                principal=new_housing.loan_amount,
                remaining_balance=new_housing.loan_amount,
                interest_rate=new_housing.loan_interest_rate,
                monthly_payment=self._calculate_monthly_interest(
                    new_housing.loan_amount, new_housing.loan_interest_rate
                ),
                start_date=move_date,
                is_tax_deductible=True,
                deduction_type=TaxDeductionType.HOUSING_LOAN,
            )
            dashboard.loans.append(loan)
            changes["loan_added"] = loan.to_dict()

        self.save_dashboard()
        return changes

    def _calculate_monthly_interest(self, principal: int, annual_rate: float) -> int:
        """월 이자 계산 (이자만 납부 가정)"""
        if annual_rate == 0:
            return 0
        return int(principal * (annual_rate / 100) / 12)

    def add_transaction(self, transaction: Transaction) -> dict:
        """거래 추가 및 YTD 지표 업데이트"""
        dashboard = self.load_dashboard()

        # 거래 ID 생성
        if not transaction.id:
            transaction.id = f"txn_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # 거래 추가
        dashboard.recent_transactions.append(transaction)

        # 최근 100건만 유지
        if len(dashboard.recent_transactions) > 100:
            dashboard.recent_transactions = dashboard.recent_transactions[-100:]

        # YTD 지표 업데이트
        ytd_updates = self._update_ytd_metrics(dashboard, transaction)

        self.save_dashboard()

        return {
            "transaction_id": transaction.id,
            "ytd_updates": ytd_updates,
            "deduction_status": dashboard.get_credit_card_deduction_status(),
        }

    def _update_ytd_metrics(self, dashboard: FinancialDashboard, txn: Transaction) -> dict:
        """YTD 지표 업데이트"""
        if not dashboard.ytd_metrics:
            dashboard.ytd_metrics = YTDMetrics(year=dashboard.current_date.year)

        ytd = dashboard.ytd_metrics
        updates = {}

        if txn.transaction_type == TransactionType.EXPENSE:
            ytd.total_expense += txn.amount
            updates["total_expense"] = ytd.total_expense

            # 결제 수단별 누적
            if txn.payment_method == PaymentMethod.CREDIT_CARD:
                ytd.credit_card_usage += txn.amount
                updates["credit_card_usage"] = ytd.credit_card_usage
            elif txn.payment_method == PaymentMethod.DEBIT_CARD:
                ytd.debit_card_usage += txn.amount
                updates["debit_card_usage"] = ytd.debit_card_usage

            # 카테고리별
            if txn.category == ExpenseCategory.HOUSING:
                ytd.monthly_rent_paid += txn.amount
                updates["monthly_rent_paid"] = ytd.monthly_rent_paid
            elif txn.category == ExpenseCategory.LOAN_PAYMENT:
                ytd.loan_principal_paid += txn.amount
                updates["loan_principal_paid"] = ytd.loan_principal_paid

        elif txn.transaction_type == TransactionType.INCOME:
            ytd.total_income += txn.amount
            updates["total_income"] = ytd.total_income

        elif txn.transaction_type == TransactionType.SAVING:
            ytd.total_savings += txn.amount
            updates["total_savings"] = ytd.total_savings

        return updates

    def update_income(self, new_salary: int, reason: str = "") -> dict:
        """소득 변경 (연봉 인상, 성과급 등)"""
        dashboard = self.load_dashboard()
        old_salary = dashboard.user_info.salary

        dashboard.user_info.salary = new_salary

        # 소득 구간 재계산 (신용카드 공제 기준)
        changes = {
            "event": "income_change",
            "old_salary": old_salary,
            "new_salary": new_salary,
            "reason": reason,
            "new_deduction_status": dashboard.get_credit_card_deduction_status(),
        }

        self.save_dashboard()
        return changes

    def get_dashboard_summary(self) -> str:
        """대시보드 요약 문자열 생성 (AI 응답용)"""
        dashboard = self.load_dashboard()

        # 월 고정 지출
        monthly_fixed = dashboard.get_total_monthly_fixed_expense()

        # 신용카드 공제 상태
        deduction = dashboard.get_credit_card_deduction_status()

        # 복잡한 조건부 값 미리 계산
        planned_move = dashboard.housing.planned_move_date.isoformat() if dashboard.housing.planned_move_date else "N/A"
        ytd_year = dashboard.ytd_metrics.year if dashboard.ytd_metrics else dashboard.current_date.year
        remaining = deduction["remaining_to_limit"]
        deduction_status = "공제한도 도달" if deduction["limit_reached"] else f"한도까지 {remaining:,}원 남음"
        total_income = f"{dashboard.ytd_metrics.total_income:,}원" if dashboard.ytd_metrics else "0원"
        total_expense = f"{dashboard.ytd_metrics.total_expense:,}원" if dashboard.ytd_metrics else "0원"
        tax_focus = json.dumps(dashboard.tax_strategy.focus_items if dashboard.tax_strategy else [], ensure_ascii=False)
        tax_notes = dashboard.tax_strategy.notes if dashboard.tax_strategy else ""

        summary = f"""[Updated Dashboard]
```json
{{
  "Current_Date": "{dashboard.current_date.isoformat()}",
  "User_Info": {{
    "Name": "{dashboard.user_info.name}",
    "Age": {dashboard.user_info.age},
    "Job": "{dashboard.user_info.job}",
    "Salary": "{dashboard.user_info.salary:,}원",
    "Household": "{dashboard.user_info.household}"
  }},
  "Housing": {{
    "Type": "{dashboard.housing.housing_type.value}",
    "Deposit": "{dashboard.housing.deposit:,}원",
    "Monthly_Rent": "{dashboard.housing.monthly_rent:,}원",
    "Maintenance_Fee": "{dashboard.housing.maintenance_fee:,}원",
    "Loan_Amount": "{dashboard.housing.loan_amount:,}원",
    "Planned_Move": "{planned_move}"
  }},
  "Monthly_Fixed_Expense": "{monthly_fixed:,}원",
  "Savings": ["""

        for i, savings in enumerate(dashboard.savings_accounts):
            comma = "," if i < len(dashboard.savings_accounts) - 1 else ""
            tax_deductible = str(savings.is_tax_deductible).lower()
            summary += f"""
    {{
      "Name": "{savings.name}",
      "Monthly": "{savings.monthly_amount:,}원",
      "Tax_Deductible": {tax_deductible}
    }}{comma}"""

        summary += """
  ],
  "Loans": ["""

        for i, loan in enumerate(dashboard.loans):
            comma = "," if i < len(dashboard.loans) - 1 else ""
            summary += f"""
    {{
      "Name": "{loan.name}",
      "Remaining": "{loan.remaining_balance:,}원",
      "Monthly_Payment": "{loan.monthly_payment:,}원",
      "Interest_Rate": "{loan.interest_rate}%"
    }}{comma}"""

        summary += f"""
  ],
  "YTD_Metrics ({ytd_year})": {{
    "Credit_Card_Usage": "{deduction['total_usage']:,}원",
    "Deduction_Status": "{deduction_status}",
    "Total_Income": "{total_income}",
    "Total_Expense": "{total_expense}"
  }},
  "Tax_Strategy": {{
    "Focus": {tax_focus},
    "Notes": "{tax_notes}"
  }}
}}
```"""

        return summary

    def reset_dashboard(self) -> None:
        """대시보드 초기화 (기본값으로)"""
        self._dashboard = create_default_dashboard(str(self.data_dir))
        self.save_dashboard()
        logger.info("Dashboard reset to default")
