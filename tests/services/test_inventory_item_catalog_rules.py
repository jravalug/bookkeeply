from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import InventoryItem
from app.services.inventory_service import InventoryService


class TestInventoryItemCatalogRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def setUp(self):
        InventoryItem.query.delete()
        db.session.commit()

    def test_create_item_defaults_usage_type_and_active(self):
        item = InventoryService.create_item(name="Harina", unit="kg")

        self.assertEqual(item.usage_type, InventoryItem.USAGE_TYPE_MIXED)
        self.assertTrue(item.is_active)
        self.assertEqual(item.unit, "kg")

    def test_create_item_rejects_invalid_unit(self):
        with self.assertRaises(ValueError):
            InventoryService.create_item(name="Azucar", unit="libra")

    def test_create_item_rejects_normalized_name_duplicate(self):
        InventoryService.create_item(name="Cafe Molido", unit="kg")

        with self.assertRaises(ValueError):
            InventoryService.create_item(name="cafe   molído", unit="kg")

    def test_update_item_allows_usage_type_and_active_changes(self):
        item = InventoryService.create_item(name="Leche", unit="l")

        updated = InventoryService.update_item(
            inventory_item_id=item.id,
            name="Leche Entera",
            unit="l",
            usage_type=InventoryItem.USAGE_TYPE_PRODUCTION_INPUT,
            is_active=False,
        )

        self.assertEqual(updated.name, "Leche Entera")
        self.assertEqual(updated.usage_type, InventoryItem.USAGE_TYPE_PRODUCTION_INPUT)
        self.assertFalse(updated.is_active)


if __name__ == "__main__":
    unittest.main()
