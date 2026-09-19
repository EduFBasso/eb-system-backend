from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Paginacao padrao para endpoints operacionais."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class LargeResultsSetPagination(PageNumberPagination):
    """Paginacao para exportacoes e listagens administrativas maiores."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500