from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryAccountingRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_accounting_ledger_list_returns_items(self):
        fake_business = SimpleNamespace(id=14)
        fake_entries = [
            SimpleNamespace(
                id=1,
                movement_id=100,
                movement_type="purchase",
                destination=None,
                source_bucket="supplier",
                destination_bucket="warehouse",
                source_account_code=None,
                destination_account_code="7101",
                quantity=2.0,
                unit="kg",
                unit_cost=5.0,
                amount=10.0,
                valuation_method="fefo",
                document="FAC-1",
                reference_type="invoice",
                reference_id=20,
                created_at=None,
            )
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_inventory_ledger_entries",
            return_value=fake_entries,
        ):
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/ledger/list"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["amount"], 10.0)

    def test_accounting_mixed_sale_create_accepts_1586_1587(self):
        fake_business = SimpleNamespace(id=15)
        fake_breakdown = SimpleNamespace(
            id=8,
            sale_id=77,
            production_account_code="1586",
            merchandise_account_code="1587",
            production_cost=120.0,
            merchandise_cost=80.0,
        )

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.upsert_sale_cost_breakdown",
            return_value=fake_breakdown,
        ) as upsert_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/mixed-sale/create",
                json={
                    "sale_id": 77,
                    "production_cost": 120,
                    "merchandise_cost": 80,
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["production_account_code"], "1586")
        self.assertEqual(payload["item"]["merchandise_account_code"], "1587")
        upsert_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
