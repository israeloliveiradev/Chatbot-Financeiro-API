import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean, Date, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

class Base(DeclarativeBase):
    pass

class ClientModel(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now())

    monthly_goals: Mapped[list["MonthlyGoalModel"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    spendings: Mapped[list["SpendingModel"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    goals: Mapped[list["GoalModel"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class SpendingCategoryModel(Base):
    __tablename__ = "spending_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)

    monthly_goals: Mapped[list["MonthlyGoalModel"]] = relationship(back_populates="category")
    spendings: Mapped[list["SpendingModel"]] = relationship(back_populates="category")


class MonthlyGoalModel(Base):
    __tablename__ = "monthly_goals"
    __table_args__ = (
        UniqueConstraint("client_id", "category_id", "year_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spending_categories.id"), nullable=False)
    year_month: Mapped[date] = mapped_column(Date, nullable=False)
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    alert_80_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    alert_100_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    client: Mapped["ClientModel"] = relationship(back_populates="monthly_goals")
    category: Mapped["SpendingCategoryModel"] = relationship(back_populates="monthly_goals")


class SpendingModel(Base):
    __tablename__ = "spendings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spending_categories.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    spent_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), server_default=func.now())

    client: Mapped["ClientModel"] = relationship(back_populates="spendings")
    category: Mapped["SpendingCategoryModel"] = relationship(back_populates="spendings")


class GoalModel(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), server_default=func.now(), onupdate=func.now())

    client: Mapped["ClientModel"] = relationship(back_populates="goals")
    contributions: Mapped[list["ContributionModel"]] = relationship(back_populates="goal", cascade="all, delete-orphan")


class ContributionModel(Base):
    __tablename__ = "contributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contributed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), server_default=func.now())

    goal: Mapped["GoalModel"] = relationship(back_populates="contributions")

