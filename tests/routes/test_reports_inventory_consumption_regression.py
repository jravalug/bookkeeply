from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryConsumptionRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_inventory_consumption_endpoint_returns_payload(self):
        fake_business = SimpleNamespace(id=1)
        fake_filters = {"business_id": 1, "specific_business_id": None}
        fake_consumption = {
            "7": {
                "name": "Harina",
                "unit": "kg",
                "total_consumed": 3.5,
                "product_usages": [],
            }
        }

        with patch(
            "app.routes.reports._resolve_business_scope_or_redirect",
            return_value=(fake_business, fake_filters, None),
        ), patch(
            "app.routes.reports.sales_service.get_inventory_consumption",
            return_value=fake_consumption,
        ) as consumption_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/report/inventory-consumption",
                json={"month": "2026-03"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["month"], "2026-03")
        self.assertEqual(payload["consumption"], fake_consumption)
        consumption_mock.assert_called_once_with("2026-03", 1, None)

    def test_inventory_consumption_requires_month(self):
        fake_business = SimpleNamespace(id=1)
        fake_filters = {"business_id": 1, "specific_business_id": None}

        with patch(
            "app.routes.reports._resolve_business_scope_or_redirect",
            return_value=(fake_business, fake_filters, None),
        ):
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/report/inventory-consumption",
                json={},
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn("month", payload["error"].lower())


if __name__ == "__main__":
    unittest.main()
