from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventorySupplyRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_supply_list_returns_items(self):
        fake_business = SimpleNamespace(id=1)
        fake_supply = SimpleNamespace(
            id=10,
            business_id=1,
            inventory_item_id=7,
            inventory_item=SimpleNamespace(name="Azucar"),
            product_specific_id=None,
            product_specific=None,
            product_variant="Azucar blanca",
            is_active=True,
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_supplies",
            return_value=[fake_supply],
        ) as list_supplies_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/supply/list"
                "?include_inactive=true"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["inventory_item_name"], "Azucar")
        list_supplies_mock.assert_called_once_with(business_id=1, include_inactive=True)

    def test_supply_create_returns_created_item(self):
        fake_business = SimpleNamespace(id=4)
        fake_supply = SimpleNamespace(
            id=33,
            business_id=4,
            inventory_item_id=8,
            product_specific_id=None,
            product_variant="Harina 000",
            is_active=True,
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_supply",
            return_value=fake_supply,
        ) as create_supply_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/supply/create",
                json={
                    "inventory_item_id": 8,
                    "product_variant": "Harina 000",
                    "is_active": "true",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["id"], 33)
        create_supply_mock.assert_called_once_with(
            business_id=4,
            inventory_item_id=8,
            product_variant="Harina 000",
            product_specific_id=None,
            is_active=True,
        )

    def test_supply_update_returns_updated_item(self):
        fake_business = SimpleNamespace(id=5)
        fake_supply = SimpleNamespace(
            id=44,
            business_id=5,
            inventory_item_id=9,
            product_specific_id=None,
            product_variant="Leche entera",
            is_active=False,
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.update_supply",
            return_value=fake_supply,
        ) as update_supply_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/supply/44/update",
                json={
                    "inventory_item_id": 9,
                    "product_variant": "Leche entera",
                    "is_active": "false",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["is_active"], False)
        update_supply_mock.assert_called_once_with(
            business_id=5,
            supply_id=44,
            inventory_item_id=9,
            product_variant="Leche entera",
            product_specific_id=None,
            is_active=False,
        )

    def test_supply_delete_returns_success_message(self):
        fake_business = SimpleNamespace(id=6)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.delete_supply",
            return_value=None,
        ) as delete_supply_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/supply/77/delete"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("eliminado", payload["message"].lower())
        delete_supply_mock.assert_called_once_with(business_id=6, supply_id=77)


if __name__ == "__main__":
    unittest.main()
