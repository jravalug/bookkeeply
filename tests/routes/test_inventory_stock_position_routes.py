from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryStockPositionRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_stock_position_returns_items(self):
        fake_business = SimpleNamespace(id=15)
        fake_rows = [
            {
                "inventory_item_id": 1,
                "inventory_item_name": "Harina",
                "unit": "kg",
                "stock_available": 10.0,
                "stock_committed": 5.0,
                "stock_virtual": 15.0,
                "stock_committed_sales_floor": 2.0,
                "stock_committed_wip": 3.0,
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_stock_position",
            return_value=fake_rows,
        ) as stock_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/stock/position"
                "?inventory_item_id=1"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["inventory_item_name"], "Harina")
        stock_mock.assert_called_once_with(
            business_id=15,
            inventory_item_id=1,
        )

    def test_stock_position_returns_400_when_service_rejects(self):
        fake_business = SimpleNamespace(id=15)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_stock_position",
            side_effect=ValueError("inventory_item_id debe ser un entero positivo"),
        ):
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/stock/position"
                "?inventory_item_id=0"
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("inventory_item_id", payload["message"])


if __name__ == "__main__":
    unittest.main()
