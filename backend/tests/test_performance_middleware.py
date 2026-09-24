from unittest.mock import patch

import pytest
from django.http import JsonResponse
from django.test import RequestFactory, override_settings

from apps.authentication.models import Tenant
from core.middleware import QueryTimingMiddleware


@pytest.mark.django_db
@override_settings(PERFORMANCE_DIAGNOSTICS_ENABLED=True, SLOW_REQUEST_THRESHOLD_MS=0)
def test_slow_request_log_includes_database_summary():
    def get_response(_request):
        Tenant.objects.count()
        return JsonResponse({'status': 'ok'})

    middleware = QueryTimingMiddleware(get_response)

    with patch('core.middleware.logger.info') as log_info:
        response = middleware(RequestFactory().get('/performance-test/'))

    assert response.status_code == 200
    log_info.assert_called_once()
    message, elapsed_ms, method, path, db_duration_ms, query_count = log_info.call_args.args
    assert message == 'SLOW %sms %s %s db=%sms queries=%s'
    assert elapsed_ms >= 0
    assert method == 'GET'
    assert path == '/performance-test/'
    assert db_duration_ms >= 0
    assert query_count == 1