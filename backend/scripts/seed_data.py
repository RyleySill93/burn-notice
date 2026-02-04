#!/usr/bin/env python3
"""Seed the database with realistic-looking data for design review."""

import random
import secrets
from datetime import date, datetime, timedelta

from src.app.engineers.domains import EngineerCreate
from src.app.engineers.models import Engineer
from src.app.usage.domains import UsageCreate, UsageDailyCreate
from src.app.usage.models import Usage, UsageDaily
from src.common import context
from src.core.customer.domains import CustomerCreate
from src.core.customer.models import Customer
from src.core.membership.domains import MembershipCreate
from src.core.membership.models import Membership
from src.core.user.domains import UserCreate
from src.core.user.models import User
from src.network.database.session import SessionManager

# Sample engineer data
ENGINEERS = [
    {'name': 'Alex Chen', 'email': 'alex.chen@example.com'},
    {'name': 'Sarah Johnson', 'email': 'sarah.johnson@example.com'},
    {'name': 'Marcus Williams', 'email': 'marcus.williams@example.com'},
    {'name': 'Emily Rodriguez', 'email': 'emily.rodriguez@example.com'},
    {'name': 'David Kim', 'email': 'david.kim@example.com'},
    {'name': 'Jessica Taylor', 'email': 'jessica.taylor@example.com'},
    {'name': 'Michael Brown', 'email': 'michael.brown@example.com'},
    {'name': 'Amanda Garcia', 'email': 'amanda.garcia@example.com'},
    {'name': 'Chris Martinez', 'email': 'chris.martinez@example.com'},
    {'name': 'Nicole Anderson', 'email': 'nicole.anderson@example.com'},
    {'name': 'Ryan Thomas', 'email': 'ryan.thomas@example.com'},
    {'name': 'Lauren Davis', 'email': 'lauren.davis@example.com'},
]

MODELS = [
    'claude-sonnet-4-20250514',
    'claude-opus-4-5-20251101',
    'claude-3-5-haiku-20241022',
]


def generate_api_key() -> str:
    """Generate a unique API key."""
    return f'bn_{secrets.token_urlsafe(30)}'


def seed_data():
    """Seed the database with sample data."""
    # Set up application context for database audit
    context.initialize(
        user_type=context.AppContextUserType.SYSTEM,
        request_id='seed-script',
    )

    with SessionManager(commit_on_success=True):
        from src.network.database import db

        _run_seed(db)


def _run_seed(db):
    """Actual seed logic with db context."""
    print('Seeding database with sample data...')

    # Get or create customer
    customer = Customer.get_or_none(name='lumonic')
    if not customer:
        customer = Customer.create(CustomerCreate(name='lumonic'))
        print(f'Created customer: {customer.name}')
    else:
        print(f'Using existing customer: {customer.name}')

    # Create users, memberships, and engineers
    engineers_created = []
    for eng_data in ENGINEERS:
        first_name, last_name = eng_data['name'].split(' ', 1)
        email = eng_data['email']

        # Check if user already exists
        user = User.get_or_none(email=email)
        if not user:
            user = User.create(
                UserCreate(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    is_active=True,
                )
            )
            print(f'Created user: {user.email}')

        # Check if membership exists
        membership = Membership.get_or_none(customer_id=customer.id, user_id=user.id)
        if not membership:
            membership = Membership.create(
                MembershipCreate(
                    customer_id=customer.id,
                    user_id=user.id,
                    is_active=True,
                    api_key=generate_api_key(),
                )
            )
            print(f'Created membership for: {user.email}')

        # Check if engineer exists
        external_id = f'user_{user.id}'
        engineer = Engineer.get_or_none(customer_id=customer.id, external_id=external_id)
        if not engineer:
            engineer = Engineer.create(
                EngineerCreate(
                    customer_id=customer.id,
                    external_id=external_id,
                    display_name=eng_data['name'],
                )
            )
            print(f'Created engineer: {engineer.display_name}')

        engineers_created.append(engineer)

    # Generate usage data for the past 30 days
    today = date.today()

    # Clear existing usage data to avoid duplicates
    print('Clearing existing usage data...')
    db.session.query(Usage).delete()
    db.session.query(UsageDaily).delete()
    db.session.commit()

    print('Generating usage data for the past 30 days...')

    # Assign base activity levels to engineers (some are more active than others)
    engineer_activity = {}
    for eng in engineers_created:
        # Random base activity level: high (3), medium (2), low (1)
        engineer_activity[eng.id] = random.choice([1, 1, 2, 2, 2, 3, 3])

    for days_ago in range(30, -1, -1):  # 30 days ago to today
        current_date = today - timedelta(days=days_ago)
        is_weekend = current_date.weekday() >= 5

        for engineer in engineers_created:
            activity_level = engineer_activity[engineer.id]

            # Skip some days randomly (more likely to skip on weekends)
            if is_weekend and random.random() < 0.6:
                continue
            if random.random() < 0.15:  # 15% chance of no activity on any day
                continue

            # Number of sessions for this day (based on activity level)
            num_sessions = random.randint(1, activity_level * 3)

            daily_tokens = 0
            daily_input = 0
            daily_output = 0
            session_ids = set()

            for _ in range(num_sessions):
                session_id = f'session_{secrets.token_hex(8)}'
                session_ids.add(session_id)

                # Number of API calls in this session
                num_calls = random.randint(5, 50) * activity_level

                for call_idx in range(num_calls):
                    # Token amounts vary by model and call type
                    model = random.choices(
                        MODELS,
                        weights=[0.6, 0.25, 0.15],  # Sonnet most common
                    )[0]

                    # Input tokens: typically 500-5000
                    tokens_input = random.randint(200, 8000)
                    # Output tokens: typically 100-2000
                    tokens_output = random.randint(50, 3000)

                    # Create timestamp within the day
                    hour = random.randint(8, 22)  # 8am to 10pm
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)

                    created_at = datetime.combine(
                        current_date, datetime.min.time().replace(hour=hour, minute=minute, second=second)
                    )

                    usage = Usage.create(
                        UsageCreate(
                            engineer_id=engineer.id,
                            tokens_input=tokens_input,
                            tokens_output=tokens_output,
                            model=model,
                            session_id=session_id,
                        )
                    )
                    # Update created_at manually since it defaults to now()
                    db.session.execute(
                        Usage.__table__.update().where(Usage.__table__.c.id == usage.id).values(created_at=created_at)
                    )

                    daily_tokens += tokens_input + tokens_output
                    daily_input += tokens_input
                    daily_output += tokens_output

            # Create daily rollup (skip today, it comes from live data)
            if days_ago > 0 and daily_tokens > 0:
                UsageDaily.create(
                    UsageDailyCreate(
                        engineer_id=engineer.id,
                        date=current_date,
                        total_tokens=daily_tokens,
                        tokens_input=daily_input,
                        tokens_output=daily_output,
                        session_count=len(session_ids),
                    )
                )

        if days_ago % 5 == 0:
            print(f'  Generated data for {current_date}')
            db.session.commit()

    db.session.commit()
    print('Done! Database seeded successfully.')

    # Print summary stats
    total_usage = db.session.query(Usage).count()
    total_daily = db.session.query(UsageDaily).count()
    total_engineers = db.session.query(Engineer).filter(Engineer.customer_id == customer.id).count()

    print('\nSummary:')
    print(f'  Engineers: {total_engineers}')
    print(f'  Usage records: {total_usage}')
    print(f'  Daily rollups: {total_daily}')


if __name__ == '__main__':
    seed_data()
