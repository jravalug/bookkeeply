from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryItemListHtmxRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

    def test_item_list_get_htmx_returns_panel_partial(self):
        fake_client = SimpleNamespace(slug="cliente-demo")
        fake_business = SimpleNamespace(slug="negocio-demo", client=fake_client)
        fake_items = [SimpleNamespace(id=1, name="Harina", unit="kg")]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.get_all_items",
            return_value=fake_items,
        ):
            response = self.client.get(
                "/clients/cliente-demo/business/negocio-demo/inventory/item/list",
                headers={"HX-Request": "true"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="inventory-items-panel"', response.data)
        self.assertIn(b"Harina", response.data)

    def test_item_list_post_htmx_creates_item_and_returns_panel(self):
        fake_client = SimpleNamespace(slug="cliente-demo")
        fake_business = SimpleNamespace(slug="negocio-demo", client=fake_client)
        fake_items = [SimpleNamespace(id=2, name="Azucar", unit="kg")]

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_item",
        ) as create_item_mock, patch(
            "app.routes.inventory.inventory_service.get_all_items",
            return_value=fake_items,
        ):
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/item/list",
                data={"name": "Azucar", "unit": "kg"},
                headers={"HX-Request": "true"},
            )

        self.assertEqual(response.status_code, 200)
        create_item_mock.assert_called_once_with(name="Azucar", unit="kg")
        self.assertIn(b'id="inventory-items-panel"', response.data)
        self.assertIn(b"Articulo de inventario agregado correctamente", response.data)

    def test_item_list_post_non_htmx_keeps_classic_redirect(self):
        fake_client = SimpleNamespace(slug="cliente-demo")
        fake_business = SimpleNamespace(slug="negocio-demo", client=fake_client)

        with patch(
            "app.routes.inventory.inventory_service.resolve_business",
            return_value=fake_business,
        ), patch(
            "app.routes.inventory.inventory_service.create_item",
        ) as create_item_mock:
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/inventory/item/list",
                data={"name": "Sal", "unit": "kg"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        create_item_mock.assert_called_once_with(name="Sal", unit="kg")


if __name__ == "__main__":
    unittest.main()
