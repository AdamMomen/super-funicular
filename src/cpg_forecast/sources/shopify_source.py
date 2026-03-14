"""Shopify API source adapter (stub for extension)."""

from __future__ import annotations

import pandas as pd


class ShopifySourceAdapter:
    """Load orders from Shopify API via OAuth + REST/GraphQL.

    Extension point for production: OAuth flow, pagination, rate limiting.
    See: https://shopify.dev/docs/api/admin-rest
    """

    def __init__(self, shop_domain: str, access_token: str | None = None) -> None:
        self.shop_domain = shop_domain
        self.access_token = access_token

    def load_orders(self) -> pd.DataFrame:
        """Load orders from Shopify. Not implemented."""
        raise NotImplementedError(
            "Connect Shopify API: implement OAuth, then fetch orders via "
            "GET /admin/api/2024-01/orders.json. Map to order_date, sku, quantity."
        )

    def get_name(self) -> str:
        return f"shopify:{self.shop_domain}"
