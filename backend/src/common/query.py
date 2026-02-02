import re
from typing import Any, List, Optional, Union

from sqlalchemy import ClauseElement, Column, case, func, literal_column, or_, text
from sqlalchemy.orm import Query

from src.common.enum import BaseEnum


# Query Operator Enums
class TextSearchLanguage(BaseEnum):
    ENGLISH = 'english'
    # simple is languge agnostic, so it removes stemming + stopwords when constructing the search vector/query
    SIMPLE = 'simple'


class QueryOperator(BaseEnum):
    CONTAINS = '@@'


def preprocess_search_text(search_text: str) -> str:
    """
    Preprocesses the search text by standardizing it for postgres text search.
    Preserves international characters and diacritics while handling special characters.
    """
    if not search_text:
        return ''

    search_text = search_text.strip().lower()

    # Split into terms but preserve international characters
    terms = []
    for part in search_text.split():
        # Keep all letters (including diacritics), numbers, and email characters
        # Only remove characters that would cause issues with tsquery
        cleaned = re.sub(r'[&|!():*"\'\\]', '', part)
        if cleaned:
            terms.append(cleaned)
            # Also add parts split by @ and . for better email matching
            if '@' in cleaned or '.' in cleaned:
                sub_parts = re.split(r'[@.]', cleaned)
                terms.extend([p for p in sub_parts if p and p not in terms])

    return ' '.join(terms)


def pgsql_full_text_search(
    query: Query,
    search_field: str,
    search: str | None,
    language_search_vector: TextSearchLanguage = TextSearchLanguage.ENGLISH,
):
    """
    Performs a full-text search using ts_rank_cd on a specified field of a model. Does no pagination,
    simply creates the search ranked query to return to callers to process results.

    only performs search and ranking - should not implement any other conditional logic - that should be owned
    by clients of this query utility

    will always search the 'simple' search vector which is language agnostic as it will not stem words or eliminate
    stopwords. will also use whatever language search vector is passed in as well to create a composite vector search
    score
    """
    cleaned_search = preprocess_search_text(search)
    terms = cleaned_search.strip().split()
    if terms:
        prepared_terms = ' & '.join([f'{term.strip()}:*' for term in terms if term])
        # language specific search
        search_query_language = func.to_tsquery(language_search_vector.value, prepared_terms)
        text_search_vector_language = func.to_tsvector(language_search_vector.value, search_field)
        rank_expression_language = func.ts_rank_cd(text_search_vector_language, search_query_language)
        # language agnostic search
        search_query_simple = func.to_tsquery(TextSearchLanguage.SIMPLE.value, prepared_terms)
        text_search_vector_simple = func.to_tsvector(TextSearchLanguage.SIMPLE.value, search_field)
        rank_expression_simple = func.ts_rank_cd(text_search_vector_simple, search_query_simple)

        average_search_score = (rank_expression_language + rank_expression_simple) / 2

        unified_score = case(
            (func.lower(search_field) == func.lower(search), 1000),  # Exact match gives a score of 1000
            (func.lower(search_field).startswith(func.lower(search)), 500),  # Starts with gives a score of 500
            else_=average_search_score,  # If none of the above conditions are met, use the average search score
        ).label('unified_score')

        # Composite score for alphabetical tie-breaking
        alphabetical_factor = (func.ascii(func.lower(func.substr(search_field, 1, 1))) - 96) / 100.0
        composite_score = (unified_score - alphabetical_factor).label('composite_score')

        query = (
            query.add_columns(unified_score, composite_score)
            .filter(
                text_search_vector_language.op(QueryOperator.CONTAINS.value)(search_query_language)
                | text_search_vector_simple.op(QueryOperator.CONTAINS.value)(search_query_simple)
            )
            .order_by(unified_score.desc(), composite_score.desc())
        )
    else:
        # Use literal_column to add a constant search_rank value
        unified_score = literal_column('0.0').label('unified_score')
        composite_score = literal_column('0.0').label('composite_score')
        query = query.add_columns(unified_score, composite_score).order_by(search_field)
    return query


def pg_trgm_substring_search_like(
    query: Query,
    search_field: str,
    search: str | None,
):
    """
    Performs an efficient substring search using ILIKE and the pg_trgm GIN index.
    """
    cleaned_search = preprocess_search_text(search)
    if cleaned_search:
        # Use similarity score for ordering
        similarity_score = func.similarity(search_field, cleaned_search).label('similarity_score')
        query = (
            query.add_columns(similarity_score)
            .filter(search_field.ilike(f'%{cleaned_search}%'))
            .order_by(similarity_score.desc())
        )
    else:
        similarity_score = literal_column('0.0').label('similarity_score')
        query = query.add_columns(similarity_score).order_by(search_field)
    return query


def _create_full_text_search_vector(field: str, language: TextSearchLanguage) -> tuple:
    """
    Creates a text search vector and query for a given field and language.
    """
    text_search_vector = func.to_tsvector(language.value, field)
    return text_search_vector


def _get_exact_match_score(field: str, search: str, base_score: float = 1000.0) -> case:
    """
    Creates a scoring expression for exact matches with different weights.
    """
    return case(
        (func.lower(field) == func.lower(search), base_score),
        (func.lower(field).startswith(func.lower(search)), base_score * 0.5),
        else_=0.0,
    )


def _get_field_expression(field: Union[str, ClauseElement]) -> ClauseElement:
    """
    Convert a field reference to the appropriate SQLAlchemy expression.
    """
    if isinstance(field, str):
        return text(field)
    return field


def multi_field_search(
    query: Query,
    search: Optional[str],
    fields_config: List[dict[str, Any]],
    id_field: Optional[Union[str, Column]] = None,
) -> Query:
    """
    Performs a configurable multi-field search with weighted scoring using PostgreSQL full-text search.

    The function combines multiple search strategies:
    - Full text search using both English and Simple (language-agnostic) dictionaries
    - Partial matching using ILIKE
    - Exact string matching
    - Direct ID matching
    """
    if not search or not fields_config:
        return query.add_columns(literal_column('0.0').label('search_score')).order_by(
            _get_field_expression(fields_config[0]['field'])
        )

    cleaned_search = preprocess_search_text(search)
    terms = cleaned_search.split()

    if not terms:
        return query.add_columns(literal_column('0.0').label('search_score')).order_by(
            _get_field_expression(fields_config[0]['field'])
        )

    # Prepare search conditions
    search_conditions = []
    score_components = []

    # Handle ID-based search if provided
    if id_field:
        cleaned_id_search = search.strip()
        id_condition = func.lower(id_field) == func.lower(cleaned_id_search)
        search_conditions.append(id_condition)
        score_components.append(case((id_condition, 2000.0), else_=0.0))

    # Process each field according to its configuration
    for field_config in fields_config:
        field_expr = _get_field_expression(field_config['field'])
        weight = field_config.get('weight', 1.0)
        exact_match_score = field_config.get('exact_match_score', 1000.0)

        # Add ILIKE condition for partial matches
        like_conditions = []
        for term in terms:
            like_conditions.append(func.lower(field_expr).like(f'%{term}%'))

        # Create text search vectors
        vector_en = func.to_tsvector(TextSearchLanguage.ENGLISH.value, field_expr)
        vector_simple = func.to_tsvector(TextSearchLanguage.SIMPLE.value, field_expr)

        # Prepare tsquery with partial matching
        tsquery_terms = []
        for term in terms:
            tsquery_terms.append(f'{term}:*')
        prepared_terms = ' | '.join(tsquery_terms)  # Use OR instead of AND for better partial matches

        query_en = func.to_tsquery(TextSearchLanguage.ENGLISH.value, prepared_terms)
        query_simple = func.to_tsquery(TextSearchLanguage.SIMPLE.value, prepared_terms)

        # Combine conditions
        field_conditions = [
            vector_en.op(QueryOperator.CONTAINS.value)(query_en),
            vector_simple.op(QueryOperator.CONTAINS.value)(query_simple),
            *like_conditions,
        ]
        search_conditions.append(or_(*field_conditions))

        # Calculate scores
        exact_match = case((func.lower(field_expr) == func.lower(cleaned_search), exact_match_score), else_=0.0)

        ts_rank_en = func.ts_rank_cd(vector_en, query_en) * weight
        ts_rank_simple = func.ts_rank_cd(vector_simple, query_simple) * weight

        # Add scores for LIKE matches
        like_score = sum(case((condition, 50.0 * weight), else_=0.0) for condition in like_conditions)

        score_components.extend([exact_match, ts_rank_en, ts_rank_simple, like_score])

    # Combine all scores
    total_score = sum(score_components).label('search_score')

    # Apply search conditions and scoring
    query = query.add_columns(total_score).filter(or_(*search_conditions)).order_by(total_score.desc())

    return query
