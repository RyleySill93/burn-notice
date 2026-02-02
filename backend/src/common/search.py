from abc import ABC, abstractmethod
from typing import List

from src.network.database.repository.mixin import SearchDomainType


class SearchInterface(ABC):
    SEARCH_DOMAIN = NotImplemented
    """
    Interface domain specific search implementations must implement so they can be searched as part of the orchestration
    global search.

    We are implementing search as an interface to be implemented by various domains instead of extending exissting service
    classes to leverage the shared sql <> search domain logic. 
    """

    def search(
        self,
        search: str | None,
        limit: int | None = 50,
        **specifications,
    ) -> List[SearchDomainType]:
        """
        implement limit w/ sane default but allow null. limit useful when paginating upstream in call-site of
        domain search
        """
        query = self._search(search, **specifications)
        if limit:
            query = query.limit(limit)
        return self._convert_to_domain(query)

    @abstractmethod
    def _search(self, search: str | None, **specifications) -> List[SearchDomainType]:
        raise NotImplementedError

    def _convert_to_domain(self, query) -> List[SearchDomainType]:
        results = []
        for row in query:
            (
                model_instance,
                unified_score,
                composite_score,
            ) = row
            search_field_value = getattr(model_instance, self.SEARCH_DOMAIN.get_search_field_value())
            results.append(
                self.SEARCH_DOMAIN.factory(model_instance, unified_score, composite_score, search_field_value)
            )
        return results
