from datetime import datetime, date
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


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeInventoryItemModel:
    id = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class _FakeSaleDetailModel:
    id = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class _FakeSaleModel:
    id = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class TestInventoryKardexCostReportsRules(unittest.TestCase):
    def test_list_valued_kardex_builds_running_stock_and_value(self):
        movements = [
            SimpleNamespace(
                id=1,
                movement_date=datetime(2026, 3, 1, 10, 0, 0),
                inventory_item_id=10,
                movement_type="purchase",
                adjustment_kind=None,
                quantity=5.0,
                unit="kg",
                unit_cost=2.0,
                total_cost=None,
                account_code="7101",
                reference_type=None,
                reference_id=None,
                document="FAC-1",
            ),
            SimpleNamespace(
                id=2,
                movement_date=datetime(2026, 3, 1, 11, 0, 0),
                inventory_item_id=10,
                movement_type="consumption",
                adjustment_kind=None,
                quantity=2.0,
                unit="kg",
                unit_cost=2.0,
                total_cost=None,
                account_code="7101",
                reference_type="sale_inventory_line",
                reference_id=101,
                document=None,
            ),
        ]
        item_rows = [SimpleNamespace(id=10, name="Harina")]

        with mock.patch.object(
            InventoryService,
            "list_movements",
            return_value=movements,
        ), mock.patch(
            "app.services.inventory_service.InventoryItem",
            _FakeInventoryItemModel(item_rows),
        ):
            rows = InventoryService.list_valued_kardex(business_id=7)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["running_stock"], 5.0)
        self.assertEqual(rows[0]["running_value"], 10.0)
        self.assertEqual(rows[1]["delta_quantity"], -2.0)
        self.assertEqual(rows[1]["delta_value"], -4.0)
        self.assertEqual(rows[1]["running_stock"], 3.0)
        self.assertEqual(rows[1]["running_value"], 6.0)

    def test_summarize_sale_consumption_cost_report_groups_by_sale(self):
        movements = [
            SimpleNamespace(
                id=10,
                movement_type="consumption",
                adjustment_kind=None,
                quantity=3.0,
                unit_cost=2.0,
                total_cost=None,
                reference_type="sale_inventory_line",
                reference_id=201,
            ),
            SimpleNamespace(
                id=11,
                movement_type="adjustment",
                adjustment_kind="positive",
                quantity=1.0,
                unit_cost=2.0,
                total_cost=None,
                reference_type="sale_inventory_line",
                reference_id=201,
            ),
        ]
        detail_rows = [SimpleNamespace(id=201, sale_id=40)]
        sale_rows = [SimpleNamespace(id=40, sale_number="007", date=date(2026, 3, 2))]

        with mock.patch.object(
            InventoryService,
            "list_movements",
            return_value=movements,
        ), mock.patch(
            "app.services.inventory_service.SaleDetail",
            _FakeSaleDetailModel(detail_rows),
        ), mock.patch(
            "app.services.inventory_service.Sale",
            _FakeSaleModel(sale_rows),
        ):
            rows = InventoryService.summarize_sale_consumption_cost_report(
                business_id=7,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sale_id"], 40)
        self.assertEqual(rows[0]["consumption_quantity"], 3.0)
        self.assertEqual(rows[0]["consumption_cost"], 6.0)
        self.assertEqual(rows[0]["reversal_cost"], 2.0)
        self.assertEqual(rows[0]["net_consumption_cost"], 4.0)


if __name__ == "__main__":
    unittest.main()
