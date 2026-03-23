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


class _FakeBusinessQuery:
    def __init__(self, business):
        self._business = business

    def get(self, _business_id):
        return self._business


class _FakeInventoryItemQuery:
    def __init__(self, rows):
        self._rows = rows
        self._rows_by_id = {int(row.id): row for row in rows}

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows

    def get(self, item_id):
        return self._rows_by_id.get(int(item_id))


class _FakeInventoryItemModel:
    id = _FakeColumn()
    name = _FakeColumn()

    def __init__(self, rows):
        self.query = _FakeInventoryItemQuery(rows)


class TestInventoryRebuildHistoryRules(unittest.TestCase):
    def test_validate_stock_consistency_detects_mismatch_and_negative_balance(self):
        movements = [
            SimpleNamespace(
                id=1,
                inventory_item_id=11,
                movement_type="purchase",
                quantity=3.0,
                adjustment_kind=None,
                movement_date=None,
            ),
            SimpleNamespace(
                id=2,
                inventory_item_id=11,
                movement_type="consumption",
                quantity=5.0,
                adjustment_kind=None,
                movement_date=None,
            ),
        ]
        items = [SimpleNamespace(id=11, name="Harina", stock=1.0)]

        with mock.patch(
            "app.services.inventory_service.Business",
            SimpleNamespace(query=_FakeBusinessQuery(SimpleNamespace(id=9))),
        ), mock.patch(
            "app.services.inventory_service.InventoryItem",
            _FakeInventoryItemModel(items),
        ), mock.patch.object(
            InventoryService,
            "list_movements",
            return_value=movements,
        ):
            result = InventoryService.validate_stock_consistency_from_history(
                business_id=9
            )

        self.assertEqual(result["mismatch_count"], 1)
        self.assertEqual(result["negative_balance_issue_count"], 1)
        self.assertFalse(result["is_consistent"])
        self.assertEqual(result["mismatches"][0]["expected_stock"], -2.0)

    def test_rebuild_stock_from_history_dry_run_reports_updates_without_commit(self):
        movements = [
            SimpleNamespace(
                id=10,
                inventory_item_id=5,
                movement_type="purchase",
                quantity=7.0,
                adjustment_kind=None,
                movement_date=None,
            )
        ]
        items = [SimpleNamespace(id=5, name="Leche", stock=0.0)]

        with mock.patch(
            "app.services.inventory_service.Business",
            SimpleNamespace(query=_FakeBusinessQuery(SimpleNamespace(id=9))),
        ), mock.patch(
            "app.services.inventory_service.InventoryItem",
            _FakeInventoryItemModel(items),
        ), mock.patch.object(
            InventoryService,
            "list_movements",
            return_value=movements,
        ), mock.patch(
            "app.services.inventory_service.db.session.commit"
        ) as commit_mock:
            result = InventoryService.rebuild_stock_from_history(
                business_id=9,
                commit=False,
            )

        self.assertEqual(result["updated_count"], 1)
        self.assertFalse(result["commit_applied"])
        self.assertEqual(items[0].stock, 0.0)
        commit_mock.assert_not_called()

    def test_rebuild_stock_from_history_apply_updates_item_and_commits(self):
        movements = [
            SimpleNamespace(
                id=20,
                inventory_item_id=8,
                movement_type="purchase",
                quantity=10.0,
                adjustment_kind=None,
                movement_date=None,
            ),
            SimpleNamespace(
                id=21,
                inventory_item_id=8,
                movement_type="consumption",
                quantity=2.0,
                adjustment_kind=None,
                movement_date=None,
            ),
        ]
        items = [SimpleNamespace(id=8, name="Queso", stock=1.0)]

        with mock.patch(
            "app.services.inventory_service.Business",
            SimpleNamespace(query=_FakeBusinessQuery(SimpleNamespace(id=9))),
        ), mock.patch(
            "app.services.inventory_service.InventoryItem",
            _FakeInventoryItemModel(items),
        ), mock.patch.object(
            InventoryService,
            "list_movements",
            return_value=movements,
        ), mock.patch(
            "app.services.inventory_service.db.session.commit"
        ) as commit_mock:
            result = InventoryService.rebuild_stock_from_history(
                business_id=9,
                commit=True,
            )

        self.assertEqual(result["updated_count"], 1)
        self.assertTrue(result["commit_applied"])
        self.assertEqual(items[0].stock, 8.0)
        commit_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
