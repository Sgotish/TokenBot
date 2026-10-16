"""Measured token accounting. Unknown values stay unknown; no invented discounts."""
from decimal import Decimal, ROUND_HALF_UP


def counter(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError('Token counts must be nonnegative integers')
    return value


def normalize(response):
    u = response.get('usage')
    if not isinstance(u, dict):
        return None
    # OpenAI input totals include cached tokens. Anthropic input excludes cache counts.
    if 'input_tokens' in u and 'input_tokens_details' not in u and ('cache_read_input_tokens' in u or 'cache_creation_input_tokens' in u):
        read = counter(u.get('cache_read_input_tokens', 0))
        write = counter(u.get('cache_creation_input_tokens', 0))
        plain = counter(u['input_tokens'])
        output = counter(u['output_tokens'])
    else:
        incoming = counter(u['input_tokens'] if 'input_tokens' in u else u['prompt_tokens'])
        output = counter(u['output_tokens'] if 'output_tokens' in u else u['completion_tokens'])
        details = u.get('input_tokens_details', u.get('prompt_tokens_details'))
        # Some compatible gateways omit the cache breakdown. Do not turn unknown into zero.
        if not isinstance(details, dict) or 'cached_tokens' not in details:
            return {'input_total':incoming,'output':output,'cache_read':None,'cache_write':None,'uncached':None}
        read = counter(details['cached_tokens'])
        write = counter(details.get('cache_write_tokens', details.get('cache_creation_tokens', 0)))
        plain = incoming - read - write
        if plain < 0:
            raise ValueError('Cache counts exceed input total')
    return {'input_total':plain+read+write,'output':output,'cache_read':read,'cache_write':write,'uncached':plain}


def amount(usage, rate):
    """Explicit prices per million in ONE configured currency; not invoice reconciliation."""
    if usage is None or any(usage.get(k) is None for k in ('uncached','cache_read','cache_write','output')):
        return None
    total=Decimal(0)
    for k in ('uncached','cache_read','cache_write','output'):
        price=Decimal(str(rate[k]))
        if not price.is_finite() or price < 0:
            raise ValueError('Prices must be finite and nonnegative')
        total += Decimal(counter(usage[k])) * price / Decimal(1000000)
    return total


def summarize(rows, pricing):
    currency=pricing['currency']
    cost=Decimal(0); revenue=Decimal(0); known=0
    input_total=0;read=0;write=0;cache_denominator=0;cache_known=0
    successful=sum(r.get('status')=='succeeded' for r in rows)
    for row in rows:
        if row.get('status')!='succeeded': continue
        usage=row.get('usage')
        if usage:
            input_total+=usage['input_total']
            if usage['cache_read'] is not None:
                read+=usage['cache_read'];write+=usage['cache_write'];cache_denominator+=usage['input_total'];cache_known+=1
        rate=pricing.get('models',{}).get(row.get('model'))
        if not rate: continue
        c=amount(usage,rate['cost']);r=amount(usage,rate['sell'])
        if c is not None and r is not None:
            cost+=c;revenue+=r;known+=1
    def f(x): return str(x.quantize(Decimal('0.000001'),rounding=ROUND_HALF_UP))
    return {'currency':currency,'jobs':len(rows),'successful':successful,'priced_successes':known,
            'unpriced_successes':successful-known,'cache_observed_successes':cache_known,
            'input_tokens':input_total,'cache_read_tokens':read,'cache_write_tokens':write,
            'cache_read_hit_rate':None if cache_denominator==0 else read/cache_denominator,
            'estimated_cost_known_rows':f(cost),'estimated_revenue_known_rows':f(revenue),
            'estimated_margin_known_rows':f(revenue-cost),'complete':known==successful and successful==len(rows),
            'basis':'Configured prices; excludes unpriced/failed/uncertain work and fixed expenses. Reconcile actual upstream bills.'}
