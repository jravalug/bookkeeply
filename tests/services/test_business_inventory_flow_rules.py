from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import Business
from app.services.business_service import BusinessService


class TestBusinessInventoryFlowRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()
        cls.service = BusinessService()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def setUp(self):
        Business.query.delete()
        db.session.commit()

    def test_create_business_enables_wip_by_default_for_restaurant(self):
        business = self.service.create_business(
            name="Resto Demo",
            business_activity=Business.ACTIVITY_RESTAURANT,
        )

        self.assertTrue(business.inventory_flow_sales_floor_enabled)
        self.assertTrue(business.inventory_flow_wip_enabled)

    def test_create_business_keeps_wip_disabled_for_retail(self):
        business = self.service.create_business(
            name="Tienda Demo",
            business_activity=Business.ACTIVITY_RETAIL,
        )

        self.assertTrue(business.inventory_flow_sales_floor_enabled)
        self.assertFalse(business.inventory_flow_wip_enabled)

    def test_create_business_allows_manual_override(self):
        business = self.service.create_business(
            name="Cafe Sin WIP",
            business_activity=Business.ACTIVITY_CAFETERIA,
            inventory_flow_wip_enabled=False,
        )

        self.assertFalse(business.inventory_flow_wip_enabled)

    def test_update_business_recomputes_default_when_activity_changes(self):
        business = self.service.create_business(
            name="Servicio Demo",
            business_activity=Business.ACTIVITY_SERVICE,
        )
        self.assertFalse(business.inventory_flow_wip_enabled)

        updated = self.service.update_business(
            business,
            business_activity=Business.ACTIVITY_BAR,
        )
        self.assertTrue(updated.inventory_flow_wip_enabled)


if __name__ == "__main__":
    unittest.main()
