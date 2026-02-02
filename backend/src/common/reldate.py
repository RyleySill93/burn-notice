import datetime
import re
from typing import Annotated, Tuple

from dateutil.relativedelta import relativedelta
from pydantic import AfterValidator

from src.common.constants import DEFAULT_FISCAL_YEAR_END_MONTH, FQE_MONTHS_BY_FYE_MONTH, FYE_TO_SEMI_ANNUAL_MONTHS
from src.common.enum import BaseEnum
from src.common.exceptions import InternalException
from src.common.utils import get_first_date_of_month, get_last_date_of_month


class RelDateException(InternalException): ...


class MalformedAbsoluteRelDate(RelDateException): ...


class MalformedRelDate(RelDateException): ...


class RelDatePeriodEnum(BaseEnum):
    CALENDAR_WEEK = 'CW'
    CALENDAR_MONTH = 'CM'
    CALENDAR_QUARTER = 'CQ'
    CALENDAR_SEMI_ANNUAL = 'CH'
    CALENDAR_YEAR = 'CY'
    FISCAL_QUARTER = 'FQ'
    FISCAL_SEMI_ANNUAL = 'FH'
    FISCAL_YEAR = 'FY'


class RelDateModifierEnum(BaseEnum):
    # modifiy the output of the ldate to be start of the period type
    START_OF_PERIOD = '!'
    # modify the outout of the ldate to anchor at the current day so just move full period chunks like - 3m and keep day
    ANCHOR_IN_PERIOD = '@'


TargetRelDateType = str | datetime.date


class RelDate:
    """
    The RelDate parser is capable of parsing dates in both absolute and relative formats:
        1) The absolute format follows the ISO standard (YYYY-MM-DD),
        2) The relative format is a string indicating an offset from the current date.
           - Appending a '!' to a relative date string returns the beginning of the period instead of the end.
           - Appending a '@' to a relative date string serves as a reference anchor, indicating the same period type
             offset (e.g., '-1CM@' for the prior calendar month on the same day).

    Below is a table illustrating examples of relative date strings and their results, assuming a fiscal year end month of August (8):

    | Relative to 4/19/24 | Example   | Result                | Description                          |
    |----------------------|-----------|-----------------------|--------------------------------------|
    -MONTH------------------------------------------
    |                      | 0CM       | 2024-04-30            | End of the current month             |
    |                      | 0CM!      | 2024-04-01            | Start of the current month           |
    |                      | 0CM@      | 2024-04-19            | Same day in the current month        |
    |                      | -1CM      | 2024-03-31            | End of the last month                |
    |                      | -1CM!     | 2024-03-01            | Start of the last month              |
    |                      | -1CM@     | 2024-03-19            | Same day in the prior calendar month |
    |                      | 1CM       | 2024-05-31            | End of the next month                |
    |                      | 1CM!      | 2024-05-01            | Start of the next month              |
    |                      | 1CM@      | 2024-05-19            | Same day in the next calendar month  |
    -QUARTER----------------------------------------
    |                      | 0CQ       | 2024-06-30            | End of the current quarter           |
    |                      | 0CQ!      | 2024-04-01            | Start of the current quarter         |
    |                      | 0CQ@      | 2024-04-19            | Same day in the current quarter      |
    |                      | -1CQ      | 2024-03-31            | End of the last quarter              |
    |                      | -1CQ!     | 2024-01-01            | Start of the last quarter            |
    |                      | -1CQ@     | 2024-01-19            | Same day in the last quarter         |
    |                      | 1CQ       | 2024-09-30            | End of the next quarter              |
    |                      | 1CQ!      | 2024-07-01            | Start of the next quarter            |
    |                      | 1CQ@      | 2024-07-19            | Same day in the next quarter         |
    -FISCAL QUARTER (FYE: AUGUST)------------------
    |                      | 0FQ       | 2024-05-31            | End of the current fiscal quarter    |
    |                      | 0FQ!      | 2024-03-01            | Start of the current fiscal quarter  |
    |                      | 0FQ@      | 2024-04-19            | Same day in the current fiscal quarter |
    |                      | -1FQ      | 2024-02-29            | End of the last fiscal quarter       |
    |                      | -1FQ!     | 2023-12-01            | Start of the last fiscal quarter     |
    |                      | -1FQ@     | 2024-01-19            | Same day in the last fiscal quarter  |
    |                      | 1FQ       | 2024-08-31            | End of the next fiscal quarter       |
    |                      | 1FQ!      | 2024-06-01            | Start of the next fiscal quarter     |
    |                      | 1FQ@      | 2024-07-19            | Same day in the next fiscal quarter  |
    -YEAR-------------------------------------------
    |                      | 0CY       | 2024-12-31            | End of the current year              |
    |                      | 0CY!      | 2024-01-01            | Start of the current year            |
    |                      | 0CY@      | 2024-04-19            | Same day in the current year         |
    |                      | 0CY#      | 2024                  | Current year as an integer           |
    |                      | -1CY      | 2023-12-31            | End of the last year                 |
    |                      | -1CY!     | 2023-01-01            | Start of the last year               |
    |                      | -1CY@     | 2023-04-19            | Same day in the last year            |
    |                      | 1CY       | 2025-12-31            | End of the next year                 |
    |                      | 1CY!      | 2025-01-01            | Start of the next year               |
    |                      | 1CY@      | 2025-04-19            | Same day in the next year            |
    -FISCAL YEAR (FYE: AUGUST)---------------------
    |                      | 0FY       | 2024-08-31            | End of the current fiscal year       |
    |                      | 0FY!      | 2023-09-01            | Start of the current fiscal year     |
    |                      | 0FY@      | 2024-04-19            | Same day in the current fiscal year  |
    |                      | -1FY      | 2023-08-31            | End of the last fiscal year          |
    |                      | -1FY!     | 2022-09-01            | Start of the last fiscal year        |
    |                      | -1FY@     | 2023-04-19            | Same day in the last fiscal year     |
    |                      | 1FY       | 2025-08-31            | End of the next fiscal year          |
    |                      | 1FY!      | 2024-09-01            | Start of the next fiscal year        |
    |                      | 1FY@      | 2025-04-19            | Same day in the next fiscal year     |

    The examples use the date 4/19/24 as a reference point.
    The 'C' prefix refers to the end of the calendar period (month, quarter, year),
    while the lack of the 'C' prefix refers to the exact amount of time from the current date.
    Negative numbers indicate a time before the reference date,
    and positive numbers indicate a time after the reference date.
    now handles datetime passed.

    """

    def __init__(
        self,
        relative_to_date: datetime.date = None,
        fiscal_year_end_month: int | str | None = DEFAULT_FISCAL_YEAR_END_MONTH,
    ):
        # Configuration for parser
        self.relative_to_date: datetime.date = (
            relative_to_date.date()
            if isinstance(relative_to_date, datetime.datetime)
            else relative_to_date or datetime.date.today()
        )

        self.fiscal_year_end_month = int(fiscal_year_end_month)

    def __call__(self, target: TargetRelDateType):
        return self.parse(target)

    def validate(self, target: TargetRelDateType) -> str:
        if isinstance(target, datetime.date):
            return target.strftime('%Y-%m-%d')

        self.parse(target)
        return target

    def parse(self, target: TargetRelDateType) -> datetime.date:
        if isinstance(target, datetime.date):
            # Already parsed
            return target
        elif target.count('-') == 2:
            # Dumb but cheap / performant way to detect ISO date
            return self.parse_absolute_date(target)
        else:
            # Assume its a relative date
            return self.parse_relative_date(target)

    def parse_absolute_date(self, target_str: str):
        try:
            return datetime.datetime.strptime(target_str, '%Y-%m-%d').date()
        except ValueError:
            raise MalformedAbsoluteRelDate(f'Unable to parse {target_str}')

    def parse_relative_date(self, target_str: str):
        """
        Handles relative date parsing
        """
        number, period, modifier = self._split_number_period_and_modifier(target_str)
        if period == RelDatePeriodEnum.CALENDAR_WEEK.value:
            return self._parse_for_relative_calendar_week(weeks_offset=number, modifier=modifier)
        elif period == RelDatePeriodEnum.CALENDAR_MONTH.value:
            return self._parse_for_relative_calendar_month(months_offset=number, modifier=modifier)
        elif period == RelDatePeriodEnum.CALENDAR_QUARTER.value:
            return self._parse_for_relative_calendar_quarter(quarters_offset=number, modifier=modifier)
        elif period == RelDatePeriodEnum.CALENDAR_SEMI_ANNUAL.value:
            return self._parse_for_relative_calendar_semi_annual(semi_annual_offset=number, modifier=modifier)
        elif period == RelDatePeriodEnum.CALENDAR_YEAR.value:
            return self._parse_for_relative_calendar_year(years_offset=number, modifier=modifier)
        elif period == RelDatePeriodEnum.FISCAL_QUARTER.value:
            return self._parse_for_relative_fiscal_quarter(quarters_offset=number, modifier=modifier)
        elif period == RelDatePeriodEnum.FISCAL_SEMI_ANNUAL.value:
            return self._parse_for_relative_fiscal_semi_annual(semi_annual_offset=number, modifier=modifier)
        elif period == RelDatePeriodEnum.FISCAL_YEAR.value:
            return self._parse_for_relative_fiscal_year(years_offset=number, modifier=modifier)
        else:
            raise MalformedRelDate(f'Unsupported period type: {period}')

    @classmethod
    def _split_number_period_and_modifier(
        cls, target_str: str
    ) -> Tuple[int, RelDatePeriodEnum, RelDateModifierEnum | None]:
        """
        Parsing out the number, period, and modifier from target_str.

        Returns:
            Tuple[int, str, str | None]: (offset number, period, modifier)
        """
        # Identify the modifier if present
        modifier = None
        if target_str[-1] in RelDateModifierEnum._value2member_map_:
            modifier = target_str[-1]
            target_str = target_str[:-1]

        # Identify the period if present
        period = None
        for period_enum in RelDatePeriodEnum:
            if target_str.endswith(period_enum.value):
                period = period_enum.value
                target_str = target_str[: -len(period)]
                break

        if period is None:
            raise MalformedRelDate(f'Invalid period type in {target_str}')

        # The remaining part should be the number
        try:
            number = int(target_str)
        except ValueError:
            raise MalformedRelDate(f'Could not parse the number from {target_str}')

        return number, period, modifier

    def _parse_for_relative_calendar_week(
        self, weeks_offset: int, modifier: RelDateModifierEnum | None = None
    ) -> datetime.date:
        # Calculate the start of the current week (Monday)
        start_of_week = self.relative_to_date - datetime.timedelta(days=self.relative_to_date.weekday())

        # Adjust the date by the specified number of weeks
        adjusted_date = start_of_week + datetime.timedelta(weeks=weeks_offset)

        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            # Return Monday of the target week
            return adjusted_date
        elif modifier == RelDateModifierEnum.ANCHOR_IN_PERIOD.value:
            # Return the same weekday as the relative_to_date, but in the target week
            return adjusted_date + datetime.timedelta(days=self.relative_to_date.weekday())
        else:
            # Return Sunday of the target week (end of the week)
            return adjusted_date + datetime.timedelta(days=6)

    def _parse_for_relative_calendar_month(
        self, months_offset: int, modifier: RelDateModifierEnum | None = None
    ) -> datetime.date | int:
        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            # Take an extra period so we can go forward 1 day at the end
            months_offset -= 1

        # Adjust the date by the specified number of months
        adjusted_date = self.relative_to_date + relativedelta(months=months_offset)

        # Get the start of the next month, then go back one day
        next_month = (adjusted_date.month % 12) + 1
        if next_month == 1:  # If next month is January, we are crossing the year boundary
            adjusted_date = adjusted_date.replace(year=adjusted_date.year + 1)

        result = adjusted_date.replace(month=next_month, day=1) - datetime.timedelta(days=1)
        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            # Add the extra day from the extra month we reversed to get to the beginning of the month
            result += datetime.timedelta(days=1)

        if modifier == RelDateModifierEnum.ANCHOR_IN_PERIOD.value:
            return result.replace(day=adjusted_date.day)

        return result

    def _parse_for_relative_calendar_quarter(
        self, quarters_offset: int, modifier: RelDateModifierEnum | None = None
    ) -> datetime.date | int:
        # Determine the start of the current quarter
        current_month = self.relative_to_date.month
        start_of_quarter = current_month - ((current_month - 1) % 3)

        # Get the starting point at the beginning of the current quarter
        start_date = self.relative_to_date.replace(month=start_of_quarter, day=1)

        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            # Take an extra quarter so we can go forward 1 day at the end
            quarters_offset -= 1

        # Adjust the date by adding/subtracting the quarter offset (3 months per quarter)
        adjusted_date = start_date + relativedelta(months=quarters_offset * 3)

        # Calculate the end of the adjusted quarter
        next_quarter_start_month = (adjusted_date.month + 2) // 3 * 3 + 1
        if next_quarter_start_month > 12:
            next_quarter_start_month = 1
            adjusted_date = adjusted_date.replace(year=adjusted_date.year + 1)

        result = adjusted_date.replace(month=next_quarter_start_month, day=1) - datetime.timedelta(days=1)
        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            result += datetime.timedelta(days=1)

        if modifier == RelDateModifierEnum.ANCHOR_IN_PERIOD.value:
            return self.relative_to_date + relativedelta(months=quarters_offset * 3)

        return result

    def _parse_for_relative_calendar_semi_annual(
        self, semi_annual_offset: int, modifier: RelDateModifierEnum | None = None
    ) -> datetime.date:
        # Calculate the current semi-annual period
        current_month = self.relative_to_date.month
        current_semi_annual = 1 if current_month <= 6 else 2

        # Calculate the target semi-annual period
        total_periods = current_semi_annual + semi_annual_offset
        target_semi_annual = (total_periods - 1) % 2 + 1
        target_year = self.relative_to_date.year + (total_periods - 1) // 2

        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            # Start of the semi-annual period
            return datetime.date(target_year, 1 if target_semi_annual == 1 else 7, 1)
        elif modifier == RelDateModifierEnum.ANCHOR_IN_PERIOD.value:
            # Same day within the target semi-annual period
            target_month = self.relative_to_date.month
            if target_semi_annual != current_semi_annual:
                target_month = target_month + 6 if target_month <= 6 else target_month - 6
            return min(
                datetime.date(target_year, target_month, self.relative_to_date.day),
                datetime.date(target_year, 6 if target_semi_annual == 1 else 12, 30 if target_semi_annual == 1 else 31),
            )
        else:
            # End of the semi-annual period
            return datetime.date(
                target_year, 6 if target_semi_annual == 1 else 12, 30 if target_semi_annual == 1 else 31
            )

    def _parse_for_relative_calendar_year(
        self, years_offset: int, modifier: RelDateModifierEnum | None = None
    ) -> datetime.date | int:
        # Adjust the date by the specified number of years
        adjusted_date = self.relative_to_date + relativedelta(years=years_offset)

        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            result = adjusted_date.replace(month=1, day=1)
        else:
            result = adjusted_date.replace(month=12, day=31)

        if modifier == RelDateModifierEnum.ANCHOR_IN_PERIOD.value:
            return adjusted_date.replace(month=self.relative_to_date.month, day=self.relative_to_date.day)

        return result

    def _parse_for_relative_fiscal_quarter(
        self, quarters_offset: int, modifier: str | None = None
    ) -> datetime.date | int:
        # Adjust the date by the specified number of fiscal quarters (3 months per quarter)
        adjusted_date = get_first_date_of_month(self.relative_to_date + relativedelta(months=quarters_offset * 3))

        # Determine the end month of the target fiscal quarter
        target_fiscal_quarter_end_month = self.determine_fiscal_quarter_end_month(
            self.fiscal_year_end_month, adjusted_date.month
        )

        # Determine the end month of the prior fiscal quarter
        prior_period_adjusted_date = adjusted_date - relativedelta(months=3)
        prior_fiscal_end_month = self.determine_fiscal_quarter_end_month(
            self.fiscal_year_end_month, prior_period_adjusted_date.month
        )

        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            # Calculate the start of the fiscal quarter
            start_year = adjusted_date.year
            if prior_fiscal_end_month > adjusted_date.month:
                start_year -= 1
            start_date = datetime.date(start_year, prior_fiscal_end_month, 1) + relativedelta(months=1)
            return start_date

        end_year = adjusted_date.year
        if target_fiscal_quarter_end_month < adjusted_date.month:
            end_year += 1
        end_date = datetime.date(end_year, target_fiscal_quarter_end_month, adjusted_date.day)
        result = get_last_date_of_month(end_date)

        if modifier == RelDateModifierEnum.ANCHOR_IN_PERIOD.value:
            # Maintain the same day of the month within the adjusted fiscal quarter
            try:
                return self.relative_to_date.replace(
                    year=adjusted_date.year, month=adjusted_date.month, day=self.relative_to_date.day
                )
            except ValueError:
                # If the day is out of range for the adjusted month, use the last day of the adjusted month
                last_day_of_month = get_last_date_of_month(adjusted_date)
                return last_day_of_month

        return result

    def _parse_for_relative_fiscal_semi_annual(self, semi_annual_offset: int, modifier: str | None = None):
        # Adjust the date by the specified number of fiscal quarters (6 months per half)
        adjusted_date = get_first_date_of_month(self.relative_to_date + relativedelta(months=semi_annual_offset * 6))

        # Determine the end month of the target fiscal half
        target_fiscal_half_end_month = self.determine_fiscal_half_end_month(
            self.fiscal_year_end_month, adjusted_date.month
        )

        # Determine the end month of the prior fiscal half
        prior_period_adjusted_date = adjusted_date - relativedelta(months=6)
        prior_fiscal_end_month = self.determine_fiscal_half_end_month(
            self.fiscal_year_end_month, prior_period_adjusted_date.month
        )

        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            # Calculate the start of the fiscal half
            start_year = adjusted_date.year
            if prior_fiscal_end_month > adjusted_date.month:
                start_year -= 1
            start_date = datetime.date(start_year, prior_fiscal_end_month, 1) + relativedelta(months=1)
            return start_date

        end_year = adjusted_date.year
        if target_fiscal_half_end_month < adjusted_date.month:
            end_year += 1
        end_date = datetime.date(end_year, target_fiscal_half_end_month, adjusted_date.day)
        result = get_last_date_of_month(end_date)

        if modifier == RelDateModifierEnum.ANCHOR_IN_PERIOD.value:
            # Maintain the same day of the month within the adjusted fiscal half
            try:
                return self.relative_to_date.replace(
                    year=adjusted_date.year, month=adjusted_date.month, day=self.relative_to_date.day
                )
            except ValueError:
                # If the day is out of range for the adjusted month, use the last day of the adjusted month
                last_day_of_month = get_last_date_of_month(adjusted_date)
                return last_day_of_month

        return result

    def _parse_for_relative_fiscal_year(self, years_offset: int, modifier: str | None = None) -> datetime.date | int:
        fye_month = self.fiscal_year_end_month
        # step 1 - look at the relative_to_date month. if this month is > the fiscal year end month, set target year
        # to be incremented by 1 so we have the fiscal year representation of that calendar date to then manipulate
        anchor_month = self.relative_to_date.month
        if anchor_month > fye_month:
            target_year = self.relative_to_date.year + 1
        else:
            target_year = self.relative_to_date.year
        target_year = target_year + years_offset

        if modifier == RelDateModifierEnum.START_OF_PERIOD.value:
            target_date = datetime.date(target_year - 1, fye_month, 1) + relativedelta(months=1)
        else:
            last_day_of_month = (
                datetime.date(target_year, fye_month, 1) + relativedelta(months=1) - datetime.timedelta(days=1)
            )
            target_date = last_day_of_month

        if modifier == RelDateModifierEnum.ANCHOR_IN_PERIOD.value:
            try:
                # Determine the month and day within the target fiscal year
                anchor_date = datetime.date(target_year, anchor_month, self.relative_to_date.day)
                return anchor_date
            except ValueError:
                # If the day is out of range for the target month, use the last day of the target month
                return target_date

        return target_date

    @staticmethod
    def determine_fiscal_quarter_end_month(fye_month: int | str, target_month: int) -> int:
        fye_month = int(fye_month)
        quarter_end_months = FQE_MONTHS_BY_FYE_MONTH[fye_month]
        for i, quarter_end in enumerate(quarter_end_months):
            quarter_start = (quarter_end - 2) if (quarter_end - 2) > 0 else (quarter_end - 2) + 12
            quarter_middle = (quarter_end - 1) if (quarter_end - 1) > 0 else (quarter_end - 1) + 12
            quarter_months = [quarter_start, quarter_middle, quarter_end]
            if target_month in quarter_months:
                return quarter_end

    @staticmethod
    def determine_current_fiscal_quarter(
        effective_date: datetime.date,
        fye_month: int | str,
    ) -> int:
        fye_month = int(fye_month)
        target_month = effective_date.month
        quarter_end_months = FQE_MONTHS_BY_FYE_MONTH[fye_month]
        for i, quarter_end in enumerate(quarter_end_months):
            quarter_start = (quarter_end - 2) if (quarter_end - 2) > 0 else (quarter_end - 2) + 12
            quarter_middle = (quarter_end - 1) if (quarter_end - 1) > 0 else (quarter_end - 1) + 12
            quarter_months = [quarter_start, quarter_middle, quarter_end]
            if target_month in quarter_months:
                return i + 1

    @staticmethod
    def determine_fiscal_half_end_month(fye_month: int | str, target_month: int) -> int:
        fye_month = int(fye_month)
        half_end_months = FYE_TO_SEMI_ANNUAL_MONTHS[fye_month]
        for i, half_end in enumerate(half_end_months):
            half_months = []
            for x in range(5, -1, -1):
                half_months.append((half_end - x) if (half_end - x) > 0 else (half_end - x) + 12)
                if target_month in half_months:
                    return half_end

    @staticmethod
    def determine_current_fiscal_half(effective_date: datetime.date, fye_month: int | str):
        fye_month = int(fye_month)
        target_month = effective_date.month
        half_end_months = FYE_TO_SEMI_ANNUAL_MONTHS[fye_month]
        for i, half_end in enumerate(half_end_months):
            half_months = []
            for x in range(5, -1, -1):
                half_months.append((half_end - x) if (half_end - x) > 0 else (half_end - x) + 12)
                if target_month in half_months:
                    return i + 1


# Type to make sure string is valid
ValidRelDateType = Annotated[str | datetime.date, AfterValidator(RelDate().validate)]


class RelDateTemplateParser:
    """
    A template parser that processes relative date expressions and applies custom date formatting.

    This parser allows for the use of relative date expressions within double curly braces {{ }}
    in a template string. It also supports custom date formatting using a pipe symbol |.

    The relative date expressions are parsed using a RelDateParser, which should be implemented
    to handle various relative date formats (e.g., -1FQ, 0CM, 1FY).

    Date formatting supports the following tokens (case-insensitive):
    - 'yyyy': Four-digit year (e.g., "2024")
    - 'yy': Last two digits of the year (e.g., "24")
    - 'mmmm': Full month name (e.g., "July")
    - 'mmm': Abbreviated month name (e.g., "Jul")
    - 'mm': Two-digit month (e.g., "07")
    - 'm': Month without leading zero (e.g., "7")
    - 'dd': Two-digit day (e.g., "05")
    - 'd': Day without leading zero (e.g., "5")
    - 'do': Day with ordinal suffix (e.g., "5th")
    - 'dddd': Full weekday name (e.g., "Monday")
    - 'ddd': Abbreviated weekday name (e.g., "Mon")
    - 'fq': Fiscal quarter number (e.g., 1)
    - 'q': Calendar quarter number (e.g., 2)
    - 'fyyyy': Four-digit fiscal year (e.g., "2025")
    - 'fyy': Last two digits of the fiscal year (e.g., "25")

    Note: Format tokens are case-insensitive, so 'MMM YY', 'mmm yy', and 'Mmm Yy' are all equivalent.

    Args:
        relative_to_date (datetime, optional): The reference date for relative calculations.
            Defaults to the current date.
        fiscal_year_end_month (int, optional): The month (1-12) when the fiscal year ends.
            Defaults to 8 (August).

    Examples:
        parser = RelDateTemplateParser(fiscal_year_end_month=8)  # Fiscal year ends in August

        # Basic usage
        template = "Report for: {{ -1FQ }}"
        result = parser.parse(template)
        # Output: "Report for: 2024-01-01" (assuming current date is in Q2 2024)

        # With date formatting
        template = "Current month: {{ 0CM | mmmm yyyy }}"
        result = parser.parse(template)
        # Output: "Current month: April 2024" (assuming current date is in April 2024)

        # Multiple expressions in one template
        template = "Period: {{ -1FQ | mm/dd/yy }} to {{ 0FQ | mm/dd/yy }}"
        result = parser.parse(template)
        # Output: "Period: 01/01/24 to 03/31/24" (assuming current date is in Q2 2024)

        # Fiscal quarter formatting
        template = "FQ{{ 0FQ | fq }} of {{ 0FQ | yyyy }}"
        result = parser.parse(template)
        # Output: "FQ3 of 2024" (assuming current date is in May 2024 and fiscal year ends in August)

        # Calendar quarter formatting
        template = "Calendar Quarter: Q{{ 0CQ | q }} of {{ 0CQ | yyyy }}"
        result = parser.parse(template)
        # Output: "Calendar Quarter: Q2 of 2024" (assuming current date is in Q2 2024)

    Note:
        The actual parsing of relative date expressions (e.g., -1FQ, 0CM) should be implemented
        in the RelDateParser class, which is used internally by this parser.
    """

    def __init__(self, relative_to_date: datetime.date | None = None, fiscal_year_end_month: int = 12):
        self.reldate_parser = RelDate(relative_to_date, fiscal_year_end_month)
        self.fiscal_year_end_month = fiscal_year_end_month

    def format_date(self, date: datetime.date, format_str: str):
        format_map = {
            'yyyy': lambda d: f'{d.year:04d}',
            'yy': lambda d: f'{d.year % 100:02d}',
            'mmmm': lambda d: d.strftime('%B'),
            'mmm': lambda d: d.strftime('%b'),
            'mm': lambda d: f'{d.month:02d}',
            'm': lambda d: f'{d.month}',
            'dd': lambda d: f'{d.day:02d}',
            'd': lambda d: f'{d.day}',
            'do': lambda d: f'{d.day}{self._ordinal_suffix(d.day)}',
            'dddd': lambda d: d.strftime('%A'),
            'ddd': lambda d: d.strftime('%a'),
            'ww': lambda d: f'{d.isocalendar()[1]:02d}',
            'w': lambda d: f'{d.isocalendar()[1]}',
            'q': lambda d: f'{(d.month - 1) // 3 + 1}',
            'fq': lambda d: f'{self._get_fiscal_quarter(d)}',
            'fyyyy': lambda d: f'{self._get_fiscal_year(d):04d}',
            'fyy': lambda d: f'{self._get_fiscal_year(d) % 100:02d}',
        }

        tokens_replaced = [False]  # Use a list to allow modification in the inner function

        def replace_format(match):
            key = match.group(0).lower()
            if key in format_map:
                tokens_replaced[0] = True
                return format_map[key](date)
            return match.group(0)

        # Use regex to find and replace format specifiers (case-insensitive)
        pattern = '|'.join(map(re.escape, sorted(format_map.keys(), key=len, reverse=True)))
        result = re.sub(pattern, replace_format, format_str, flags=re.IGNORECASE)

        if not tokens_replaced[0]:
            raise ValueError(f"No valid date format tokens found in: '{format_str}'")

        return result

    def parse(self, template):
        def replace_match(match):
            expr = match.group(1)

            # Check if this is a nested curly brace
            if expr.strip().startswith('{') and expr.strip().endswith('}'):
                return '{{' + expr + '}}'

            parts = expr.split('|', 1)

            # Assume the first part is always a RelDate expression
            rel_date_expr = parts[0].strip()
            date = self.reldate_parser.parse(rel_date_expr)

            # Apply formatting if provided
            if len(parts) > 1:
                format_str = parts[1].strip()
                try:
                    return self.format_date(date, format_str)
                except ValueError as e:
                    raise ValueError(f"Error in expression '{{{{ {expr} }}}}': {str(e)}")
            else:
                return str(date)

        return re.sub(r'\{\{(.*?)\}\}', replace_match, template)

    @staticmethod
    def _ordinal_suffix(day: int):
        if 11 <= day <= 13:
            return 'th'
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return suffix

    def _get_fiscal_quarter(self, date: datetime.date):
        return self.reldate_parser.determine_current_fiscal_quarter(
            effective_date=date,
            fye_month=self.fiscal_year_end_month,
        )

    def _get_fiscal_year(self, date: datetime.date) -> int:
        if date.month > self.fiscal_year_end_month:
            return date.year + 1
        return date.year


def adjust_month_for_fye_change(current_month: int, old_fye_month: int, new_fye_month: int) -> int:
    """
    Preserve the relative offset of a month when the fiscal year end changes.

    When a fiscal year end is updated, annual deliverables should maintain their
    relative position to the fiscal year end. For example, a deliverable that
    triggers "1 month before FYE" should remain 1 month before the new FYE.

    Args:
        current_month: The current month (1-12) to adjust
        old_fye_month: The old fiscal year end month (1-12)
        new_fye_month: The new fiscal year end month (1-12)

    Returns:
        The adjusted month (1-12) that maintains the same offset from the new FYE

    Examples:
        >>> # Budget deliverable: Nov (month 11) with Dec FYE (month 12) -> offset -1
        >>> # Change to Jun FYE (month 6) -> should be May (month 5), still offset -1
        >>> adjust_month_for_fye_change(11, 12, 6)
        5

        >>> # Deliverable in same month as FYE
        >>> adjust_month_for_fye_change(12, 12, 6)
        6

        >>> # Deliverable 3 months after FYE: Mar (month 3) with Dec FYE -> offset +3
        >>> # Change to Jun FYE -> should be Sep (month 9), still offset +3
        >>> adjust_month_for_fye_change(3, 12, 6)
        9
    """
    # Calculate offset from old FYE
    offset = current_month - old_fye_month

    # Normalize offset to -6 to +6 range (shortest distance around the calendar)
    # This ensures we preserve the "closest" relationship to the FYE
    if offset > 6:
        offset = offset - 12
    elif offset < -6:
        offset = offset + 12

    # Apply the same offset to new FYE
    new_month = new_fye_month + offset

    # Wrap to 1-12 range
    if new_month < 1:
        new_month = new_month + 12
    elif new_month > 12:
        new_month = new_month - 12

    return new_month
