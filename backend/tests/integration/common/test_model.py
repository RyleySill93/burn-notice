import pytest
from sqlalchemy import and_, desc, or_

# Using the User here to test with
from src.core.user import User, UserCreate
from src.network.database.repository.exceptions import PreventingModelTruncation


class TestRepositoryMixinMethods:
    def test_get(self, staff_user):
        fetched_user = User.get(id=staff_user.id)
        assert fetched_user.email == staff_user.email

    def test_get_or_none(self, staff_user):
        fetched_user = User.get_or_none(id=staff_user.id)
        assert fetched_user.email == staff_user.email

        # Test a non-existent user
        assert User.get_or_none(email='missing@example.com') is None

    def test_latest(self, non_staff_user, staff_user):
        # Touch a user to update last modified
        User.update(id=non_staff_user.id, first_name='last-touched')
        user = (
            User.get_query()
            .filter(User.id.in_((non_staff_user.id, staff_user.id)))
            .order_by(desc(User.created_at))
            .first()
        )
        latest_user = User.latest(User.id.in_((non_staff_user.id, staff_user.id)), by=User.modified_at)

        # Since the non_staff_user is created after the staff_user, it should be the latest.
        assert latest_user.email == user.email

    def test_list_attribute(self, staff_user, non_staff_user):
        emails = User.list_attribute('email')
        assert staff_user.email in emails
        assert non_staff_user.email in emails

    def test_list_attributes(self, staff_user, non_staff_user):
        data = User.list_attributes(
            attributes=[
                User.id,
                User.is_active,
            ],
            clauses=[User.id == staff_user.id],
        )
        assert data[0][0] == staff_user.id
        assert data[0][1] == staff_user.is_active

    def test_list_paginated(self, staff_user, non_staff_user):
        paginated_response = User.list_paginated(page_size=1, page=1, ordering='created_at')
        assert len(paginated_response.results) == 1
        assert paginated_response.results[0]['email'] == 'system@burn_notice.com'

        paginated_response = User.list_paginated(page_size=1, page=2, ordering='created_at')
        assert len(paginated_response.results) == 1
        assert paginated_response.results[0]['email'] == 'dev@burn_notice.com'

        paginated_response = User.list_paginated(
            page_size=1, page=1, ordering='created_at', clauses=[User.email == staff_user.email]
        )
        assert len(paginated_response.results) == 1
        assert paginated_response.results[0]['email'] == staff_user.email

    def test_count(self, staff_user, non_staff_user):
        """
        There are two default users
        """
        assert User.count() == 2 + 2

    def test_delete(self, staff_user):
        """
        Test a user gets deleted with a clause
        """
        User.delete(User.id == staff_user.id)
        assert not User.get_or_none(User.id == staff_user.id)

    def test_delete_with_null_arguments(self, staff_user):
        """
        There are two default users
        """
        with pytest.raises(PreventingModelTruncation):
            # Empty delete
            User.delete()
        with pytest.raises(PreventingModelTruncation):
            # Empty list
            User.delete(*[])
        with pytest.raises(PreventingModelTruncation):
            # Empty clauses tuple
            User.delete(*())

        # This is not going to be allowed via sqlalchemy soon which is great, delete these when that is the case
        # Invoking or_() without arguments is deprecated, and will be disallowed in a future release
        with pytest.raises(PreventingModelTruncation):
            User.delete(or_(*[]))
        # Invoking and_() without arguments is deprecated, and will be disallowed in a future release
        with pytest.raises(PreventingModelTruncation):
            User.delete(and_(*[]))

    def test_update(self, staff_user):
        updated_user = User.update(staff_user.id, first_name='John', last_name='Doe')
        assert updated_user.first_name == 'John'
        assert updated_user.last_name == 'Doe'

    def test_update_raise_for_bad_key(self, staff_user):
        with pytest.raises(ValueError):
            User.update(staff_user.id, bad_first_name='John', last_name='Doe')

    def test_update_or_create(self, staff_user):
        # Test existing updated case
        updated_user = User.update_or_create(
            updates={'email': 'updated-email'},
            id=staff_user.id,
        )
        assert updated_user.email == 'updated-email'

        # Test created case
        new_user = User.update_or_create(updates={'id': 'new-id'}, email='new@example.com', first_name='Colt')
        assert new_user.first_name == 'Colt'

    def test_bulk_update(self, staff_user, non_staff_user):
        User.bulk_update(updates={'is_active': False}, clauses=[User.id == staff_user.id])
        staff_user = User.get(id=staff_user.id)
        assert not staff_user.is_active

    def test_bulk_update_mappings(self, staff_user, non_staff_user):
        User.bulk_update_mappings(
            [
                {'id': staff_user.id, 'is_active': False},
                {'id': non_staff_user.id, 'is_active': False},
            ]
        )
        assert User.count(User.is_active == False) == 2

    def test_bulk_create(self):
        """
        There are two default users
        """
        users = [UserCreate(email=f'email_{i}@email.com') for i in range(0, 5)]
        assert User.bulk_create(users) == 5
        assert User.count() == 5 + 2
