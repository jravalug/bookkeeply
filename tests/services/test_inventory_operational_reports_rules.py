from datetime import datetime
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class _FakeColumn:
    def in_(self, values):
        return ("in", values)

    def asc(self):
        return ("asc",)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeItemModel:
    id = _FakeColumn()
    name = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class TestInventoryOperationalReportsRules(unittest.TestCase):
    def test_turnover_coverage_builds_metrics(self):
        movements = [
            SimpleNamespace(
                inventory_item_id=10,
                movement_type="purchase",
                adjustment_kind=None,
                quantity=20.0,
            ),
            SimpleNamespace(
                inventory_item_id=10,
                movement_type="consumption",
                adjustment_kind=None,
                quantity=8.0,
            ),
        ]
        items = [
            SimpleNamespace(id=10, name="Harina", unit="kg", stock=12.0, min_stock=5.0)
        ]

        with mock.patch.object(
            InventoryService,
            "list_movements",
            return_value=movements,
        ), mock.patch(
            "app.services.inventory_service.InventoryItem",
            _FakeItemModel(items),
        ):
            rows = InventoryService.list_inventory_turnover_coverage(
                business_id=9,
                start_date=datetime(2026, 3, 1),
                end_date=datetime(2026, 3, 10),
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["opening_stock"], 0.0)
        self.assertEqual(rows[0]["closing_stock"], 12.0)
        self.assertEqual(rows[0]["outbound_quantity"], 8.0)
        self.assertIsNotNone(rows[0]["days_of_coverage"])

    def test_stockout_risk_filters_only_relevant_items(self):
        base_rows = [
            {
                "inventory_item_id": 1,
                "inventory_item_name": "A",
                "unit": "kg",
                "closing_stock": 0.0,
                "avg_daily_outbound": 1.0,
                "days_of_coverage": 0.0,
                "min_stock": 2.0,
            },
            {
                "inventory_item_id": 2,
                "inventory_item_name": "B",
                "unit": "kg",
                "closing_stock": 100.0,
                "avg_daily_outbound": 1.0,
                "days_of_coverage": 100.0,
                "min_stock": 10.0,
            },
        ]

        with mock.patch.object(
            InventoryService,
            "list_inventory_turnover_coverage",
            return_value=base_rows,
        ):
            rows = InventoryService.list_stockout_risk_report(business_id=9)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["inventory_item_id"], 1)
        self.assertTrue(rows[0]["stockout"])


if __name__ == "__main__":
    unittest.main()
