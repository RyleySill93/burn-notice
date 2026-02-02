"""
Unit tests for the PermissionHandler base class.

These tests verify the core selector matching and rule extraction logic
that all permission handlers inherit and rely upon.
"""

import pytest

from src.core.authorization.constants import (
    PermissionEffectEnum,
    PermissionTypeEnum,
    ResourceSelectorTypeEnum,
    ResourceTypeEnum,
)
from src.core.authorization.domains import AccessPolicyRead
from src.core.authorization.permission_handler import PermissionHandler


class ConcretePermissionHandler(PermissionHandler):
    """Concrete implementation for testing the base class methods."""

    @property
    def resource_type(self) -> ResourceTypeEnum:
        return ResourceTypeEnum.CUSTOMER

    def get_all_resource_ids(self):
        return {'cust_1', 'cust_2', 'cust_3'}

    def get_universe(self, parent_resource_ids):
        return parent_resource_ids

    def get_hierarchical_resource_ids(self, rules, permission_type, parent_resource_ids=None):
        return set()

    def _has_hierarchical_permission(self, rules, permission_type, resource_id):
        return False

    def list_resources_for_customer(self, customer_id):
        return [{'id': customer_id, 'name': 'Test Customer'}]


def make_policy(
    permission_type: PermissionTypeEnum,
    resource_type: ResourceTypeEnum,
    effect: PermissionEffectEnum,
    selector: dict,
    policy_id: str = 'policy_1',
) -> AccessPolicyRead:
    """Helper to create an AccessPolicyRead for testing."""
    return AccessPolicyRead(
        id=policy_id,
        name='Test Policy',
        permission_type=permission_type,
        resource_type=resource_type,
        resource_selector=selector,
        effect=effect,
        customer_id=None,
    )


class TestExtractResourceIdsFromRule:
    """Tests for extract_resource_ids_from_rule method."""

    @pytest.fixture
    def handler(self):
        return ConcretePermissionHandler()

    def test_extract_exact_selector(self, handler):
        """EXACT selector should return a set with the single ID."""
        rule = make_policy(
            PermissionTypeEnum.READ,
            ResourceTypeEnum.CUSTOMER,
            PermissionEffectEnum.ALLOW,
            {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
        )

        result = handler.extract_resource_ids_from_rule(rule)

        assert result == {'cust_123'}

    def test_extract_exact_selector_no_id(self, handler):
        """EXACT selector without ID should return empty set."""
        rule = make_policy(
            PermissionTypeEnum.READ,
            ResourceTypeEnum.CUSTOMER,
            PermissionEffectEnum.ALLOW,
            {'type': ResourceSelectorTypeEnum.EXACT},
        )

        result = handler.extract_resource_ids_from_rule(rule)

        assert result == set()

    def test_extract_multiple_selector(self, handler):
        """MULTIPLE selector should return all specified IDs."""
        rule = make_policy(
            PermissionTypeEnum.READ,
            ResourceTypeEnum.CUSTOMER,
            PermissionEffectEnum.ALLOW,
            {'type': ResourceSelectorTypeEnum.MULTIPLE, 'ids': ['cust_1', 'cust_2', 'cust_3']},
        )

        result = handler.extract_resource_ids_from_rule(rule)

        assert result == {'cust_1', 'cust_2', 'cust_3'}

    def test_extract_multiple_selector_empty_ids(self, handler):
        """MULTIPLE selector with empty ids should return empty set."""
        rule = make_policy(
            PermissionTypeEnum.READ,
            ResourceTypeEnum.CUSTOMER,
            PermissionEffectEnum.ALLOW,
            {'type': ResourceSelectorTypeEnum.MULTIPLE, 'ids': []},
        )

        result = handler.extract_resource_ids_from_rule(rule)

        assert result == set()

    def test_extract_wildcard_selector(self, handler):
        """WILDCARD selector should return empty set (no specific IDs)."""
        rule = make_policy(
            PermissionTypeEnum.READ,
            ResourceTypeEnum.CUSTOMER,
            PermissionEffectEnum.ALLOW,
            {'type': ResourceSelectorTypeEnum.WILDCARD},
        )

        result = handler.extract_resource_ids_from_rule(rule)

        assert result == set()

    def test_extract_wildcard_except_selector(self, handler):
        """WILDCARD_EXCEPT selector should return empty set (IDs handled specially)."""
        rule = make_policy(
            PermissionTypeEnum.READ,
            ResourceTypeEnum.CUSTOMER,
            PermissionEffectEnum.ALLOW,
            {'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': ['cust_1']},
        )

        result = handler.extract_resource_ids_from_rule(rule)

        assert result == set()


class TestSelectorMatchesResource:
    """Tests for _selector_matches_resource method."""

    @pytest.fixture
    def handler(self):
        return ConcretePermissionHandler()

    def test_exact_matches_same_id(self, handler):
        """EXACT selector should match when IDs are equal."""
        selector = {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'}

        result = handler._selector_matches_resource(selector, 'cust_123')

        assert result is True

    def test_exact_does_not_match_different_id(self, handler):
        """EXACT selector should not match different IDs."""
        selector = {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'}

        result = handler._selector_matches_resource(selector, 'cust_456')

        assert result is False

    def test_multiple_matches_included_id(self, handler):
        """MULTIPLE selector should match IDs in the list."""
        selector = {'type': ResourceSelectorTypeEnum.MULTIPLE, 'ids': ['cust_1', 'cust_2', 'cust_3']}

        assert handler._selector_matches_resource(selector, 'cust_1') is True
        assert handler._selector_matches_resource(selector, 'cust_2') is True
        assert handler._selector_matches_resource(selector, 'cust_3') is True

    def test_multiple_does_not_match_excluded_id(self, handler):
        """MULTIPLE selector should not match IDs not in the list."""
        selector = {'type': ResourceSelectorTypeEnum.MULTIPLE, 'ids': ['cust_1', 'cust_2']}

        result = handler._selector_matches_resource(selector, 'cust_999')

        assert result is False

    def test_wildcard_matches_any_id(self, handler):
        """WILDCARD selector should match any resource ID."""
        selector = {'type': ResourceSelectorTypeEnum.WILDCARD}

        assert handler._selector_matches_resource(selector, 'cust_1') is True
        assert handler._selector_matches_resource(selector, 'cust_999') is True
        assert handler._selector_matches_resource(selector, 'any_id_at_all') is True

    def test_wildcard_except_matches_non_excluded(self, handler):
        """WILDCARD_EXCEPT should match IDs not in the exclusion list."""
        selector = {'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': ['cust_1', 'cust_2']}

        assert handler._selector_matches_resource(selector, 'cust_3') is True
        assert handler._selector_matches_resource(selector, 'cust_999') is True

    def test_wildcard_except_does_not_match_excluded(self, handler):
        """WILDCARD_EXCEPT should not match IDs in the exclusion list."""
        selector = {'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': ['cust_1', 'cust_2']}

        assert handler._selector_matches_resource(selector, 'cust_1') is False
        assert handler._selector_matches_resource(selector, 'cust_2') is False

    def test_wildcard_matches_without_resource_id(self, handler):
        """WILDCARD selector should return True when no resource_id is provided."""
        selector = {'type': ResourceSelectorTypeEnum.WILDCARD}

        result = handler._selector_matches_resource(selector, None)

        assert result is True

    def test_exact_does_not_match_without_resource_id(self, handler):
        """EXACT selector should return False when no resource_id is provided."""
        selector = {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'}

        result = handler._selector_matches_resource(selector, None)

        assert result is False


class TestHasMatchingAllowRule:
    """Tests for has_matching_allow_rule method."""

    @pytest.fixture
    def handler(self):
        return ConcretePermissionHandler()

    def test_finds_exact_match(self, handler):
        """Should find an ALLOW rule that matches exactly."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
            )
        ]

        result = handler.has_matching_allow_rule(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is True

    def test_no_match_for_deny(self, handler):
        """Should not find DENY rules when looking for ALLOW."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
            )
        ]

        result = handler.has_matching_allow_rule(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is False

    def test_no_match_for_different_permission_type(self, handler):
        """Should not match when permission type differs."""
        rules = [
            make_policy(
                PermissionTypeEnum.WRITE,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
            )
        ]

        result = handler.has_matching_allow_rule(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is False

    def test_no_match_for_different_resource_type(self, handler):
        """Should not match when resource type differs."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.PROJECT,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
            )
        ]

        result = handler.has_matching_allow_rule(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is False

    def test_wildcard_allow_matches_any_resource(self, handler):
        """Wildcard ALLOW should match any resource ID."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.WILDCARD},
            )
        ]

        assert handler.has_matching_allow_rule(rules, PermissionTypeEnum.READ, 'cust_123') is True
        assert handler.has_matching_allow_rule(rules, PermissionTypeEnum.READ, 'any_id') is True


class TestHasMatchingDenyRule:
    """Tests for has_matching_deny_rule method."""

    @pytest.fixture
    def handler(self):
        return ConcretePermissionHandler()

    def test_finds_exact_match(self, handler):
        """Should find a DENY rule that matches exactly."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
            )
        ]

        result = handler.has_matching_deny_rule(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is True

    def test_no_match_for_allow(self, handler):
        """Should not find ALLOW rules when looking for DENY."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
            )
        ]

        result = handler.has_matching_deny_rule(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is False

    def test_no_match_for_different_permission_type(self, handler):
        """Should not match when permission type differs."""
        rules = [
            make_policy(
                PermissionTypeEnum.WRITE,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
            )
        ]

        result = handler.has_matching_deny_rule(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is False

    def test_wildcard_deny_matches_any_resource(self, handler):
        """Wildcard DENY should match any resource ID."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.WILDCARD},
            )
        ]

        assert handler.has_matching_deny_rule(rules, PermissionTypeEnum.READ, 'cust_123') is True
        assert handler.has_matching_deny_rule(rules, PermissionTypeEnum.READ, 'any_id') is True

    def test_wildcard_except_deny_matches_non_excluded(self, handler):
        """WILDCARD_EXCEPT DENY should match non-excluded resources."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.WILDCARD_EXCEPT, 'excluded_ids': ['cust_safe']},
            )
        ]

        assert handler.has_matching_deny_rule(rules, PermissionTypeEnum.READ, 'cust_123') is True
        assert handler.has_matching_deny_rule(rules, PermissionTypeEnum.READ, 'cust_safe') is False


class TestHasHierarchicalPermission:
    """Tests for has_hierarchical_permission method."""

    @pytest.fixture
    def handler(self):
        return ConcretePermissionHandler()

    def test_deny_overrides_allow(self, handler):
        """Explicit DENY should override any ALLOW rule."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
                policy_id='allow_policy',
            ),
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
                policy_id='deny_policy',
            ),
        ]

        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is False

    def test_allow_without_deny(self, handler):
        """Should allow access when there is an ALLOW but no DENY."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_123'},
            )
        ]

        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is True

    def test_no_rules_returns_false(self, handler):
        """Should deny access when there are no rules."""
        rules = []

        result = handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, 'cust_123')

        assert result is False

    def test_wildcard_deny_blocks_all(self, handler):
        """Wildcard DENY should block access to any resource."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.WILDCARD},
            ),
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.WILDCARD},
            ),
        ]

        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, 'cust_1') is False
        assert handler.has_hierarchical_permission(rules, PermissionTypeEnum.READ, 'any_id') is False


class TestFilterByPermissionModel:
    """Tests for filter_by_permission_model method."""

    @pytest.fixture
    def handler(self):
        return ConcretePermissionHandler()

    def test_filters_out_denied_ids(self, handler):
        """Should filter out IDs that have explicit DENY rules."""
        candidate_ids = {'cust_1', 'cust_2', 'cust_3'}
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.EXACT, 'id': 'cust_2'},
            )
        ]

        result = handler.filter_by_permission_model(candidate_ids, rules, PermissionTypeEnum.READ)

        assert 'cust_2' not in result
        assert 'cust_1' in result
        assert 'cust_3' in result

    def test_empty_candidates_returns_empty(self, handler):
        """Should return empty set when no candidates provided."""
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.ALLOW,
                {'type': ResourceSelectorTypeEnum.WILDCARD},
            )
        ]

        result = handler.filter_by_permission_model(set(), rules, PermissionTypeEnum.READ)

        assert result == set()

    def test_wildcard_deny_not_handled_at_this_level(self, handler):
        """
        Wildcard DENY is NOT handled by filter_by_permission_model.

        Wildcard deny handling happens at a higher level in PermissionService.list_permitted_ids
        which checks for wildcard deny before calling filter_by_permission_model.
        This test documents that filter_by_permission_model only handles explicit IDs.
        """
        candidate_ids = {'cust_1', 'cust_2', 'cust_3'}
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.WILDCARD},
            )
        ]

        result = handler.filter_by_permission_model(candidate_ids, rules, PermissionTypeEnum.READ)

        # Wildcard deny doesn't filter at this level - all candidates pass through
        # The PermissionService.list_permitted_ids handles wildcard deny separately
        assert result == candidate_ids

    def test_multiple_selector_deny(self, handler):
        """MULTIPLE selector DENY should filter all specified IDs."""
        candidate_ids = {'cust_1', 'cust_2', 'cust_3', 'cust_4'}
        rules = [
            make_policy(
                PermissionTypeEnum.READ,
                ResourceTypeEnum.CUSTOMER,
                PermissionEffectEnum.DENY,
                {'type': ResourceSelectorTypeEnum.MULTIPLE, 'ids': ['cust_1', 'cust_3']},
            )
        ]

        result = handler.filter_by_permission_model(candidate_ids, rules, PermissionTypeEnum.READ)

        assert result == {'cust_2', 'cust_4'}
