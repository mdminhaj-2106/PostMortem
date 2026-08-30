"""Step 1 (design doc §5, corrected per this plan's header): hard segment/region/
product filter over support_tickets, using live schema values directly -- no
taxonomy.yaml, no identity-resolution call (support_tickets.customer_id is already
canonical, Layer 1 writes it directly; the Identity Resolution Graph exists for
v_crm_customer_mapping's account-mapping fuzziness only).

flagged_facets() decides WHICH (dimension, slice_value) to filter on: the same
top-share-of-deviation signal Stage 5a's signatures.product_concentration already
uses for `product`, generalized to `region`/`segment` too. Region/segment carry no
real cause signal in most of this dataset's event types (stage05a's README /
architecture.md's Known architectural risks -- no event type ever touches region,
and affected_segment is an orthogonal per-event modifier) -- this function does not
assume otherwise, it just reports whichever slice_value the decomposition's real
numbers concentrate on, if any clears the bar. Zero flagged facets is a legitimate
result, not an error.
"""

from models import DIMENSIONS

_THIN_ELIGIBILITIES = ("LIMITED_HISTORY", "INSUFFICIENT_DATA")
FACET_CONCENTRATION_THRESHOLD = 0.6  # same bar as signatures.PRODUCT_CONCENTRATION_THRESHOLD


def flagged_facets(decomposition_result):
    """[(dimension, slice_value), ...] -- zero to three facets, one per dimension
    whose top OBSERVED, non-thin slice_value's |deviation_pct| share of that
    dimension's total clears FACET_CONCENTRATION_THRESHOLD. Never forces a facet a
    dimension doesn't actually show (plan Scope/Out #3 -- no false joint attribution)."""
    by_dim_kpi = {}
    for s in decomposition_result.slices:
        if s.observation_status != "OBSERVED" or s.deviation_pct is None or s.eligibility in _THIN_ELIGIBILITIES:
            continue
        by_dim_kpi.setdefault((s.dimension, s.kpi_name), []).append(s)

    best_by_dim = {}
    for (dimension, _kpi_name), slices in by_dim_kpi.items():
        magnitudes = sorted(
            ((s.slice_value, abs(s.deviation_pct)) for s in slices), key=lambda pair: pair[1], reverse=True
        )
        total = sum(m for _, m in magnitudes)
        if total <= 0 or len(magnitudes) < 2:
            continue
        top_value, top_mag = magnitudes[0]
        share = top_mag / total
        if share > FACET_CONCENTRATION_THRESHOLD and share > best_by_dim.get(dimension, (None, 0.0))[1]:
            best_by_dim[dimension] = (top_value, share)

    return [(dimension, value) for dimension, (value, _share) in best_by_dim.items()]


def matching_customer_ids(cur, episode_id, dimension, slice_value):
    """customer_ids whose real region/segment matches this facet, or -- for
    `product` -- who placed at least one order in that product category this
    episode (support_tickets carries no product_id of its own to filter on
    directly)."""
    if dimension in ("region", "segment"):
        cur.execute(
            f"SELECT customer_id FROM customers WHERE episode_id=%s AND {dimension}=%s",
            (episode_id, slice_value),
        )
        return {row[0] for row in cur.fetchall()}
    if dimension == "product":
        cur.execute(
            "SELECT DISTINCT o.customer_id FROM orders o JOIN products p ON p.product_id = o.product_id "
            "WHERE o.episode_id=%s AND p.category=%s",
            (episode_id, slice_value),
        )
        return {row[0] for row in cur.fetchall()}
    raise ValueError(f"unknown dimension: {dimension!r}, must be one of {DIMENSIONS}")


def _filter_by_matches(facets, matches_by_facet, tickets):
    """Pure keep/exclude decision, no DB access -- split out from filter_tickets so
    it's directly unit-testable on a small fixture (plan §12.1), same "call the real
    function, no mock framework" style as this project's other offline tests.
    matches_by_facet: {(dimension, slice_value): set(customer_id)}."""
    kept = []
    for ticket in tickets:
        customer_id = ticket[2]
        matched_dims = [
            dimension for (dimension, slice_value) in facets
            if customer_id in matches_by_facet.get((dimension, slice_value), ())
        ]
        if matched_dims:
            kept.append((ticket, matched_dims))
    return kept


def filter_tickets(cur, episode_id, facets, tickets):
    """tickets: [(ticket_id, day_offset, customer_id, text), ...]. Keeps a ticket if
    its customer matches ANY flagged facet -- Stage 4 decomposes each dimension
    independently, so this never assumes a false joint (region AND segment AND
    product) intersection (plan Scope/Out #3). Returns
    [(ticket, matched_dimensions), ...]; matched_dimensions is which flagged
    dimension(s) this particular ticket's customer satisfied."""
    if not facets:
        return []
    matches_by_facet = {
        (dimension, slice_value): matching_customer_ids(cur, episode_id, dimension, slice_value)
        for dimension, slice_value in facets
    }
    return _filter_by_matches(facets, matches_by_facet, tickets)
