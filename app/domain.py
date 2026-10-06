"""Pure money and evidence calculations. All monetary inputs are CZK."""
import math

DEFAULT_SETTINGS = {
    'daily_limit': 0, 'monthly_limit': 0, 'max_cpa': 0, 'target_cpa': 0,
    'min_roas': 0, 'target_roas': 0, 'minimum_purchases': 10,
}
ECONOMIC_FIELDS = ('sale_price', 'purchase_cost', 'vat_rate', 'shipping_cost',
                   'payment_percent', 'payment_fixed', 'returns_cost', 'other_cost')


def number(value, field, maximum=1e9):
    if isinstance(value, bool):
        raise ValueError(f'{field}: očekáváno číslo.')
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field}: očekáváno číslo.') from None
    if not math.isfinite(result) or result < 0 or result > maximum:
        raise ValueError(f'{field}: hodnota musí být mezi 0 a {maximum}.')
    return result


def economics(data):
    result = {k: number(data.get(k, 0), k, 100 if k in ('vat_rate', 'payment_percent') else 1e9)
              for k in ECONOMIC_FIELDS}
    if result['sale_price'] <= 0:
        raise ValueError('Prodejní cena musí být větší než nula.')
    return result


def margin(e, revenue=None, quantity=1):
    """Revenue includes VAT, all costs excluding payment percentage are net CZK per unit.

    Import includes product revenue only. Shipping income must be netted against shipping
    cost outside this model. Contribution is estimated, never accounting profit.
    """
    gross = e['sale_price'] * quantity if revenue is None else revenue
    net = gross / (1 + e['vat_rate'] / 100)
    costs = sum(e[k] for k in ('purchase_cost', 'shipping_cost', 'payment_fixed', 'returns_cost', 'other_cost')) * quantity
    return round(net - costs - gross * e['payment_percent'] / 100, 2)


def ratios(row):
    spend, clicks, purchases, revenue = (row.get(k, 0) for k in ('spend', 'clicks', 'purchases', 'revenue'))
    row.update(cpa=round(spend / purchases, 2) if purchases else None,
               roas=round(revenue / spend, 3) if spend else None,
               ctr=round(clicks / row['impressions'] * 100, 2) if row.get('impressions') else None,
               cpc=round(spend / clicks, 2) if clicks else None,
               conversion_rate=round(purchases / clicks * 100, 2) if clicks else None,
               profit=round(row.get('contribution', 0) - spend, 2))
    return row
