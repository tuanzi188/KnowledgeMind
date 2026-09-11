from app.core.user_context import UserContext
from app.services.access_control import (
    build_acl_metadata,
    can_access,
    can_manage,
    filter_accessible_records,
)


def test_admin_can_access_everything():
    admin = UserContext(user_id="a", roles=["admin"])
    assert can_access(admin, {"owner": "someone"}) is True
    records = [{"metadata": {"owner": "someone"}}]
    assert filter_accessible_records(admin, records) == records


def test_public_and_owner_access():
    user = UserContext(user_id="u1", roles=[])
    assert can_access(user, {"is_public": True}) is True
    assert can_access(user, {"owner": "u1"}) is True
    assert can_access(user, {"owner": "u2"}) is False


def test_department_and_role_access():
    user = UserContext(user_id="u1", roles=["reader"], department="sales")
    assert can_access(user, {"allowed_departments": ["sales"]}) is True
    assert can_access(user, {"allowed_roles": ["reader"]}) is True
    assert can_access(user, {"allowed_departments": ["hr"]}) is False


def test_can_manage_and_acl_build():
    admin = UserContext(user_id="a", roles=["admin"])
    user = UserContext(user_id="u1", roles=[])
    assert can_manage(admin, {"owner": "u2"}) is True
    assert can_manage(user, {"owner": "u1"}) is True
    assert can_manage(user, {"owner": "u2"}) is False

    acl = build_acl_metadata(
        user,
        allowed_users=["u1", "u2"],
        allowed_departments=["sales"],
        is_public=False,
    )
    assert acl["owner"] == "u1"
    assert acl["is_public"] is False
    assert acl["allowed_users"] == ["u1", "u2"]
    assert acl["allowed_departments"] == ["sales"]