import base64
import calendar
import datetime
import decimal
import re
from collections import defaultdict
from decimal import Decimal
from importlib import import_module
from itertools import islice
from typing import Callable, Generic, Iterable, List, Optional, Type, TypeVar, Union

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

from src.common.lazy import SimpleLazyObject

HTML_BLOCK_TAGS = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']


def base64_encode_string(to_encode: str) -> str:
    to_encode_bytes = to_encode.encode('utf-8')
    encoded_to_encode = base64.b64encode(to_encode_bytes)
    encoded_to_encode_str = encoded_to_encode.decode('utf-8')

    return encoded_to_encode_str


def decimal_parse(number: Union[str, Decimal, float, int]) -> Decimal:
    """
    Ensures a decimal is returned with valid string or datetime
    """
    if isinstance(number, Decimal):
        return number

    if isinstance(number, float) or isinstance(number, int):
        return Decimal(number)

    return Decimal(number.replace(',', ''))


def safe_decimal_parse(number: Union[str, Decimal, None]) -> Optional[Decimal]:
    """
    Ensures a decimal is returned with valid string or datetime
    and does not raise for None
    """
    if not number:
        return None

    return decimal_parse(number)


def safe_date_or_datetime_to_date(d: Union[datetime.date, datetime.datetime]) -> datetime.date:
    if isinstance(d, datetime.datetime):
        return d.date()
    elif isinstance(d, datetime.date):
        return d
    else:
        raise TypeError(f'Expected datetime.date or datetime.datetime, got {type(d)}')


def safe_datetime_parse(
    dt: Union[str, datetime.datetime, None],
) -> Optional[datetime.datetime]:
    """
    Ensures a datetime is returned with valid string or datetime
    and does not raise for None
    """
    if isinstance(dt, datetime.datetime):
        return dt

    if not dt:
        return None

    return date_parser.parse(dt)


def safe_date_parse(
    date: Union[str, datetime.date, None],
) -> Optional[datetime.date]:
    """
    Ensures a datetime is returned with valid string or datetime
    and does not raise for None
    """
    if isinstance(date, datetime.date):
        return date

    if not date:
        return None

    return date_parser.parse(date).date()


def raise_exception(exc: Exception):
    """
    Useful for lambdas
    """
    raise exc


_T = TypeVar('_T')


def split_every(iterable: Iterable[_T], split_size: int) -> List[_T]:
    piece: _T = list(islice(iterable, split_size))
    while piece:
        yield piece
        piece = list(islice(iterable, split_size))


def import_dotted_path_string(dotted_path: str):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError(f'Module {module_path} does not define a {class_name} attribute/class') from err


def get_nested_attr(element: object, attribute: str):
    attributes = attribute.split('.')

    current_element = element
    for attribute in attributes:
        if not current_element:
            return None
        current_element = getattr(current_element, attribute)

    return current_element


def group_iterable_by_attribute(
    iterable: Iterable[object],
    group_by_key: str,
    sort_key: str | None = None,
    value_key: str | None = None,
    reverse: bool = False,
):
    grouped_iterable = defaultdict(list)

    for element in iterable:
        value = get_nested_attr(element, group_by_key)

        if value_key:
            element = get_nested_attr(element, value_key)

        grouped_iterable[value].append(element)

    if sort_key:
        for key, value in grouped_iterable.items():
            grouped_iterable[key] = sorted(value, key=lambda item: get_nested_attr(item, sort_key), reverse=reverse)

    return grouped_iterable


def get_nested_key(element: object, attribute: str):
    attributes = attribute.split('.')

    current_element = element
    for attribute in attributes:
        if not current_element:
            return None
        current_element = current_element[attribute]

    return current_element


def legal_strftime(date: datetime.date) -> str:
    """
    Used for contracts formats dates to like '29th of July, 2022'
    """
    suffix = 'th' if 11 <= date.day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(date.day % 10, 'th')
    return date.strftime('{S} of %B, %Y').replace('{S}', str(date.day) + suffix)


def format_money(number: decimal.Decimal, currency_sym: str = '$') -> str:
    return f'{currency_sym}{number:,.2f}'


class _LazyReference(SimpleLazyObject): ...


LazyCallableType = TypeVar('LazyCallableType', bound=Callable)


def make_lazy(func: Type[LazyCallableType]) -> Generic[LazyCallableType]:
    """
    Func will not be executed unless accessed
    """
    return _LazyReference(func)


def get_last_date_of_month(date: datetime.date) -> datetime.date:
    return datetime.date(date.year, date.month, calendar.monthrange(date.year, date.month)[1])


def get_first_date_of_month(date: datetime.date) -> datetime.date:
    return datetime.date(date.year, date.month, 1)


def get_last_date_of_quarter(date: datetime.date) -> datetime.date:
    adjusted_date = date + relativedelta(months=2)
    return get_last_date_of_month(adjusted_date)


def get_last_date_of_year(date: datetime.date) -> datetime.date:
    return datetime.date(date.year, 12, 31)


# Pre-compile patterns
COMMON_HTML_TAGS = re.compile(
    r'<(?:p|div|span|a|b|i|strong|em|h[1-6]|br|hr|img|table|tr|td|ul|ol|li)[\s>]', re.IGNORECASE
)


def html_to_plain_text(value: str) -> str:
    # Value can be numbies, or bool
    if not isinstance(value, str):
        return value

    if not value:
        return value

    # Quick check: if no '<' character, it can't be HTML
    if '<' not in value:
        return value

    # Check for common HTML tags (more reliable than just any tag pattern)
    if not COMMON_HTML_TAGS.search(value):
        return value

    # Only use BeautifulSoup if we're confident it's HTML
    soup = BeautifulSoup(value, 'html.parser')
    plain_text = soup.get_text(separator=' ', strip=True)
    plain_text = ' '.join(plain_text.split())

    return plain_text


def rich_html_to_plain_text(value: str) -> str:
    """
    Convert HTML to formatted plain text for Excel display.
    Preserves structure with bullet points, line breaks, etc.
    """
    # Value can be numbers, or bool
    if not isinstance(value, str):
        return value

    if not value:
        return value

    # Quick check: if no '<' character, it can't be HTML
    if '<' not in value:
        return value

    # Check for common HTML tags
    if not COMMON_HTML_TAGS.search(value):
        return value

    # Parse HTML
    soup = BeautifulSoup(value, 'html.parser')

    # Process lists to add bullet points
    for ul in soup.find_all('ul'):
        for li in ul.find_all('li', recursive=False):
            # Add bullet point to beginning of li text
            li.string = '• ' + (li.get_text(strip=True) if li.get_text(strip=True) else '')

    # Process ordered lists
    for ol in soup.find_all('ol'):
        for i, li in enumerate(ol.find_all('li', recursive=False), 1):
            # Add number to beginning of li text
            li.string = f'{i}. ' + (li.get_text(strip=True) if li.get_text(strip=True) else '')

    # Replace block elements with text + line breaks
    for tag in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        tag.insert_after('\n')

    # Replace br tags with line breaks
    for br in soup.find_all('br'):
        br.replace_with('\n')

    # Replace hr tags with line breaks
    for hr in soup.find_all('hr'):
        hr.replace_with('\n')

    # Get the text with structure preserved
    text = soup.get_text()

    # Clean up excessive whitespace while preserving intentional line breaks
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # Clean each line individually
        cleaned_line = ' '.join(line.split())
        cleaned_lines.append(cleaned_line)

    # Join lines and remove excessive blank lines
    result = '\n'.join(cleaned_lines)

    # Replace multiple consecutive line breaks with max 2
    while '\n\n\n' in result:
        result = result.replace('\n\n\n', '\n\n')

    # Trim leading/trailing whitespace
    result = result.strip()

    return result
