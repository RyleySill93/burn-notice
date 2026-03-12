from datetime import date, timedelta

from loguru import logger
from sqlalchemy import func

from src.app.engineers.models import Engineer
from src.app.leaderboard.service import LeaderboardService, get_day_bounds_utc
from src.app.records.domains import RecordCreate, RecordRead
from src.app.records.enums import RecordPeriod, RecordScope, RecordType
from src.app.records.models import Record
from src.app.usage.models import UsageDaily
from src.network.database import db


class RecordService:
    @staticmethod
    def get_current_record(
        engineer_id: str | None,
        customer_id: str,
        record_type: str,
        record_period: str,
        record_scope: str,
    ) -> RecordRead | None:
        """Get the current record (highest value) for a given type/period/scope."""
        query = db.session.query(Record).filter(
            Record.customer_id == customer_id,
            Record.record_type == record_type,
            Record.record_period == record_period,
            Record.record_scope == record_scope,
        )
        if record_scope == RecordScope.PERSONAL and engineer_id:
            query = query.filter(Record.engineer_id == engineer_id)

        result = query.order_by(Record.value.desc()).first()
        return Record._to_domain(result) if result else None

    @staticmethod
    def get_records_for_customer(customer_id: str) -> list[RecordRead]:
        """Get all records for a customer."""
        records = db.session.query(Record).filter(Record.customer_id == customer_id).all()
        return [Record._to_domain(r) for r in records]

    @staticmethod
    def check_and_store_record(
        engineer_id: str,
        customer_id: str,
        record_type: str,
        record_period: str,
        value: float,
        record_date: date,
    ) -> RecordRead | None:
        """Check if a value beats the current record and store it if so. Returns the new record or None."""
        if value <= 0:
            return None

        # Check personal record
        personal_record = RecordService._check_record(
            engineer_id=engineer_id,
            customer_id=customer_id,
            record_type=record_type,
            record_period=record_period,
            record_scope=RecordScope.PERSONAL,
            value=value,
            record_date=record_date,
        )

        # Check company record
        company_record = RecordService._check_record(
            engineer_id=engineer_id,
            customer_id=customer_id,
            record_type=record_type,
            record_period=record_period,
            record_scope=RecordScope.COMPANY,
            value=value,
            record_date=record_date,
        )

        db.session.commit()

        # Return company record if set (more significant), else personal
        return company_record or personal_record

    @staticmethod
    def _check_record(
        engineer_id: str,
        customer_id: str,
        record_type: str,
        record_period: str,
        record_scope: str,
        value: float,
        record_date: date,
    ) -> RecordRead | None:
        """Check and store a single record if it beats the current one."""
        if record_scope == RecordScope.PERSONAL:
            current = (
                db.session.query(Record)
                .filter(
                    Record.engineer_id == engineer_id,
                    Record.customer_id == customer_id,
                    Record.record_type == record_type,
                    Record.record_period == record_period,
                    Record.record_scope == RecordScope.PERSONAL,
                )
                .order_by(Record.value.desc())
                .first()
            )
        else:
            current = (
                db.session.query(Record)
                .filter(
                    Record.customer_id == customer_id,
                    Record.record_type == record_type,
                    Record.record_period == record_period,
                    Record.record_scope == RecordScope.COMPANY,
                )
                .order_by(Record.value.desc())
                .first()
            )

        current_value = current.value if current else 0

        if value > current_value:
            record = Record.create(
                RecordCreate(
                    engineer_id=engineer_id,
                    customer_id=customer_id,
                    record_type=record_type,
                    record_period=record_period,
                    record_scope=record_scope,
                    value=value,
                    previous_value=current_value if current_value > 0 else None,
                    record_date=record_date,
                )
            )
            logger.info(
                'New record set',
                engineer_id=engineer_id,
                record_type=record_type,
                record_period=record_period,
                record_scope=record_scope,
                value=value,
                previous_value=current_value,
            )
            return record

        return None

    @staticmethod
    def process_records_for_date(customer_id: str, for_date: date) -> list[RecordRead]:
        """Process all record types for a given date. Called by scheduler after daily rollup."""
        new_records: list[RecordRead] = []
        engineers = db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()

        for engineer in engineers:
            # Daily tokens
            daily_tokens = RecordService._get_engineer_daily_tokens(engineer.id, for_date)
            result = RecordService.check_and_store_record(
                engineer_id=engineer.id,
                customer_id=customer_id,
                record_type=RecordType.TOKENS,
                record_period=RecordPeriod.DAILY,
                value=daily_tokens,
                record_date=for_date,
            )
            if result:
                new_records.append(result)

            # Daily time
            daily_time = RecordService._get_engineer_daily_time(engineer.id, for_date)
            result = RecordService.check_and_store_record(
                engineer_id=engineer.id,
                customer_id=customer_id,
                record_type=RecordType.TIME,
                record_period=RecordPeriod.DAILY,
                value=daily_time,
                record_date=for_date,
            )
            if result:
                new_records.append(result)

        # Check weekly records on Sundays (end of week)
        if for_date.weekday() == 6:  # Sunday
            week_start = for_date - timedelta(days=6)
            for engineer in engineers:
                weekly_tokens = RecordService._get_engineer_range_tokens(engineer.id, week_start, for_date)
                result = RecordService.check_and_store_record(
                    engineer_id=engineer.id,
                    customer_id=customer_id,
                    record_type=RecordType.TOKENS,
                    record_period=RecordPeriod.WEEKLY,
                    value=weekly_tokens,
                    record_date=for_date,
                )
                if result:
                    new_records.append(result)

                weekly_time = RecordService._get_engineer_range_time(engineer.id, week_start, for_date)
                result = RecordService.check_and_store_record(
                    engineer_id=engineer.id,
                    customer_id=customer_id,
                    record_type=RecordType.TIME,
                    record_period=RecordPeriod.WEEKLY,
                    value=weekly_time,
                    record_date=for_date,
                )
                if result:
                    new_records.append(result)

        # Check monthly records on last day of month
        next_day = for_date + timedelta(days=1)
        if next_day.month != for_date.month:
            month_start = for_date.replace(day=1)
            for engineer in engineers:
                monthly_tokens = RecordService._get_engineer_range_tokens(engineer.id, month_start, for_date)
                result = RecordService.check_and_store_record(
                    engineer_id=engineer.id,
                    customer_id=customer_id,
                    record_type=RecordType.TOKENS,
                    record_period=RecordPeriod.MONTHLY,
                    value=monthly_tokens,
                    record_date=for_date,
                )
                if result:
                    new_records.append(result)

                monthly_time = RecordService._get_engineer_range_time(engineer.id, month_start, for_date)
                result = RecordService.check_and_store_record(
                    engineer_id=engineer.id,
                    customer_id=customer_id,
                    record_type=RecordType.TIME,
                    record_period=RecordPeriod.MONTHLY,
                    value=monthly_time,
                    record_date=for_date,
                )
                if result:
                    new_records.append(result)

        logger.info(
            'Records processed',
            customer_id=customer_id,
            for_date=str(for_date),
            new_records_count=len(new_records),
        )
        return new_records

    @staticmethod
    def _get_engineer_daily_tokens(engineer_id: str, for_date: date) -> float:
        """Get total tokens for an engineer on a specific date."""
        result = (
            db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
            .filter(
                UsageDaily.engineer_id == engineer_id,
                UsageDaily.date == for_date,
            )
            .scalar()
        )
        return float(result or 0)

    @staticmethod
    def _get_engineer_daily_time(engineer_id: str, for_date: date) -> float:
        """Get active minutes for an engineer on a specific date."""
        start_utc, end_utc = get_day_bounds_utc(for_date)
        return float(LeaderboardService._calculate_active_minutes(engineer_id, start_utc, end_utc))

    @staticmethod
    def _get_engineer_range_tokens(engineer_id: str, start_date: date, end_date: date) -> float:
        """Get total tokens for an engineer in a date range."""
        result = (
            db.session.query(func.coalesce(func.sum(UsageDaily.total_tokens), 0))
            .filter(
                UsageDaily.engineer_id == engineer_id,
                UsageDaily.date >= start_date,
                UsageDaily.date <= end_date,
            )
            .scalar()
        )
        return float(result or 0)

    @staticmethod
    def _get_engineer_range_time(engineer_id: str, start_date: date, end_date: date) -> float:
        """Get active minutes for an engineer in a date range."""
        start_utc, _ = get_day_bounds_utc(start_date)
        _, end_utc = get_day_bounds_utc(end_date)
        return float(LeaderboardService._calculate_active_minutes(engineer_id, start_utc, end_utc))

    @staticmethod
    def backfill_records(customer_id: str) -> dict:
        """Backfill records from historical UsageDaily data."""
        engineers = db.session.query(Engineer).filter(Engineer.customer_id == customer_id).all()

        # Find date range from UsageDaily
        min_date = (
            db.session.query(func.min(UsageDaily.date))
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(Engineer.customer_id == customer_id)
            .scalar()
        )
        max_date = (
            db.session.query(func.max(UsageDaily.date))
            .join(Engineer, UsageDaily.engineer_id == Engineer.id)
            .filter(Engineer.customer_id == customer_id)
            .scalar()
        )

        if not min_date or not max_date:
            return {'days_processed': 0, 'records_created': 0}

        records_created = 0
        current = min_date

        while current <= max_date:
            for engineer in engineers:
                # Daily tokens
                daily_tokens = RecordService._get_engineer_daily_tokens(engineer.id, current)
                if daily_tokens > 0:
                    result = RecordService._check_record(
                        engineer_id=engineer.id,
                        customer_id=customer_id,
                        record_type=RecordType.TOKENS,
                        record_period=RecordPeriod.DAILY,
                        record_scope=RecordScope.PERSONAL,
                        value=daily_tokens,
                        record_date=current,
                    )
                    if result:
                        records_created += 1
                    result = RecordService._check_record(
                        engineer_id=engineer.id,
                        customer_id=customer_id,
                        record_type=RecordType.TOKENS,
                        record_period=RecordPeriod.DAILY,
                        record_scope=RecordScope.COMPANY,
                        value=daily_tokens,
                        record_date=current,
                    )
                    if result:
                        records_created += 1

                # Daily time
                daily_time = RecordService._get_engineer_daily_time(engineer.id, current)
                if daily_time > 0:
                    result = RecordService._check_record(
                        engineer_id=engineer.id,
                        customer_id=customer_id,
                        record_type=RecordType.TIME,
                        record_period=RecordPeriod.DAILY,
                        record_scope=RecordScope.PERSONAL,
                        value=daily_time,
                        record_date=current,
                    )
                    if result:
                        records_created += 1
                    result = RecordService._check_record(
                        engineer_id=engineer.id,
                        customer_id=customer_id,
                        record_type=RecordType.TIME,
                        record_period=RecordPeriod.DAILY,
                        record_scope=RecordScope.COMPANY,
                        value=daily_time,
                        record_date=current,
                    )
                    if result:
                        records_created += 1

            # Weekly records on Sundays
            if current.weekday() == 6:
                week_start = current - timedelta(days=6)
                for engineer in engineers:
                    weekly_tokens = RecordService._get_engineer_range_tokens(engineer.id, week_start, current)
                    if weekly_tokens > 0:
                        result = RecordService._check_record(
                            engineer_id=engineer.id,
                            customer_id=customer_id,
                            record_type=RecordType.TOKENS,
                            record_period=RecordPeriod.WEEKLY,
                            record_scope=RecordScope.PERSONAL,
                            value=weekly_tokens,
                            record_date=current,
                        )
                        if result:
                            records_created += 1
                        result = RecordService._check_record(
                            engineer_id=engineer.id,
                            customer_id=customer_id,
                            record_type=RecordType.TOKENS,
                            record_period=RecordPeriod.WEEKLY,
                            record_scope=RecordScope.COMPANY,
                            value=weekly_tokens,
                            record_date=current,
                        )
                        if result:
                            records_created += 1

                    weekly_time = RecordService._get_engineer_range_time(engineer.id, week_start, current)
                    if weekly_time > 0:
                        result = RecordService._check_record(
                            engineer_id=engineer.id,
                            customer_id=customer_id,
                            record_type=RecordType.TIME,
                            record_period=RecordPeriod.WEEKLY,
                            record_scope=RecordScope.PERSONAL,
                            value=weekly_time,
                            record_date=current,
                        )
                        if result:
                            records_created += 1
                        result = RecordService._check_record(
                            engineer_id=engineer.id,
                            customer_id=customer_id,
                            record_type=RecordType.TIME,
                            record_period=RecordPeriod.WEEKLY,
                            record_scope=RecordScope.COMPANY,
                            value=weekly_time,
                            record_date=current,
                        )
                        if result:
                            records_created += 1

            # Monthly records on last day of month
            next_day = current + timedelta(days=1)
            if next_day.month != current.month:
                month_start = current.replace(day=1)
                for engineer in engineers:
                    monthly_tokens = RecordService._get_engineer_range_tokens(engineer.id, month_start, current)
                    if monthly_tokens > 0:
                        result = RecordService._check_record(
                            engineer_id=engineer.id,
                            customer_id=customer_id,
                            record_type=RecordType.TOKENS,
                            record_period=RecordPeriod.MONTHLY,
                            record_scope=RecordScope.PERSONAL,
                            value=monthly_tokens,
                            record_date=current,
                        )
                        if result:
                            records_created += 1
                        result = RecordService._check_record(
                            engineer_id=engineer.id,
                            customer_id=customer_id,
                            record_type=RecordType.TOKENS,
                            record_period=RecordPeriod.MONTHLY,
                            record_scope=RecordScope.COMPANY,
                            value=monthly_tokens,
                            record_date=current,
                        )
                        if result:
                            records_created += 1

                    monthly_time = RecordService._get_engineer_range_time(engineer.id, month_start, current)
                    if monthly_time > 0:
                        result = RecordService._check_record(
                            engineer_id=engineer.id,
                            customer_id=customer_id,
                            record_type=RecordType.TIME,
                            record_period=RecordPeriod.MONTHLY,
                            record_scope=RecordScope.PERSONAL,
                            value=monthly_time,
                            record_date=current,
                        )
                        if result:
                            records_created += 1
                        result = RecordService._check_record(
                            engineer_id=engineer.id,
                            customer_id=customer_id,
                            record_type=RecordType.TIME,
                            record_period=RecordPeriod.MONTHLY,
                            record_scope=RecordScope.COMPANY,
                            value=monthly_time,
                            record_date=current,
                        )
                        if result:
                            records_created += 1

            db.session.commit()
            current += timedelta(days=1)

        days_processed = (max_date - min_date).days + 1
        logger.info(
            'Backfill complete',
            customer_id=customer_id,
            days_processed=days_processed,
            records_created=records_created,
        )
        return {'days_processed': days_processed, 'records_created': records_created}
