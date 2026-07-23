import time
import logging
from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger('performance')

class QueryTimingMiddleware:
    """Mede tempo da requisição e loga se ultrapassar limiar.

    Configurável via env: SLOW_REQUEST_THRESHOLD_MS (default 500ms)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.threshold_ms = int(getattr(settings, 'SLOW_REQUEST_THRESHOLD_MS', 500))

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > self.threshold_ms:
            logger.info("SLOW %sms %s %s", int(elapsed_ms), request.method, request.path)
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
            '/odonto/',
            '/sessions/',
            '/token/',
        )
        return path.startswith(prefixes)
