import pytest
from django.urls import resolve, reverse


@pytest.mark.parametrize(
    ("path", "url_name", "namespace"),
    [
        ("/health/", None, ""),
        ("/health/full", None, ""),
        ("/token/", "token_obtain_pair", ""),
        ("/token/refresh/", "token_refresh", ""),
        ("/register/clients/", "client-list", ""),
        ("/register/clients-basic/", "client-basic-list", ""),
        ("/register/professionals/", "professional-list", ""),
        ("/register/auth/professional-create/", None, ""),
        ("/agenda/appointments/", "appointment-list", ""),
        ("/inventory/suppliers/", "supplier-list", ""),
        ("/clinic/treatment/plans/", "odonto-plan-list", ""),
        (
            "/api/v1/auth/bakery/login/admin/",
            "bakery_admin_login",
            "",
        ),
        (
            "/api/v1/auth/bakery/login/customer/",
            "bakery_customer_login",
            "",
        ),
        ("/api/v1/bakery/customers/", "customer-list", "bakery"),
        ("/api/v1/bakery/products/", "product-list", "bakery"),
        ("/api/v1/bakery/orders/", "order-list", "bakery"),
        ("/api/v1/bakery/ledger-entries/", "ledger-entry-list", "bakery"),
        ("/api/v1/bakery/tenant/identity/", "tenant-identity", "bakery"),
        ("/api/v1/bakery/tenant/profile/", "tenant-profile", "bakery"),
    ],
)
def test_critical_paths_keep_their_url_contract(path, url_name, namespace):
    match = resolve(path)

    assert match.url_name == url_name
    assert match.namespace == namespace


@pytest.mark.parametrize(
    ("route_name", "expected_path"),
    [
        ("token_obtain_pair", "/token/"),
        ("token_refresh", "/token/refresh/"),
        ("client-list", "/register/clients/"),
        ("client-basic-list", "/register/clients-basic/"),
        ("professional-list", "/register/professionals/"),
        ("appointment-list", "/agenda/appointments/"),
        ("supplier-list", "/inventory/suppliers/"),
        ("odonto-plan-list", "/clinic/treatment/plans/"),
        ("bakery_admin_login", "/api/v1/auth/bakery/login/admin/"),
        ("bakery_customer_login", "/api/v1/auth/bakery/login/customer/"),
        ("bakery:customer-list", "/api/v1/bakery/customers/"),
        ("bakery:tenant-profile", "/api/v1/bakery/tenant/profile/"),
    ],
)
def test_critical_route_names_keep_their_paths(route_name, expected_path):
    assert reverse(route_name) == expected_path
