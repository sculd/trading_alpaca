# dual momentum for major software tech stocks

import pylivetrader.algorithm as algo
from pylivetrader.api import (
    attach_pipeline,
    date_rules,
    get_datetime,
    time_rules,
    order,
    get_open_orders,
    cancel_order,
    pipeline_output,
    schedule_function,
)


_NUM_HOLINGS = 4
_WINDOW_SIZE = 22 # 22 days = 1 month
MAX_GROSS_LEVERAGE = 1.0
MAX_LONG_POSITION_SIZE = 1.00
MAX_SHORT_POSITION_SIZE = 1.00

import logbook

log = logbook.Logger('algo')

def record(*args, **kwargs):
    print('args={}, kwargs={}'.format(args, kwargs))

def initialize(context):
    log.info("initializing")
    context.currently_holding = set()
    schedule_function(clear, date_rules.month_start(), time_rules.market_open())
    schedule_function(daily_rebalance, date_rules.every_day(), time_rules.market_open(hours=1))
    schedule_function(rebalance, date_rules.month_start(), time_rules.market_close(hours=1))
    set_benchmark(symbol('SPY'))
    context.days_cnt = 0

def before_trading_start(context, data):
    '''called every day'''
    context.days_cnt += 1

def clear(context, data):
    log.info(get_datetime())
    log.info("clearing")
    for s in context.currently_holding:
        order_target_percent(s, 0)
    context.currently_holding = set()   

def daily_rebalance(context, data):
    spy = symbol('SPY')
    safe = symbol('TLT')
    for stock in context.portfolio.positions:
        if data.can_trade(stock):
            price = data.current(stock, 'price')
            assets_hist = data.history(stock, 'price', 10 + 1, '1d')
            asset_mom = assets_hist[-1] / assets_hist[0] - 1.0
            if asset_mom < -0.20:
                order_target(stock, 0)
    
def rebalance(context, data):
    assets = symbols('AAPL','GOOG','MSFT','AMZN')
    safe = symbol('TLT')
    
    assets_hist = data.history(assets, 'price', _WINDOW_SIZE + 1, '1d')
    mom = ((assets_hist.iloc[-1]/assets_hist.iloc[0]) - 1.0).dropna()
    top_mom = mom.sort_values()[-_NUM_HOLINGS:]
    top_assets = top_mom.index

    safe_hist = data.history(safe, 'price', _WINDOW_SIZE + 1, '1d')
    safe_mom = (safe_hist[-1]/safe_hist[0]) - 1.0

    n_picks = len(top_assets)
    
    target_weights = {}

    '''
    choose tops assets as long as its moment is larger than safe's momentum
    otherwise choose safe as long as its momentum is positive
    otherwise choose tlt
    '''
    picks = 0
    for i in range(n_picks):
        a = top_assets[i]
        m = top_mom[i]
        if m > safe_mom:
            if data.can_trade(a):
                target_weights[a] = 0.25
                context.currently_holding.add(a)
                picks += 1

    safe_percent = 0
    more_picks = 4 - picks
    if more_picks > 0:
        safe_percent = 0.25 * more_picks

    if safe_percent > 0.0 and data.can_trade(safe) and safe_mom > 0:  
        target_weights[safe] = safe_percent
        context.currently_holding.add(safe)
        
    execute(context, target_weights)    
    
    total_weight = sum(map(lambda p: target_weights[p], target_weights))
    record(
        leverage = context.account.leverage,
        holdings = len(context.currently_holding),
        total_weight = total_weight,
    )
    
def execute(context, target_weights):   
    log.info("after rebalance, holdings: %s" % (str(target_weights)))
    if_optimize = False
    
    if not if_optimize:
        for a, p in target_weights.items():
            order_target_percent(a, p)

