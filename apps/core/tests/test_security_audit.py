from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import RequestFactory

from apps.core.services.security_audit import record_sensitive_action


@pytest.mark.django_db
def test_record_sensitive_action_persists_when_table_exists():
    user = get_user_model().objects.create_user(username="audit-user", password="secret123")
    request = RequestFactory().post("/acciones/sync/")
    request.user = user
    request.META["REMOTE_ADDR"] = "127.0.0.1"

    audit = record_sensitive_action(
        request,
        action="manual_sync",
        status="success",
        details={"results": {"estado_cuenta": True}},
    )

    assert audit is not None
    assert audit.action == "manual_sync"
    assert audit.details["path"] == "/acciones/sync/"


@pytest.mark.django_db
@patch("apps.core.services.security_audit.SensitiveActionAudit.objects.create", side_effect=OperationalError("missing table"))
def test_record_sensitive_action_fails_open_when_audit_table_is_missing(_mock_create):
    user = get_user_model().objects.create_user(username="audit-user-2", password="secret123")
    request = RequestFactory().post("/acciones/sync/")
    request.user = user
    request.META["REMOTE_ADDR"] = "127.0.0.1"

    audit = record_sensitive_action(
        request,
        action="manual_sync",
        status="success",
        details={"results": {"estado_cuenta": True}},
    )

    assert audit is None
