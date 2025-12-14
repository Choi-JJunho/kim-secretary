"""재무관리 시스템 데이터 모델"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Optional
import json


class TransactionType(str, Enum):
    """거래 유형"""
    INCOME = "income"           # 수입
    EXPENSE = "expense"         # 지출
    TRANSFER = "transfer"       # 이체
    SAVING = "saving"           # 저축


class PaymentMethod(str, Enum):
    """결제 수단"""
    CREDIT_CARD = "credit_card"     # 신용카드
    DEBIT_CARD = "debit_card"       # 체크카드
    CASH = "cash"                   # 현금
    TRANSFER = "transfer"           # 계좌이체


class ExpenseCategory(str, Enum):
    """지출 카테고리"""
    HOUSING = "housing"             # 주거비 (월세, 관리비)
    FOOD = "food"                   # 식비
    TRANSPORT = "transport"         # 교통비
    UTILITIES = "utilities"         # 공과금
    INSURANCE = "insurance"         # 보험
    SAVINGS = "savings"             # 저축
    ENTERTAINMENT = "entertainment" # 여가/문화
    SHOPPING = "shopping"           # 쇼핑
    HEALTHCARE = "healthcare"       # 의료비
    EDUCATION = "education"         # 교육비
    LOAN_PAYMENT = "loan_payment"   # 대출상환
    OTHER = "other"                 # 기타


class HousingType(str, Enum):
    """주거 유형"""
    MONTHLY_RENT = "monthly_rent"       # 월세
    JEONSE = "jeonse"                   # 전세
    OWNED = "owned"                     # 자가
    RENT_FREE = "rent_free"             # 무상임대


class TaxDeductionType(str, Enum):
    """세액공제/소득공제 유형"""
    CREDIT_CARD = "credit_card"                 # 신용카드 소득공제
    DEBIT_CARD = "debit_card"                   # 체크카드 소득공제
    MONTHLY_RENT = "monthly_rent"               # 월세 세액공제
    HOUSING_LOAN = "housing_loan"               # 주택임차차입금 원리금 상환액 공제
    YOUTH_SAVINGS = "youth_savings"             # 청년도약계좌
    HOUSING_SUBSCRIPTION = "housing_subscription"  # 주택청약저축


@dataclass
class Transaction:
    """개별 거래 내역"""
    date: date
    amount: int
    transaction_type: TransactionType
    category: ExpenseCategory
    payment_method: Optional[PaymentMethod] = None
    description: str = ""
    memo: str = ""
    id: str = ""

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "amount": self.amount,
            "transaction_type": self.transaction_type.value,
            "category": self.category.value,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "description": self.description,
            "memo": self.memo,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(
            date=date.fromisoformat(data["date"]),
            amount=data["amount"],
            transaction_type=TransactionType(data["transaction_type"]),
            category=ExpenseCategory(data["category"]),
            payment_method=PaymentMethod(data["payment_method"]) if data.get("payment_method") else None,
            description=data.get("description", ""),
            memo=data.get("memo", ""),
            id=data.get("id", ""),
        )


@dataclass
class UserInfo:
    """사용자 기본 정보"""
    name: str
    age: int
    job: str
    salary: int  # 연봉 (원)
    household: str  # 가구 형태

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserInfo":
        return cls(**data)


@dataclass
class Housing:
    """주거 정보"""
    housing_type: HousingType
    deposit: int = 0            # 보증금
    monthly_rent: int = 0       # 월세
    maintenance_fee: int = 0    # 관리비
    loan_amount: int = 0        # 전세대출금
    loan_interest_rate: float = 0.0  # 대출 이자율
    move_in_date: Optional[date] = None
    planned_move_date: Optional[date] = None
    memo: str = ""

    def to_dict(self) -> dict:
        return {
            "housing_type": self.housing_type.value,
            "deposit": self.deposit,
            "monthly_rent": self.monthly_rent,
            "maintenance_fee": self.maintenance_fee,
            "loan_amount": self.loan_amount,
            "loan_interest_rate": self.loan_interest_rate,
            "move_in_date": self.move_in_date.isoformat() if self.move_in_date else None,
            "planned_move_date": self.planned_move_date.isoformat() if self.planned_move_date else None,
            "memo": self.memo,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Housing":
        return cls(
            housing_type=HousingType(data["housing_type"]),
            deposit=data.get("deposit", 0),
            monthly_rent=data.get("monthly_rent", 0),
            maintenance_fee=data.get("maintenance_fee", 0),
            loan_amount=data.get("loan_amount", 0),
            loan_interest_rate=data.get("loan_interest_rate", 0.0),
            move_in_date=date.fromisoformat(data["move_in_date"]) if data.get("move_in_date") else None,
            planned_move_date=date.fromisoformat(data["planned_move_date"]) if data.get("planned_move_date") else None,
            memo=data.get("memo", ""),
        )


@dataclass
class SavingsAccount:
    """저축 계좌"""
    name: str
    monthly_amount: int
    total_balance: int = 0
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    interest_rate: float = 0.0
    is_tax_deductible: bool = False
    deduction_type: Optional[TaxDeductionType] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "monthly_amount": self.monthly_amount,
            "total_balance": self.total_balance,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "interest_rate": self.interest_rate,
            "is_tax_deductible": self.is_tax_deductible,
            "deduction_type": self.deduction_type.value if self.deduction_type else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavingsAccount":
        return cls(
            name=data["name"],
            monthly_amount=data["monthly_amount"],
            total_balance=data.get("total_balance", 0),
            start_date=date.fromisoformat(data["start_date"]) if data.get("start_date") else None,
            end_date=date.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            interest_rate=data.get("interest_rate", 0.0),
            is_tax_deductible=data.get("is_tax_deductible", False),
            deduction_type=TaxDeductionType(data["deduction_type"]) if data.get("deduction_type") else None,
        )


@dataclass
class Loan:
    """대출 정보"""
    name: str
    principal: int              # 원금
    remaining_balance: int      # 잔액
    interest_rate: float        # 이자율
    monthly_payment: int        # 월 상환액
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_tax_deductible: bool = False
    deduction_type: Optional[TaxDeductionType] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "principal": self.principal,
            "remaining_balance": self.remaining_balance,
            "interest_rate": self.interest_rate,
            "monthly_payment": self.monthly_payment,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_tax_deductible": self.is_tax_deductible,
            "deduction_type": self.deduction_type.value if self.deduction_type else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Loan":
        return cls(
            name=data["name"],
            principal=data["principal"],
            remaining_balance=data["remaining_balance"],
            interest_rate=data["interest_rate"],
            monthly_payment=data["monthly_payment"],
            start_date=date.fromisoformat(data["start_date"]) if data.get("start_date") else None,
            end_date=date.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            is_tax_deductible=data.get("is_tax_deductible", False),
            deduction_type=TaxDeductionType(data["deduction_type"]) if data.get("deduction_type") else None,
        )


@dataclass
class YTDMetrics:
    """연간 누적 지표 (Year-To-Date)"""
    year: int
    credit_card_usage: int = 0      # 신용카드 사용액
    debit_card_usage: int = 0       # 체크카드 사용액
    total_income: int = 0           # 총 수입
    total_expense: int = 0          # 총 지출
    total_savings: int = 0          # 총 저축
    monthly_rent_paid: int = 0      # 월세 납부액
    loan_principal_paid: int = 0    # 대출 원금 상환액
    loan_interest_paid: int = 0     # 대출 이자 상환액

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "YTDMetrics":
        return cls(**data)


@dataclass
class TaxStrategy:
    """세금 전략"""
    focus_items: list[str] = field(default_factory=list)
    credit_card_limit: int = 3_000_000      # 신용카드 공제 한도
    credit_card_deduction_rate: float = 0.15
    debit_card_deduction_rate: float = 0.30
    monthly_rent_deduction_limit: int = 9_000_000  # 월세 세액공제 한도
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TaxStrategy":
        return cls(**data)


@dataclass
class FinancialDashboard:
    """재무 대시보드 - 전체 상태"""
    current_date: date
    user_info: UserInfo
    housing: Housing
    savings_accounts: list[SavingsAccount] = field(default_factory=list)
    loans: list[Loan] = field(default_factory=list)
    ytd_metrics: Optional[YTDMetrics] = None
    tax_strategy: Optional[TaxStrategy] = None
    recent_transactions: list[Transaction] = field(default_factory=list)
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "current_date": self.current_date.isoformat(),
            "user_info": self.user_info.to_dict(),
            "housing": self.housing.to_dict(),
            "savings_accounts": [s.to_dict() for s in self.savings_accounts],
            "loans": [l.to_dict() for l in self.loans],
            "ytd_metrics": self.ytd_metrics.to_dict() if self.ytd_metrics else None,
            "tax_strategy": self.tax_strategy.to_dict() if self.tax_strategy else None,
            "recent_transactions": [t.to_dict() for t in self.recent_transactions[-20:]],  # 최근 20건만
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FinancialDashboard":
        return cls(
            current_date=date.fromisoformat(data["current_date"]),
            user_info=UserInfo.from_dict(data["user_info"]),
            housing=Housing.from_dict(data["housing"]),
            savings_accounts=[SavingsAccount.from_dict(s) for s in data.get("savings_accounts", [])],
            loans=[Loan.from_dict(l) for l in data.get("loans", [])],
            ytd_metrics=YTDMetrics.from_dict(data["ytd_metrics"]) if data.get("ytd_metrics") else None,
            tax_strategy=TaxStrategy.from_dict(data["tax_strategy"]) if data.get("tax_strategy") else None,
            recent_transactions=[Transaction.from_dict(t) for t in data.get("recent_transactions", [])],
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "FinancialDashboard":
        return cls.from_dict(json.loads(json_str))

    def get_total_monthly_fixed_expense(self) -> int:
        """월 고정 지출 계산"""
        total = 0
        # 주거비
        total += self.housing.monthly_rent + self.housing.maintenance_fee
        # 저축
        for savings in self.savings_accounts:
            total += savings.monthly_amount
        # 대출 상환
        for loan in self.loans:
            total += loan.monthly_payment
        return total

    def get_credit_card_deduction_status(self) -> dict:
        """신용카드 공제 상태 확인"""
        if not self.ytd_metrics:
            return {"usage": 0, "limit_reached": False, "remaining": 0}

        salary = self.user_info.salary
        minimum_usage = int(salary * 0.25)  # 총급여 25% 초과분부터 공제
        usage = self.ytd_metrics.credit_card_usage
        limit = self.tax_strategy.credit_card_limit if self.tax_strategy else 3_000_000

        excess_usage = max(0, usage - minimum_usage)
        deductible = min(excess_usage * 0.15, limit)

        return {
            "total_usage": usage,
            "minimum_threshold": minimum_usage,
            "excess_usage": excess_usage,
            "deductible_amount": int(deductible),
            "limit": limit,
            "limit_reached": deductible >= limit,
            "remaining_to_limit": max(0, limit - int(deductible)),
        }


def load_profile_from_file(profile_path: str) -> Optional[dict]:
    """프로필 파일에서 설정 로드"""
    from pathlib import Path
    path = Path(profile_path)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def create_default_dashboard(data_dir: str = "data/finance") -> FinancialDashboard:
    """초기 대시보드 생성 (프로필 파일에서 로드, 없으면 빈 기본값)"""
    from pathlib import Path
    today = date.today()

    # 프로필 파일에서 로드 시도
    profile_path = Path(data_dir) / "profile.json"
    profile = load_profile_from_file(str(profile_path))

    if profile:
        # 프로필 파일에서 로드
        user_data = profile.get("user_info", {})
        user_info = UserInfo(
            name=user_data.get("name", "사용자"),
            age=user_data.get("age", 30),
            job=user_data.get("job", "직장인"),
            salary=user_data.get("salary", 50_000_000),
            household=user_data.get("household", "1인 가구"),
        )

        housing_data = profile.get("housing", {})
        planned_move = None
        if housing_data.get("planned_move_date"):
            try:
                planned_move = date.fromisoformat(housing_data["planned_move_date"])
            except:
                pass

        housing = Housing(
            housing_type=HousingType(housing_data.get("housing_type", "monthly_rent")),
            deposit=housing_data.get("deposit", 0),
            monthly_rent=housing_data.get("monthly_rent", 0),
            maintenance_fee=housing_data.get("maintenance_fee", 0),
            loan_amount=housing_data.get("loan_amount", 0),
            loan_interest_rate=housing_data.get("loan_interest_rate", 0.0),
            planned_move_date=planned_move,
            memo=housing_data.get("memo", ""),
        )

        savings_accounts = []
        for s in profile.get("savings_accounts", []):
            deduction_type = None
            if s.get("deduction_type"):
                try:
                    deduction_type = TaxDeductionType(s["deduction_type"])
                except:
                    pass
            savings_accounts.append(SavingsAccount(
                name=s.get("name", "저축"),
                monthly_amount=s.get("monthly_amount", 0),
                is_tax_deductible=s.get("is_tax_deductible", False),
                deduction_type=deduction_type,
            ))

        ytd_data = profile.get("ytd_metrics", {})
        ytd_metrics = YTDMetrics(
            year=ytd_data.get("year", today.year),
            credit_card_usage=ytd_data.get("credit_card_usage", 0),
            debit_card_usage=ytd_data.get("debit_card_usage", 0),
        )

        tax_data = profile.get("tax_strategy", {})
        tax_strategy = TaxStrategy(
            focus_items=tax_data.get("focus_items", []),
            notes=tax_data.get("notes", ""),
        )
    else:
        # 프로필 파일이 없으면 빈 기본값
        user_info = UserInfo(
            name="사용자",
            age=30,
            job="직장인",
            salary=50_000_000,
            household="1인 가구",
        )

        housing = Housing(
            housing_type=HousingType.MONTHLY_RENT,
            deposit=0,
            monthly_rent=0,
            maintenance_fee=0,
        )

        savings_accounts = []

        ytd_metrics = YTDMetrics(year=today.year)

        tax_strategy = TaxStrategy(
            focus_items=[],
            notes="프로필 파일(data/finance/profile.json)을 설정해주세요.",
        )

    return FinancialDashboard(
        current_date=today,
        user_info=user_info,
        housing=housing,
        savings_accounts=savings_accounts,
        loans=[],
        ytd_metrics=ytd_metrics,
        tax_strategy=tax_strategy,
        updated_at=datetime.now(),
    )
