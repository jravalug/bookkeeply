from pathlib import Path
import sys
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import ANY, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryWipRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_wip_finish_accepts_produced_product_id(self):
        fake_business = SimpleNamespace(id=15)
        fake_balance = SimpleNamespace(
            id=20,
            remaining_quantity=0.0,
            status="finished",
            produced_product_id=11,
            can_be_subproduct=True,
            finished_location="sales_floor",
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.finish_wip_balance",
            return_value=fake_balance,
        ) as finish_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/wip/20/finish",
                json={"account_code": "7101", "produced_product_id": 11},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["produced_product_id"], 11)
        self.assertEqual(payload["item"]["finished_location"], "sales_floor")
        finish_mock.assert_called_once_with(
            business_id=15,
            wip_balance_id=20,
            account_code="7101",
            produced_product_id=11,
            notes=None,
        )

    def test_wip_mark_subproduct_returns_state(self):
        fake_business = SimpleNamespace(id=16)
        fake_balance = SimpleNamespace(
            id=30,
            can_be_subproduct=True,
            status="open",
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.mark_wip_as_subproduct",
            return_value=fake_balance,
        ) as mark_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/wip/30/mark-subproduct",
                json={"can_be_subproduct": "true"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["item"]["can_be_subproduct"])
        mark_mock.assert_called_once_with(
            business_id=16,
            wip_balance_id=30,
            can_be_subproduct=True,
        )

    def test_wip_create_accepts_expiration_date(self):
        fake_business = SimpleNamespace(id=18)
        fake_balance = SimpleNamespace(
            id=41,
            inventory_item_id=7,
            quantity=3.0,
            remaining_quantity=3.0,
            unit="kg",
            status="open",
            can_be_subproduct=False,
            finished_location="finished_goods",
            expiration_date=date(2026, 5, 30),
            expiration_source="manual",
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_wip_balance",
            return_value=fake_balance,
        ) as create_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/wip/create",
                json={
                    "inventory_item_id": 7,
                    "quantity": 3,
                    "unit": "kg",
                    "account_code": "7101",
                    "expiration_date": "2026-05-30",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["expiration_source"], "manual")
        create_mock.assert_called_once_with(
            business_id=18,
            inventory_item_id=7,
            quantity=3.0,
            unit="kg",
            account_code="7101",
            source_inventory_id=None,
            expiration_date=ANY,
            can_be_subproduct=False,
            notes=None,
        )


if __name__ == "__main__":
    unittest.main()
