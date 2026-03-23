from datetime import datetime
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows


class _FakeColumn:
    def __eq__(self, other):
        return ("eq", other)

    def __ge__(self, other):
        return ("ge", other)

    def __le__(self, other):
        return ("le", other)

    def desc(self):
        return ("desc",)


class _FakeMovementModel:
    business_id = _FakeColumn()
    movement_type = _FakeColumn()
    inventory_item_id = _FakeColumn()
    waste_reason = _FakeColumn()
    movement_date = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class TestInventoryWasteReportRules(unittest.TestCase):
    def test_list_waste_report_groups_by_item_and_reason(self):
        rows = [
            SimpleNamespace(
                inventory_item_id=10,
                inventory_item=SimpleNamespace(name="Arroz"),
                waste_reason="rotura",
                quantity=2.0,
                total_cost=8.0,
                unit_cost=None,
                movement_date=datetime(2026, 3, 9, 12, 0, 0),
            ),
            SimpleNamespace(
                inventory_item_id=10,
                inventory_item=SimpleNamespace(name="Arroz"),
                waste_reason="rotura",
                quantity=1.0,
                total_cost=4.0,
                unit_cost=None,
                movement_date=datetime(2026, 3, 9, 9, 0, 0),
            ),
            SimpleNamespace(
                inventory_item_id=11,
                inventory_item=SimpleNamespace(name="Leche"),
                waste_reason="caducidad",
                quantity=3.0,
                total_cost=None,
                unit_cost=2.0,
                movement_date=datetime(2026, 3, 8, 10, 0, 0),
            ),
        ]

        fake_model = _FakeMovementModel(rows)
        with patch("app.services.inventory_service.InventoryMovement", fake_model):
            report = InventoryService.list_waste_report(business_id=1)

        self.assertEqual(len(report), 2)
        arroz_row = next(row for row in report if row["inventory_item_id"] == 10)
        self.assertEqual(arroz_row["waste_reason"], "rotura")
        self.assertEqual(arroz_row["events"], 2)
        self.assertEqual(arroz_row["total_quantity"], 3.0)
        self.assertEqual(arroz_row["total_amount"], 12.0)


if __name__ == "__main__":
    unittest.main()
