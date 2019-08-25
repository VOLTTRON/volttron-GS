
from datetime import datetime, timedelta, date, time

from vertex import Vertex
from neighbor_model import NeighborModel
from local_asset_model import LocalAssetModel
from market import Market
from time_interval import TimeInterval
from neighbor import Neighbor
from local_asset import LocalAsset
from interval_value import IntervalValue
from measurement_type import MeasurementType


def test_all():
    # TEST_ALL - test the sealed AbstractModel methods
    print('Running AbstractModel.test_all()')
    test_schedule()
    test_update_costs()


def test_schedule():
    print('Running AbstractModel.test_schedule()')
    pf = 'pass'

    #   Create a test market test_mkt
    test_mkt = Market()

    #   Create a sample time interval ti
    dt = datetime.now()
    at = dt
    # NOTE: Function Hours() corrects behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    # NOTE: Function Hours() corrects behavior of Matlab hours().
    st = datetime.combine(date.today(), time()) + timedelta(hours=24)
    ti = TimeInterval(at, dur, mkt, mct, st)

    #   Save the time interval
    test_mkt.timeIntervals = [ti]

    #   Assign a marginal price in the time interval
    test_mkt.check_marginal_prices()

    #   Create a Neighbor test object and give it a default maximum power value
    wcp_obj = Neighbor()#west chiller plant
    wcp_obj.maximumPower = 5000
    wcp_obj.minimumPower = -5000
    wcp_obj.name = 'West Chiller Plant'

    #   Create a corresponding NeighborModel
    wcp_model = NeighborModel()
    wcp_model.effectiveImpedance = .05 #ohms
    wcp_model.transactive = True
    

    #   Make sure that the model and object cross-reference one another
    wcp_obj.model = wcp_model
    wcp_model.object = wcp_obj

    #   Run a test with a NeighborModel object
    print('- running test with a NeighborModel:')

    wcp_model.schedule(test_mkt)
    print('  - the method encountered no errors')

    if len(wcp_model.scheduledPowers) != 1:
        pf = 'fail'
        raise '  - the method did not store a scheduled power'
    else:
        print('  - the method calculated and stored a scheduled power')

    wcp_obj.model.calculate_reserve_margin(mkt)
    if len(wcp_model.reserveMargins) != 1:
        pf = 'fail'
        raise '  - the method did not store a reserve margin'
    else:
        print('  - the method stored a reserve margin')

    if len(wcp_model.activeVertices) != 1:
        pf = 'fail'
        raise '  - the method did not store an active vertex'
    else:
        print('  - the method stored an active vertex')

    # Run a test again with a LocalAssetModel object
    gt1_obj = LocalAsset()#gas turbine 1
    gt1_obj.maximumPower = 1000
    gt1_mdl = LocalAssetModel()
    gt1_mdl.engagementCost = [2.0, 0.005, .5]
    gt1_mdl.defaultPower = 500
    gt1_mdl.cost_parameters = [.01, .02, .03]
    gt1_mdl.name = 'GT1'
    gt1_obj.model = gt1_mdl
    gt1_mdl.object = gt1_obj

    print('- running test with a LocalAssetModel:')

    gt1_mdl.schedule(test_mkt)
    print('  - the method encountered no errors')
    print('GT1 online is ', gt1_mdl.engagementSchedule[0].value)

    if len(gt1_mdl.scheduledPowers) != 1:
        pf = 'fail'
        raise '  - the method did not store a scheduled power'
    else:
        print('  - the method calculated and stored a scheduled power')
        print('GT1 scheduled power is ', gt1_mdl.scheduledPowers[0].value)

    gt1_obj.model.calculate_reserve_margin(mkt)
    if len(gt1_mdl.reserveMargins) != 1:
        pf = 'fail'
        raise '  - the method did not store a reserve margin'
    else:
        print('  - the method stored a reserve margin of ', gt1_mdl.reserveMargins[0].value)


    if len(gt1_mdl.activeVertices) != 1:
        pf = 'fail'
        raise '  - the method did not store an active vertex'
    else:
        print('  - the method stored an active vertex')
        print(' the vertex marginal cost is ', gt1_mdl.activeVertices[0].value.marginalPrice)

    # Success
    print('- the test ran to completion')
    print('Result: ', pf)


def test_update_costs():
    print('Running AbstractModel.test_update_costs()')

    pf = 'pass'

    #   Create a test market test_mkt
    test_mkt = Market()

    #   Create a sample time interval ti
    dt = datetime.now()
    at = dt
    #   NOTE: Function Hours() corrects behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    st = datetime.combine(date.today(), time()) + timedelta(hours=20)
    ti = TimeInterval(at, dur, mkt, mct, st)

    #   Save the time interval
    test_mkt.timeIntervals = [ti]

    #   Assign a marginal price in the time interval
    test_mkt.check_marginal_prices()

    #   Create a Neighbor test object and give it a default maximum power value
    test_obj = Neighbor()
    #     test_obj.maximumPower = 100

    #   Create a corresponding NeighborModel
    test_mdl = NeighborModel()

    #   Make sure that the model and object cross-reference one another
    test_obj.model = test_mdl
    test_mdl.object = test_obj

    test_mdl.scheduledPowers = [IntervalValue(test_mdl, ti, test_mkt, MeasurementType.ScheduledPower, 100)]
    test_mdl.activeVertices = [IntervalValue(test_mdl, ti, test_mkt, MeasurementType.ActiveVertex, Vertex(0.05, 0, 100))]

    #   Run a test with a NeighborModel object
    print('- running test with a NeighborModel:')
    try:
        test_mdl.update_costs(test_mkt)
        print('  - the method encountered no errors')
    except:
        pf = 'fail'
        raise '  - the method did not run without errors'

    if len(test_mdl.productionCosts) != 1:
        pf = 'fail'
        raise '  - the method did not store a production cost'
    else:
        print('  - the method calculated and stored a production cost')

    if len(test_mdl.dualCosts) != 1:
        pf = 'fail'
        raise '  - the method did not store a dual cost'
    else:
        print('  - the method stored a dual cost')

    if test_mdl.totalProductionCost != sum([x.value for x in test_mdl.productionCosts]):
        pf = 'fail'
        raise '  - the method did not store a total production cost'
    else:
        print('  - the method stored an total production cost')

    if test_mdl.totalDualCost != sum([x.value for x in test_mdl.dualCosts]):
        pf = 'fail'
        raise '  - the method did not store a total dual cost'
    else:
        print('  - the method stored an total dual cost')

    # Run a test again with a LocalAssetModel object
    test_obj = LocalAsset()
    #     test_obj.maximumPower = 100
    test_mdl = LocalAssetModel()
    test_obj.model = test_mdl
    test_mdl.object = test_obj

    test_mdl.scheduledPowers = [IntervalValue(test_mdl, ti, test_mkt, MeasurementType.ScheduledPower, 100)]
    test_mdl.activeVertices = [IntervalValue(test_mdl, ti, test_mkt, MeasurementType.ActiveVertex, Vertex(0.05, 0, 100))]

    print('- running test with a LocalAssetModel:')

    try:
        test_mdl.update_costs(test_mkt)
        print('  - the method encountered no errors')
    except:
        pf = 'fail'
        raise '  - the method did not run without errors'

    if len(test_mdl.productionCosts) != 1:
        pf = 'fail'
        raise '  - the method did not store a production cost'
    else:
        print('  - the method calculated and stored a production cost')

    if len(test_mdl.dualCosts) != 1:
        pf = 'fail'
        raise '  - the method did not store a dual cost'
    else:
        print('  - the method stored a dual cost')

    if test_mdl.totalProductionCost != sum([x.value for x in test_mdl.productionCosts]):
        pf = 'fail'
        raise '  - the method did not store a total production cost'
    else:
        print('  - the method stored an total production cost')

    if test_mdl.totalDualCost != sum([x.value for x in test_mdl.dualCosts]):
        pf = 'fail'
        raise '  - the method did not store a total dual cost'
    else:
        print('  - the method stored an total dual cost')

    # Success
    print('- the test ran to completion')
    print('Result: ', pf)


if __name__ == '__main__':
    test_all()
