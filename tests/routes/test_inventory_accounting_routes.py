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

    def test_accounting_kardex_valued_returns_items(self):
        fake_business = SimpleNamespace(id=15)
        fake_rows = [
            {
                "movement_id": 1,
                "movement_date": None,
                "inventory_item_id": 10,
                "inventory_item_name": "Harina",
                "movement_type": "purchase",
                "adjustment_kind": None,
                "quantity": 5.0,
                "delta_quantity": 5.0,
                "unit": "kg",
                "unit_cost": 2.0,
                "total_cost": None,
                "amount": 10.0,
                "delta_value": 10.0,
                "running_stock": 5.0,
                "running_value": 10.0,
                "account_code": "7101",
                "reference_type": None,
                "reference_id": None,
                "document": "FAC-1",
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_valued_kardex",
            return_value=fake_rows,
        ) as report_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/kardex-valued"
                "?start_date=2026-03-01&end_date=2026-03-09&inventory_item_id=10"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["running_value"], 10.0)
        report_mock.assert_called_once()

    def test_accounting_sale_consumption_cost_returns_items(self):
        fake_business = SimpleNamespace(id=15)
        fake_rows = [
            {
                "sale_id": 40,
                "sale_number": "007",
                "sale_date": None,
                "movement_count": 2,
                "consumption_quantity": 3.0,
                "consumption_cost": 6.0,
                "reversal_cost": 2.0,
                "net_consumption_cost": 4.0,
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.summarize_sale_consumption_cost_report",
            return_value=fake_rows,
        ) as report_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/sale-consumption-cost"
                "?start_date=2026-03-01&end_date=2026-03-09&sale_id=40"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["net_consumption_cost"], 4.0)
        report_mock.assert_called_once()

    def test_accounting_turnover_coverage_returns_items(self):
        fake_business = SimpleNamespace(id=15)
        fake_rows = [
            {
                "inventory_item_id": 10,
                "inventory_item_name": "Harina",
                "unit": "kg",
                "period_start": None,
                "period_end": None,
                "period_days": 10,
                "movement_count": 2,
                "opening_stock": 0.0,
                "closing_stock": 12.0,
                "inbound_quantity": 20.0,
                "outbound_quantity": 8.0,
                "average_stock": 6.0,
                "avg_daily_outbound": 0.8,
                "turnover_ratio": 1.3333,
                "days_of_coverage": 15.0,
                "min_stock": 5.0,
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_inventory_turnover_coverage",
            return_value=fake_rows,
        ) as report_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/turnover-coverage"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["items"][0]["outbound_quantity"], 8.0)
        report_mock.assert_called_once()

    def test_accounting_stockout_risk_returns_items(self):
        fake_business = SimpleNamespace(id=15)
        fake_rows = [
            {
                "inventory_item_id": 10,
                "inventory_item_name": "Harina",
                "unit": "kg",
                "closing_stock": 0.0,
                "avg_daily_outbound": 0.8,
                "days_of_coverage": 0.0,
                "min_stock": 5.0,
                "stockout": True,
                "risk_of_stockout": True,
                "min_stock_breach": True,
                "risk_level": "critical",
            }
        ]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_stockout_risk_report",
            return_value=fake_rows,
        ) as report_mock:
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/stockout-risk"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["items"][0]["stockout"])
        report_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
