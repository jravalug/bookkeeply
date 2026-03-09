from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import Business, InventoryItem, InventoryProductSpecific, Supply
from app.services.inventory_service import InventoryService


class TestInventoryCatalogStructure(unittest.TestCase):
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
        Supply.query.delete()
        InventoryProductSpecific.query.delete()
        db.session.execute(db.text("DELETE FROM inventory_product_generic"))
        InventoryItem.query.delete()
        Business.query.delete()
        db.session.commit()

    def test_create_generic_and_specific_catalog(self):
        generic = InventoryService.create_product_generic("Granos")
        specific = InventoryService.create_product_specific(generic.id, "Arroz")

        self.assertEqual(specific.generic_id, generic.id)
        self.assertEqual(specific.generic.name, "Granos")

    def test_supply_links_to_specific_and_keeps_surtido_unique_per_business(self):
        business = Business(name="Negocio Catalogo")
        item = InventoryItem(name="Item Base", unit="kg")
        db.session.add_all([business, item])
        db.session.commit()

        generic = InventoryService.create_product_generic("Lacteos")
        specific = InventoryService.create_product_specific(generic.id, "Leche")

        first_supply = InventoryService.create_supply(
            business_id=business.id,
            inventory_item_id=item.id,
            product_variant="Leche Entera 1L",
            product_specific_id=specific.id,
            is_active=True,
        )
        self.assertEqual(first_supply.product_specific_id, specific.id)

        with self.assertRaises(ValueError):
            InventoryService.create_supply(
                business_id=business.id,
                inventory_item_id=item.id,
                product_variant="Leche Entera 1L",
                product_specific_id=specific.id,
                is_active=True,
            )


if __name__ == "__main__":
    unittest.main()
