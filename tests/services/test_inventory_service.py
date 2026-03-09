from datetime import datetime
from types import SimpleNamespace
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class FakeQuery:
    def __init__(self, result):
        self.result = result
        self.filter_calls = []
        self.order_by_calls = []

    def filter(self, *conditions):
        self.filter_calls.append(conditions)
        return self

    def order_by(self, *ordering):
        self.order_by_calls.append(ordering)
        return self

    def all(self):
        return self.result


class FakeWipModel:
    STATUS_OPEN = "open"
    STATUS_FINISHED = "finished"
    STATUS_WASTE = "waste"

    def __init__(self, wip_balance):
        self.query = SimpleNamespace(get_or_404=lambda _id: wip_balance)


class FakeColumn:
    def __eq__(self, other):
        return ("eq", other)

    def __ge__(self, other):
        return ("ge", other)

    def __le__(self, other):
        return ("le", other)

    def desc(self):
        return ("desc",)


class FakeMovementModel:
    business_id = FakeColumn()
    inventory_item_id = FakeColumn()
    movement_date = FakeColumn()

    def __init__(self, query):
        self.query = query


class TestInventoryService(unittest.TestCase):
    def test_consume_wip_balance_partial_keeps_open_status(self):
        wip_balance = SimpleNamespace(
            id=10,
            business_id=1,
            status=FakeWipModel.STATUS_OPEN,
            remaining_quantity=12.0,
        )
        fake_wip_model = FakeWipModel(wip_balance)

        with patch(
            "app.services.inventory_service.InventoryWipBalance",
            fake_wip_model,
        ), patch("app.services.inventory_service.db.session.commit") as commit_mock:
            result = InventoryService.consume_wip_balance(
                business_id=1,
                wip_balance_id=10,
                consumed_quantity=4,
            )

        self.assertEqual(result.remaining_quantity, 8.0)
        self.assertEqual(result.status, FakeWipModel.STATUS_OPEN)
        commit_mock.assert_called_once()

    def test_mark_wip_waste_sets_status_and_remaining_to_zero(self):
        wip_balance = SimpleNamespace(
            id=11,
            business_id=2,
            status=FakeWipModel.STATUS_OPEN,
            remaining_quantity=3.5,
            notes=None,
        )
        fake_wip_model = FakeWipModel(wip_balance)

        with patch(
            "app.services.inventory_service.InventoryWipBalance",
            fake_wip_model,
        ), patch("app.services.inventory_service.db.session.commit") as commit_mock:
            result = InventoryService.mark_wip_waste(
                business_id=2,
                wip_balance_id=11,
                notes="Merma por derrame",
            )

        self.assertEqual(result.status, FakeWipModel.STATUS_WASTE)
        self.assertEqual(result.remaining_quantity, 0.0)
        self.assertEqual(result.notes, "Merma por derrame")
        commit_mock.assert_called_once()

    def test_finish_wip_balance_registers_wip_close_movement(self):
        wip_balance = SimpleNamespace(
            id=55,
            business_id=3,
            inventory_item_id=99,
            status=FakeWipModel.STATUS_OPEN,
            remaining_quantity=7.0,
            unit="kg",
            notes=None,
        )
        fake_wip_model = FakeWipModel(wip_balance)

        with patch(
            "app.services.inventory_service.InventoryWipBalance",
            fake_wip_model,
        ), patch(
            "app.services.inventory_service.InventoryService.create_movement"
        ) as create_movement_mock, patch(
            "app.services.inventory_service.db.session.commit"
        ) as commit_mock:
            result = InventoryService.finish_wip_balance(
                business_id=3,
                wip_balance_id=55,
                account_code="7101",
                notes="Cierre de lote",
            )

        create_movement_mock.assert_called_once_with(
            business_id=3,
            inventory_item_id=99,
            movement_type="wip_close",
            destination="finished_goods",
            quantity=7.0,
            unit="kg",
            account_code="7101",
            reference_type="wip_balance",
            reference_id=55,
            notes="Cierre de lote",
        )
        self.assertEqual(result.status, FakeWipModel.STATUS_FINISHED)
        self.assertEqual(result.remaining_quantity, 0.0)
        self.assertEqual(result.notes, "Cierre de lote")
        commit_mock.assert_called_once()

    def test_list_movements_applies_item_and_date_filters(self):
        fake_result = [MagicMock(id=1)]
        fake_query = FakeQuery(fake_result)
        fake_movement_model = FakeMovementModel(fake_query)

        with patch(
            "app.services.inventory_service.InventoryMovement",
            fake_movement_model,
        ):
            result = InventoryService.list_movements(
                business_id=5,
                inventory_item_id=42,
                start_date=datetime(2026, 3, 1),
                end_date=datetime(2026, 3, 31),
            )

        self.assertEqual(result, fake_result)
        self.assertEqual(len(fake_query.filter_calls), 4)
        self.assertEqual(len(fake_query.order_by_calls), 1)


if __name__ == "__main__":
    unittest.main()
