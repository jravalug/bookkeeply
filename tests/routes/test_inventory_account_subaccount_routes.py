from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryAccountSubaccountRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_create_subaccount_route_returns_created_item(self):
        fake_business = SimpleNamespace(id=20)
        fake_subaccount = SimpleNamespace(
            id=88,
            business_account_adoption_id=31,
            code="11005",
            name="Subcuenta demo",
            is_active=True,
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_business_subaccount",
            return_value=fake_subaccount,
        ) as create_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/account-subaccount/create",
                json={
                    "account_code": "7101",
                    "code": "11005",
                    "name": "Subcuenta demo",
                    "actor": "tester",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["code"], "11005")
        create_mock.assert_called_once_with(
            business_id=20,
            account_code="7101",
            code="11005",
            name="Subcuenta demo",
            actor="tester",
            source="inventory_api",
            template_subaccount_id=None,
        )

    def test_list_subaccount_route_returns_400_on_validation_error(self):
        fake_business = SimpleNamespace(id=21)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_business_subaccounts",
            side_effect=ValueError("La cuenta no esta adoptada en este negocio"),
        ):
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/account-subaccount/list?account_code=9999"
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])

    def test_update_subaccount_route_parses_boolean(self):
        fake_business = SimpleNamespace(id=22)
        fake_subaccount = SimpleNamespace(
            id=77,
            business_account_adoption_id=40,
            code="11006",
            name="Subcuenta editada",
            is_active=False,
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.update_business_subaccount",
            return_value=fake_subaccount,
        ) as update_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/account-subaccount/77/update",
                json={
                    "name": "Subcuenta editada",
                    "is_active": "false",
                    "actor": "tester",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["item"]["is_active"])
        update_mock.assert_called_once_with(
            business_id=22,
            business_sub_account_id=77,
            code=None,
            name="Subcuenta editada",
            is_active=False,
            actor="tester",
            source="inventory_api",
        )


if __name__ == "__main__":
    unittest.main()
