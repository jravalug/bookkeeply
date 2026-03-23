from datetime import date, timedelta
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.inventory_service import InventoryService


class _FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class _FakeColumn:
    def is_(self, value):
        return ("is", value)

    def __eq__(self, other):
        return ("eq", other)

    def asc(self):
        return ("asc",)


class _FakeInventoryItemModel:
    is_active = _FakeColumn()
    usage_type = _FakeColumn()
    name = _FakeColumn()

    def __init__(self, items):
        self.query = _FakeQuery(items)


class TestInventoryPreventiveAlertRules(unittest.TestCase):
    def test_list_inventory_preventive_alerts_returns_low_stock_and_expiring_items(
        self,
    ):
        today = date.today()
        fake_items = [
            SimpleNamespace(
                id=1,
                name="Arroz",
                usage_type="sale_direct",
                stock=2.0,
                min_stock=5.0,
                expiration_date=None,
            ),
            SimpleNamespace(
                id=2,
                name="Leche",
                usage_type="production_input",
                stock=10.0,
                min_stock=2.0,
                expiration_date=today + timedelta(days=2),
            ),
            SimpleNamespace(
                id=3,
                name="Cafe",
                usage_type="mixed",
                stock=10.0,
                min_stock=2.0,
                expiration_date=None,
            ),
        ]

        fake_model = _FakeInventoryItemModel(fake_items)

        with unittest.mock.patch(
            "app.services.inventory_service.InventoryItem",
            fake_model,
        ):
            alerts = InventoryService.list_inventory_preventive_alerts(
                days_to_expiration=7,
            )

        self.assertEqual(len(alerts), 2)
        self.assertTrue(any(item["low_stock"] for item in alerts))
        self.assertTrue(any(item["expiring_soon"] for item in alerts))

    def test_list_inventory_preventive_alerts_rejects_negative_days(self):
        with self.assertRaises(ValueError):
            InventoryService.list_inventory_preventive_alerts(days_to_expiration=-1)


if __name__ == "__main__":
    unittest.main()
