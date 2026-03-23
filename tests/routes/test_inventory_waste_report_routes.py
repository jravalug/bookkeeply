from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryWasteReportRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_waste_report_returns_items(self):
        fake_business = SimpleNamespace(id=30)
        fake_rows = [
            {
                "inventory_item_id": 10,
                "inventory_item_name": "Arroz",
                "waste_reason": "rotura",
                "events": 2,
                "total_quantity": 3.0,
                "total_amount": 12.0,
                "last_movement_date": None,
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_waste_report",
            return_value=fake_rows,
        ) as report_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/movement/waste-report"
                "?start_date=2026-03-01&end_date=2026-03-09&waste_reason=rotura"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["waste_reason"], "rotura")
        report_mock.assert_called_once()

    def test_waste_report_rejects_invalid_date_format(self):
        fake_business = SimpleNamespace(id=30)
        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ):
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/movement/waste-report"
                "?start_date=09-03-2026"
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("Formato de fecha", payload["message"])


if __name__ == "__main__":
    unittest.main()
