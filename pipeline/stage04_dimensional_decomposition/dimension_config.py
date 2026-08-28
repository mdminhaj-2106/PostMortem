"""Declared dimension applicability -- a plain dict, not a config-loading layer, same
pattern as Stage 2's relationship_graph.py/business_importance.py for small declared
config. active_customers_purchased_30d never gets a "product" slice: a customer isn't
tied to one product, so there's no v_billing_active_customers_by_product view to back it.
"""

DIMENSION_APPLICABILITY = {
    "revenue": ["region", "segment", "product"],
    "active_customers_purchased_30d": ["region", "segment"],
}


def applicable_dimensions(kpi_name):
    return DIMENSION_APPLICABILITY.get(kpi_name, [])
