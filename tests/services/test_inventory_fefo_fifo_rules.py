from datetime import datetime, date
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeColumn:
    def __eq__(self, other):
        return ("eq", other)

    def asc(self):
        return ("asc",)


class _FakeMovementModel:
    business_id = _FakeColumn()
    inventory_item_id = _FakeColumn()
    movement_date = _FakeColumn()
    id = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class TestInventoryFefoFifoRules(unittest.TestCase):
    def test_select_outgoing_lot_context_prioritizes_fefo_then_fifo_tiebreak(self):
        rows = [
            SimpleNamespace(
                id=1,
                business_id=1,
                inventory_item_id=10,
                movement_type="purchase",
                adjustment_kind=None,
                quantity=5.0,
                lot_code="LOT-B",
                lot_date=date(2026, 3, 20),
                inventory_id=101,
                movement_date=datetime(2026, 3, 1, 10, 0, 0),
            ),
            SimpleNamespace(
                id=2,
                business_id=1,
                inventory_item_id=10,
                movement_type="purchase",
                adjustment_kind=None,
                quantity=7.0,
                lot_code="LOT-A",
                lot_date=date(2026, 3, 10),
                inventory_id=102,
                movement_date=datetime(2026, 3, 2, 10, 0, 0),
            ),
        ]

        with unittest.mock.patch(
            "app.services.inventory_service.InventoryMovement",
            _FakeMovementModel(rows),
        ):
            selected = InventoryService._select_outgoing_lot_context(
                business_id=1,
                inventory_item_id=10,
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["valuation_method"], "fefo")
        self.assertEqual(selected["lot_code"], "LOT-A")
        self.assertEqual(selected["inventory_id"], 102)

    def test_select_outgoing_lot_context_uses_fifo_for_non_perishable_without_lot_date(
        self,
    ):
        rows = [
            SimpleNamespace(
                id=10,
                business_id=1,
                inventory_item_id=11,
                movement_type="purchase",
                adjustment_kind=None,
                quantity=3.0,
                lot_code=None,
                lot_date=None,
                inventory_id=201,
                movement_date=datetime(2026, 3, 1, 9, 0, 0),
            ),
            SimpleNamespace(
                id=11,
                business_id=1,
                inventory_item_id=11,
                movement_type="purchase",
                adjustment_kind=None,
                quantity=4.0,
                lot_code=None,
                lot_date=None,
                inventory_id=202,
                movement_date=datetime(2026, 3, 2, 9, 0, 0),
            ),
        ]

        with unittest.mock.patch(
            "app.services.inventory_service.InventoryMovement",
            _FakeMovementModel(rows),
        ):
            selected = InventoryService._select_outgoing_lot_context(
                business_id=1,
                inventory_item_id=11,
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["valuation_method"], "fifo")
        self.assertIsNone(selected["lot_code"])
        self.assertEqual(selected["inventory_id"], 201)


if __name__ == "__main__":
    unittest.main()
