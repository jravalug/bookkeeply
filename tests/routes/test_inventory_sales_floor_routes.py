from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventorySalesFloorRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_sales_floor_configure_returns_item(self):
        fake_business = SimpleNamespace(id=10)
        fake_item = SimpleNamespace(
            id=1,
            business_id=10,
            inventory_item_id=5,
            current_quantity=0.0,
            min_quantity=2.0,
            max_quantity=8.0,
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.configure_sales_floor_stock",
            return_value=fake_item,
        ) as configure_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/sales-floor/configure",
                json={"inventory_item_id": 5, "min_quantity": 2, "max_quantity": 8},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["min_quantity"], 2.0)
        configure_mock.assert_called_once_with(
            business_id=10,
            inventory_item_id=5,
            min_quantity=2.0,
            max_quantity=8.0,
        )

    def test_sales_floor_transfer_returns_created_payload(self):
        fake_business = SimpleNamespace(id=11)
        fake_movement = SimpleNamespace(
            id=44,
            movement_type="transfer",
            destination="sales_floor",
            inventory_item_id=6,
            quantity=3.0,
            unit="kg",
            lot_code="L-01",
        )
        fake_stock = SimpleNamespace(current_quantity=5.0)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.transfer_to_sales_floor",
            return_value=(fake_movement, fake_stock),
        ) as transfer_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/sales-floor/transfer",
                json={
                    "inventory_item_id": 6,
                    "quantity": 3,
                    "unit": "kg",
                    "account_code": "7101",
                    "lot_code": "L-01",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["destination"], "sales_floor")
        transfer_mock.assert_called_once_with(
            business_id=11,
            inventory_item_id=6,
            quantity=3.0,
            unit="kg",
            account_code="7101",
            lot_code="L-01",
            notes=None,
        )

    def test_sales_floor_alerts_returns_items(self):
        fake_business = SimpleNamespace(id=12)
        fake_alerts = [
            {
                "inventory_item_id": 3,
                "low_stock": True,
                "suggestion_to_max": 5.0,
                "suggestion_by_avg_7_days": 2.0,
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_sales_floor_alerts",
            return_value=fake_alerts,
        ) as alerts_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/sales-floor/alerts"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["items"]), 1)
        alerts_mock.assert_called_once_with(business_id=12)


if __name__ == "__main__":
    unittest.main()
