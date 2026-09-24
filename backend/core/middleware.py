import time
import logging
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger('performance')


class DatabaseTimingCollector:
    def __init__(self):
        self.duration_ms = 0.0
        self.query_count = 0

    def __call__(self, execute, sql, params, many, context):
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.duration_ms += (time.perf_counter() - start) * 1000
            self.query_count += 1


class QueryTimingMiddleware:
    """Mede tempo da requisição e loga se ultrapassar limiar.

    Configurável via env: SLOW_REQUEST_THRESHOLD_MS (default 500ms)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.threshold_ms = int(getattr(settings, 'SLOW_REQUEST_THRESHOLD_MS', 500))

    def __call__(self, request):
        start = time.perf_counter()
        collector = None
        if getattr(settings, 'PERFORMANCE_DIAGNOSTICS_ENABLED', False):
            collector = DatabaseTimingCollector()
            with connection.execute_wrapper(collector):
                response = self.get_response(request)
        else:
            response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > self.threshold_ms:
            if collector is None:
                logger.info("SLOW %sms %s %s", int(elapsed_ms), request.method, request.path)
            else:
                logger.info(
                    "SLOW %sms %s %s db=%sms queries=%s",
                    int(elapsed_ms),
                    request.method,
                    request.path,
                    int(collector.duration_ms),
                    collector.query_count,
                )
        return response


class VersionHeaderMiddleware:
    """Anexa o cabeçalho X-App-Version em todas as respostas para facilitar
    depuração entre frontend e backend, especialmente em ambientes de staging.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        version = getattr(settings, 'APP_VERSION', 'dev')
        response.headers["X-App-Version"] = version
        return response


class OnlineMutationLockMiddleware:
    """Bloqueia mutações destrutivas em ambientes online quando ativado por env.

    O objetivo é permitir criação para testes, preservando os dados reais ao
    impedir PUT/PATCH/DELETE na API.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'ONLINE_MUTATION_LOCK_ENABLED', False):
            blocked_methods = set(getattr(settings, 'ONLINE_MUTATION_LOCK_METHODS', []))
            if request.method.upper() in blocked_methods and self._is_api_path(request.path):
                return JsonResponse(
                    {
                        'detail': (
                            'Ambiente online protegido: atualizacoes e exclusoes estao '
                            'temporariamente bloqueadas.'
                        )
                    },
                    status=423,
                )
        return self.get_response(request)

    @staticmethod
    def _is_api_path(path: str) -> bool:
        prefixes = (
            '/register/',
            '/agenda/',
            '/inventory/',
            '/anamnesis/',
            '/clinic/treatment/',
            '/api/v1/bakery/',
            '/sessions/',
            '/token/',
        )
        return path.startswith(prefixes)
