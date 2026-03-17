"""initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-17 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('''
    CREATE TABLE clients (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        phone       VARCHAR(20) UNIQUE NOT NULL,
        name        VARCHAR(100),
        monthly_income  NUMERIC(12,2) NOT NULL DEFAULT 0,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    ''')

    op.execute('''
    CREATE TABLE spending_categories (
        id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name    VARCHAR(60) UNIQUE NOT NULL
    );
    ''')

    op.execute('''
    CREATE TABLE monthly_goals (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        category_id     UUID NOT NULL REFERENCES spending_categories(id),
        year_month      DATE NOT NULL,
        limit_amount    NUMERIC(12,2) NOT NULL,
        alert_80_sent   BOOLEAN NOT NULL DEFAULT false,
        alert_100_sent  BOOLEAN NOT NULL DEFAULT false,
        UNIQUE(client_id, category_id, year_month)
    );
    ''')
    
    op.execute('''
    CREATE TABLE spendings (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        category_id     UUID NOT NULL REFERENCES spending_categories(id),
        amount          NUMERIC(12,2) NOT NULL,
        description     VARCHAR(200),
        spent_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    ''')
    
    op.execute('''
    CREATE TABLE goals (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        title           VARCHAR(100) NOT NULL,
        target_amount   NUMERIC(12,2) NOT NULL,
        current_amount  NUMERIC(12,2) NOT NULL DEFAULT 0,
        deadline        DATE,
        status          VARCHAR(20) NOT NULL DEFAULT 'active',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    ''')

    op.execute('''
    CREATE TABLE contributions (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        goal_id     UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
        amount      NUMERIC(12,2) NOT NULL,
        note        VARCHAR(200),
        contributed_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    ''')


def downgrade() -> None:
    op.execute('DROP TABLE contributions;')
    op.execute('DROP TABLE goals;')
    op.execute('DROP TABLE spendings;')
    op.execute('DROP TABLE monthly_goals;')
    op.execute('DROP TABLE spending_categories;')
    op.execute('DROP TABLE clients;')
