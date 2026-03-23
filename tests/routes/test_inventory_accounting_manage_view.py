from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryAccountingManageView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_accounting_manage_get_renders_view(self):
        fake_client = SimpleNamespace(
            slug="cliente-demo",
            name="Cliente Demo",
            client_type="juridico",
            accounting_regime="fiscal",
            businesses=SimpleNamespace(all=lambda: []),
        )
        fake_business = SimpleNamespace(
            id=50,
            slug="negocio-demo",
            name="Negocio Demo",
            logo=None,
            is_general=True,
            parent_business=None,
            client=fake_client,
        )
        fake_account = SimpleNamespace(
            code="1586", name="Produccion", is_normative=True
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_catalog_accounts",
            return_value=[fake_account],
        ), patch(
            "app.routes.inventory.inventory_service.list_account_adoptions",
            return_value=[],
        ), patch(
            "app.routes.inventory.inventory_service.list_account_adoption_audits",
            return_value=[],
        ):
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/manage"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Contabilidad de Inventario", response.data)

    def test_accounting_manage_post_adopt_calls_service(self):
        fake_client = SimpleNamespace(
            slug="cliente-demo",
            name="Cliente Demo",
            client_type="juridico",
            accounting_regime="fiscal",
            businesses=SimpleNamespace(all=lambda: []),
        )
        fake_business = SimpleNamespace(
            id=51,
            slug="negocio-demo",
            name="Negocio Demo",
            logo=None,
            is_general=True,
            parent_business=None,
            client=fake_client,
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.adopt_account_by_code"
        ) as adopt_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/manage",
                data={"action": "adopt", "account_code": "1586", "actor": "tester"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        adopt_mock.assert_called_once_with(
            business_id=51,
            account_code="1586",
            actor="tester",
            source="inventory_ui",
        )

    def test_accounting_manage_post_htmx_returns_partial_content(self):
        fake_client = SimpleNamespace(
            slug="cliente-demo",
            name="Cliente Demo",
            client_type="juridico",
            accounting_regime="fiscal",
            businesses=SimpleNamespace(all=lambda: []),
        )
        fake_business = SimpleNamespace(
            id=52,
            slug="negocio-demo",
            name="Negocio Demo",
            logo=None,
            is_general=True,
            parent_business=None,
            client=fake_client,
        )
        fake_account = SimpleNamespace(
            code="1586", name="Produccion", is_normative=True
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.adopt_account_by_code"
        ) as adopt_mock, patch(
            "app.routes.inventory.inventory_service.list_catalog_accounts",
            return_value=[fake_account],
        ), patch(
            "app.routes.inventory.inventory_service.list_account_adoptions",
            return_value=[],
        ), patch(
            "app.routes.inventory.inventory_service.list_account_adoption_audits",
            return_value=[],
        ):
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/manage",
                data={"action": "adopt", "account_code": "1586", "actor": "tester"},
                headers={"HX-Request": "true"},
            )

        self.assertEqual(response.status_code, 200)
        adopt_mock.assert_called_once_with(
            business_id=52,
            account_code="1586",
            actor="tester",
            source="inventory_ui",
        )
        self.assertIn(b'id="inventory-accounting-content"', response.data)
        self.assertIn(b"Cuenta adoptada correctamente", response.data)


if __name__ == "__main__":
    unittest.main()
