from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryIncomeReportsCrossRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_cross_regression_inventory_income_and_reports_routes(self):
        fake_business = SimpleNamespace(id=21)
        fake_filters = {"business_id": 21, "specific_business_id": None}

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.list_valued_kardex",
            return_value=[
                {
                    "movement_id": 1,
                    "movement_date": None,
                    "inventory_item_id": 10,
                    "inventory_item_name": "Harina",
                    "movement_type": "purchase",
                    "adjustment_kind": None,
                    "quantity": 4.0,
                    "delta_quantity": 4.0,
                    "unit": "kg",
                    "unit_cost": 3.5,
                    "total_cost": None,
                    "amount": 14.0,
                    "delta_value": 14.0,
                    "running_stock": 4.0,
                    "running_value": 14.0,
                    "account_code": "7101",
                    "reference_type": None,
                    "reference_id": None,
                    "document": "FAC-XREG-001",
                }
            ],
        ), patch(
            "app.routes.inventory.inventory_service.summarize_sale_consumption_cost_report",
            return_value=[
                {
                    "sale_id": 1001,
                    "sale_number": "A-1001",
                    "sale_date": None,
                    "movement_count": 2,
                    "consumption_quantity": 2.0,
                    "consumption_cost": 9.0,
                    "reversal_cost": 0.5,
                    "net_consumption_cost": 8.5,
                }
            ],
        ), patch(
            "app.routes.inventory.inventory_service.list_inventory_turnover_coverage",
            return_value=[
                {
                    "inventory_item_id": 10,
                    "inventory_item_name": "Harina",
                    "unit": "kg",
                    "period_start": None,
                    "period_end": None,
                    "period_days": 7,
                    "movement_count": 3,
                    "opening_stock": 10.0,
                    "closing_stock": 6.0,
                    "inbound_quantity": 4.0,
                    "outbound_quantity": 8.0,
                    "average_stock": 8.0,
                    "avg_daily_outbound": 1.14,
                    "turnover_ratio": 1.0,
                    "days_of_coverage": 4.2,
                    "min_stock": 2.0,
                }
            ],
        ), patch(
            "app.routes.inventory.inventory_service.list_stockout_risk_report",
            return_value=[
                {
                    "inventory_item_id": 10,
                    "inventory_item_name": "Harina",
                    "unit": "kg",
                    "closing_stock": 1.0,
                    "avg_daily_outbound": 1.14,
                    "days_of_coverage": 0.87,
                    "min_stock": 2.0,
                    "stockout": False,
                    "risk_of_stockout": True,
                    "min_stock_breach": True,
                    "risk_level": "high",
                }
            ],
        ), patch(
            "app.routes.reports._resolve_business_scope_or_redirect",
            return_value=(fake_business, fake_filters, None),
        ), patch(
            "app.routes.reports.sales_service.get_inventory_consumption",
            return_value={
                "10": {
                    "name": "Harina",
                    "unit": "kg",
                    "total_consumed": 2.0,
                    "product_usages": [],
                }
            },
        ):
            kardex_response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/kardex-valued"
            )
            sale_cost_response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/sale-consumption-cost"
            )
            turnover_response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/turnover-coverage"
            )
            risk_response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/accounting/stockout-risk"
            )
            consumption_response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/report/inventory-consumption",
                json={"month": "2026-03"},
            )

        self.assertEqual(kardex_response.status_code, 200)
        self.assertEqual(sale_cost_response.status_code, 200)
        self.assertEqual(turnover_response.status_code, 200)
        self.assertEqual(risk_response.status_code, 200)
        self.assertEqual(consumption_response.status_code, 200)

        self.assertTrue(kardex_response.get_json()["ok"])
        self.assertEqual(
            kardex_response.get_json()["items"][0]["running_value"],
            14.0,
        )
        self.assertEqual(
            sale_cost_response.get_json()["items"][0]["net_consumption_cost"],
            8.5,
        )
        self.assertEqual(
            turnover_response.get_json()["items"][0]["days_of_coverage"],
            4.2,
        )
        self.assertEqual(risk_response.get_json()["items"][0]["risk_level"], "high")
        self.assertEqual(consumption_response.get_json()["month"], "2026-03")


if __name__ == "__main__":
    unittest.main()
