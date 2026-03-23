from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryPreventiveAlertRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_preventive_alerts_returns_items(self):
        fake_business = SimpleNamespace(id=15)
        fake_alerts = [
            {
                "inventory_item_id": 1,
                "inventory_item_name": "Arroz",
                "usage_type": "sale_direct",
                "stock": 2.0,
                "min_stock": 5.0,
                "low_stock": True,
                "expiration_date": None,
                "expired": False,
                "expiring_soon": False,
                "days_until_expiration": None,
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_inventory_preventive_alerts",
            return_value=fake_alerts,
        ) as alerts_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/alerts/preventive"
                "?days_to_expiration=10&usage_type=sale_direct"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["inventory_item_name"], "Arroz")
        alerts_mock.assert_called_once_with(
            days_to_expiration=10,
            usage_type="sale_direct",
        )

    def test_preventive_alerts_rejects_non_integer_days(self):
        fake_business = SimpleNamespace(id=15)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ):
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/alerts/preventive"
                "?days_to_expiration=abc"
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("days_to_expiration", payload["message"])


if __name__ == "__main__":
    unittest.main()
