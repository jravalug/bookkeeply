from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryAccountCatalogRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_account_catalog_list_includes_normative_flag(self):
        fake_business = SimpleNamespace(id=31)
        fake_accounts = [
            SimpleNamespace(id=1, code="1586", name="Produccion", is_normative=True)
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_catalog_accounts",
            return_value=fake_accounts,
        ):
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/account-catalog/list"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["items"][0]["is_normative"])

    def test_account_catalog_update_returns_400_on_normative_edit(self):
        fake_business = SimpleNamespace(id=31)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.update_catalog_account",
            side_effect=ValueError(
                "El nomenclador general es normativo y no permite editar codigo ni nombre"
            ),
        ):
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/account-catalog/update",
                json={
                    "account_code": "1586",
                    "new_code": "1586",
                    "new_name": "Produccion",
                },
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
