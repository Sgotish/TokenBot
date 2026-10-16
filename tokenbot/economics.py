"""Period economics separates received deposits, earned revenue, and fixed pool costs."""
from decimal import Decimal, ROUND_HALF_UP

def calculate(data):
    def d(name):
        v=Decimal(str(data[name]))
        if not v.is_finite() or v<0: raise ValueError('Amounts must be finite and nonnegative')
        return v
    revenue=d('earned_revenue')
    cost=sum((d(k) for k in ('upstream_api_cost','subscription_cost','hosting_cost','maintenance_cost','payment_fees','refund_cost')),Decimal(0))
    deposits=d('deposits_received')
    def f(v):return str(v.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))
    return {'currency':data['currency'],'period':data['period'],'earned_revenue':f(revenue),
            'total_cost':f(cost),'operating_result':f(revenue-cost),
            'margin_rate':None if revenue==0 else str((revenue-cost)/revenue),
            'deposits_received_separate_cash_metric':f(deposits),
            'note':'Deposits are not automatically earned revenue. Subscription capacity is measured, not unlimited.'}
