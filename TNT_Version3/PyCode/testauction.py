from auction import Auction
from local_asset_model import LocalAsset
from TransactiveNode import TransactiveNode
from time_interval import TimeInterval
from datetime import datetime, timedelta
from market_state import MarketState
from neighbor_model import Neighbor
from direction import Direction

def test_while_in_negotiation():
    print('  Running test_while_in_negotiation().')
    print('    CASE: Normal function. Asset should schedule, and market becomes converged')

    test_asset = LocalAsset()
    default_power = 4.321
    test_asset.defaultPower = default_power

    test_market = Auction()
    test_market.converged = False
    test_market.marketState = MarketState.Negotiation

    dt = datetime.now()
    test_interval = TimeInterval(dt,
                                 timedelta(hours=1),
                                 test_market,
                                 dt,
                                 dt)

    test_market.timeIntervals = [test_interval]

    test_agent = TransactiveNode()
    test_agent.markets = [test_market]
    test_agent.localAssets = [test_asset]

    assert test_market.converged is False, 'The test market should start out not converged'
    assert test_market.marketState == MarketState.Negotiation

    try:
        test_market.while_in_negotiation(test_agent)
        print('    - The method ran without errors')
    except:
        print('    - ERRORS ENCOUNTERED')

    assert test_market.converged is True, 'The market should be converged'
    assert test_market.marketState == MarketState.Negotiation, \
            'The market should not have changed from the negotiation state'
    assert len(test_asset.scheduledPowers) == 1, 'Precisely one scheduled power should have been assigned'

    print('  test_while_in_negotiation() ran to completion.\n')
    pass

def test_while_in_market_lead():
    print('  Running test_while_in_market_lead().')
    print('    CASE 1: One neighbor. Its direction is not assigned.')

    test_neighbor = Neighbor()
    test_neighbor.transactive = False
    test_neighbor.upOrDown = Direction.unknown
    test_neighbor.name = 'Test_Neighbor'

    test_market = Auction()
    test_market.marketState = MarketState.MarketLead

    dt = datetime.now()
    test_interval = TimeInterval(dt,
                                 timedelta(hours=1),
                                 test_market,
                                 dt,
                                 dt)

    test_market.timeIntervals = [test_interval]

    test_agent = TransactiveNode()
    test_agent.markets = [test_market]
    test_agent.neighbors = [test_neighbor]

    assert test_market.marketState == MarketState.MarketLead

    try:
        test_market.while_in_market_lead(test_agent)
        print('    - The method ran without errors')
    except:
        print('    - ERRORS ENCOUNTERED')

    assert test_market.marketState == MarketState.MarketLead, \
                                                    'The market should not have changed from the market lead state'
    assert test_neighbor.upOrDown == Direction.downstream, \
                                                    'The undefined direction should have been assigned downstream'
    assert len(test_neighbor.scheduledPowers) == 0, \
                                              'One scheduled power should have been scheduled by the test neighbor'

    print('  CASE 2: An upstream neighbor is added.')

    upstream_neighbor = Neighbor()
    upstream_neighbor.upOrDown = Direction.upstream

    test_agent.neighbors.append(upstream_neighbor)

    assert len(test_agent.neighbors) == 2, 'There should be two neighbors'

    try:
        test_market.while_in_market_lead(test_agent)
        print('    - The method ran without errors')
    except:
        print('    - ERRORS ENCOUNTERED')

    assert

    print('  test_while_in_market_lead() ran to completion.\n')

def test_while_in_deliver_lead():
    print('  Running test_while_in_delivery_lead().')
    print('    The test is not yet completed.')
    print('    CASE 1:')
    print('    CASE 2:')
    print('    CASE 3:')
    print('  test_while_in_delivery_lead() ran to completion.\n')
    pass

if __name__ == '__main__':
    print('Running tests in testauction.py\n')
    # test_while_in_deliver_lead()
    test_while_in_market_lead()
    # test_while_in_negotiation()
    print("Tests in testauction.py ran to completion.\n")