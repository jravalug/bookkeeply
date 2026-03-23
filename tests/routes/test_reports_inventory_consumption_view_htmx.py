from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryConsumptionViewHtmx(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()

    def test_inventory_consumption_view_post_htmx_returns_content_partial(self):
        fake_business = SimpleNamespace(
            id=5,
            slug="negocio-demo",
            client=SimpleNamespace(
                slug="cliente-demo", businesses=SimpleNamespace(all=lambda: [])
            ),
        )
        fake_filters = {"business_id": 5, "specific_business_id": None}
        fake_rows = [
            {
                "date": "2026-03-10",
                "items": [
                    {
                        "name": "Harina",
                        "unit": "kg",
                        "total_consumed": 1.25,
                        "product_usages": {"Pan": 1.25},
                    }
                ],
            }
        ]

        with patch(
            "app.routes.reports._resolve_business_scope_or_redirect",
            return_value=(fake_business, fake_filters, None),
        ), patch(
            "app.routes.reports.sales_service.get_inventory_consumption_by_day",
            return_value=fake_rows,
        ):
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/report/inventory-consumption/view",
                data={"month": "2026-03"},
                headers={"HX-Request": "true"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="inventory-consumption-content"', response.data)
        self.assertIn(b"Resultados para 2026-03", response.data)
        self.assertIn(b"Harina", response.data)

    def test_inventory_consumption_view_post_non_htmx_returns_full_view(self):
        fake_business = SimpleNamespace(
            id=7,
            slug="negocio-demo",
            client=SimpleNamespace(
                slug="cliente-demo", businesses=SimpleNamespace(all=lambda: [])
            ),
        )
        fake_filters = {"business_id": 7, "specific_business_id": None}
        fake_rows = [
            {
                "date": "2026-03-11",
                "items": [
                    {
                        "name": "Azucar",
                        "unit": "kg",
                        "total_consumed": 0.75,
                        "product_usages": {"Cafe": 0.75},
                    }
                ],
            }
        ]

        with patch(
            "app.routes.reports._resolve_business_scope_or_redirect",
            return_value=(fake_business, fake_filters, None),
        ), patch(
            "app.routes.reports.sales_service.get_inventory_consumption_by_day",
            return_value=fake_rows,
        ):
            response = self.client.post(
                "/clients/cliente-demo/business/negocio-demo/report/inventory-consumption/view",
                data={"month": "2026-03"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Consumo de Inventario por Producto", response.data)
        self.assertIn(b'id="inventory-consumption-content"', response.data)
        self.assertIn(b"Azucar", response.data)


if __name__ == "__main__":
    unittest.main()
