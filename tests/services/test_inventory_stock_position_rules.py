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

    def in_(self, values):
        return ("in", values)

    def asc(self):
        return ("asc",)


class _FakeMovementModel:
    business_id = _FakeColumn()
    inventory_item_id = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class _FakeSalesFloorModel:
    business_id = _FakeColumn()
    inventory_item_id = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class _FakeWipModel:
    business_id = _FakeColumn()
    inventory_item_id = _FakeColumn()
    status = _FakeColumn()
    STATUS_OPEN = "open"

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class _FakeInventoryItemModel:
    id = _FakeColumn()
    name = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeQuery(rows)


class TestInventoryStockPositionRules(unittest.TestCase):
    def test_list_stock_position_aggregates_available_committed_and_virtual(self):
        fake_movements = [
            SimpleNamespace(inventory_item_id=1),
            SimpleNamespace(inventory_item_id=2),
        ]
        fake_sales_floor = [
            SimpleNamespace(inventory_item_id=1, current_quantity=2.5),
            SimpleNamespace(inventory_item_id=1, current_quantity=1.5),
            SimpleNamespace(inventory_item_id=2, current_quantity=4.0),
        ]
        fake_wip = [
            SimpleNamespace(inventory_item_id=1, remaining_quantity=3.0),
            SimpleNamespace(inventory_item_id=2, remaining_quantity=1.0),
        ]
        fake_items = [
            SimpleNamespace(id=1, name="Harina", unit="kg", stock=10.0),
            SimpleNamespace(id=2, name="Leche", unit="l", stock=5.0),
        ]

        with unittest.mock.patch(
            "app.services.inventory_service.InventoryMovement",
            _FakeMovementModel(fake_movements),
        ), unittest.mock.patch(
            "app.services.inventory_service.InventorySalesFloorStock",
            _FakeSalesFloorModel(fake_sales_floor),
        ), unittest.mock.patch(
            "app.services.inventory_service.InventoryWipBalance",
            _FakeWipModel(fake_wip),
        ), unittest.mock.patch(
            "app.services.inventory_service.InventoryItem",
            _FakeInventoryItemModel(fake_items),
        ):
            rows = InventoryService.list_stock_position(business_id=9)

        self.assertEqual(len(rows), 2)

        first = next(item for item in rows if item["inventory_item_id"] == 1)
        self.assertEqual(first["stock_available"], 10.0)
        self.assertEqual(first["stock_committed_sales_floor"], 4.0)
        self.assertEqual(first["stock_committed_wip"], 3.0)
        self.assertEqual(first["stock_committed"], 7.0)
        self.assertEqual(first["stock_virtual"], 17.0)

        second = next(item for item in rows if item["inventory_item_id"] == 2)
        self.assertEqual(second["stock_available"], 5.0)
        self.assertEqual(second["stock_committed_sales_floor"], 4.0)
        self.assertEqual(second["stock_committed_wip"], 1.0)
        self.assertEqual(second["stock_committed"], 5.0)
        self.assertEqual(second["stock_virtual"], 10.0)

    def test_list_stock_position_rejects_non_positive_item_id(self):
        with self.assertRaises(ValueError):
            InventoryService.list_stock_position(business_id=9, inventory_item_id=0)


if __name__ == "__main__":
    unittest.main()
