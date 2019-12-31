# from local_asset import LocalAsset
# TODO: Check for and correct references to class LocalAsset
from local_asset_model import LocalAsset
from market import Market
from datetime import datetime, timedelta
from ip_water_heater import IpWaterHeater


def test_set_cost_mode():
    print('Running test_set_cost_mode().')
    test_asset = IpWaterHeater()

    print('  Case 1: Normal case. Provided parameter lies in (0, 1).')
    cost_mode = 0.5

    try:
        new_cost_mode = test_asset.set_cost_mode(cost_mode)
        print('  The method ran without errors')
    except:
        print(' The method encountered errors')

    assert test_asset.costMode == cost_mode, "The asset's cost mode was not as expected."
    assert new_cost_mode == cost_mode, 'An unexpected value was returned.'

    print('  Case 2: Provided parameter > 1.')
    cost_mode = 2

    try:
        new_cost_mode = test_asset.set_cost_mode(cost_mode)
        print('  The method ran without errors')
    except:
        print(' The method encountered errors')

    assert test_asset.costMode == 1, "The asset's cost mode was not as expected."
    assert new_cost_mode == 1, 'An unexpected value was returned.'

    print('  Case 3: Provided parameter < 0.')
    cost_mode = -2

    try:
        new_cost_mode = test_asset.set_cost_mode(cost_mode)
        print('  The method ran without errors')
    except:
        print(' The method encountered errors')

    assert test_asset.costMode == 0, "The asset's cost mode was not as expected."
    assert new_cost_mode == 0, 'An unexpected value was returned.'

    print('test_set_cost_mode() ran to completion.\n')


def test_get_cost_mode():
    print('Running test_set_cost_mode().')
    test_asset = IpWaterHeater()
    cost_mode = 0.5
    test_asset.costMode = cost_mode

    print('  Normal case.')

    try:
        returned_cost_mode = test_asset.get_cost_mode()
        print('  The method ran without errors')
    except:
        print(' The method encountered errors')

    assert test_asset.costMode == cost_mode, "The asset's cost mode was unexpectedly changed."
    assert returned_cost_mode == cost_mode, 'An unexpected value was returned.'

    print('test_get_cost_mode() ran to completion.\n')


def test_set_risk_mode():
    print('Running test_set_risk_mode().')
    test_asset = IpWaterHeater()

    print('  Case 1: Normal case. Provided parameter lies in (0, 1).')
    risk_mode = 0.5

    try:
        new_risk_mode = test_asset.set_risk_mode(risk_mode)
        print('  The method ran without errors')
    except:
        print(' The method encountered errors')

    assert test_asset.riskMode == risk_mode, "The asset's risk mode was not as expected."
    assert new_risk_mode == risk_mode, 'An unexpected value was returned.'

    print('  Case 2: Provided parameter > 1.')
    risk_mode = 2

    try:
        new_risk_mode = test_asset.set_risk_mode(risk_mode)
        print('  The method ran without errors')
    except:
        print(' The method encountered errors')

    assert test_asset.riskMode == 1, "The asset's cost mode was not as expected."
    assert new_risk_mode == 1, 'An unexpected value was returned.'

    print('  Case 3: Provided parameter < 0.')
    risk_mode = -2

    try:
        new_risk_mode = test_asset.set_risk_mode(risk_mode)
        print('  The method ran without errors')
    except:
        print(' The method encountered errors')

    assert test_asset.riskMode == 0, "The asset's cost mode was not as expected."
    assert new_risk_mode == 0, 'An unexpected value was returned.'

    print('test_set_risk_mode() ran to completion.\n')


def test_get_risk_mode():
    print('Running test_set_risk_mode().')
    test_asset = IpWaterHeater()
    risk_mode = 0.5
    test_asset.riskMode = risk_mode

    print('  Case 1: Risk mode exists and is read.')

    try:
        returned_risk_mode = test_asset.get_risk_mode()
        print('  The method ran without errors')
    except:
        print(' The method encountered errors')

    assert test_asset.riskMode == risk_mode, "The asset's risk mode was unexpectedly changed."
    assert returned_risk_mode == risk_mode, 'An unexpected value was returned.'

    print('test_get_risk_mode() ran to completion.\n')


def test_schedule_power():
    print('Running test_schedule_power().')
    print('test_schedule_power() ran to completion.\n')


def test_get_current_upper_temperature():
    print('Running test_get_current_upper_temperature().')
    print('  Case 1: The current upper temperature can be directly measured.')
    print('  Case 2: The current upper temperature must be inferred from model predictive control.')
    print('  Case 3: The current upper temperature is unavailable by measurement or from model predictive control')
    print('test_get_current_upper_temperature() ran to completion.\n')


def test_get_current_lower_temperature():
    print('Running test_get_current_lower_temperature().')
    print('  Case 1: The current lower temperature can be directly measured.')
    print('  Case 2: The current lower temperature must be inferred from model predictive control.')
    print('  Case 3: The current lower temperature is unavailable by measurement or from model predictive control')
    print('test_get_current_lower_temperature() ran to completion.\n')


def test_measure_inlet_temperature():
    print('Running test_measure_inlet_temperature().')
    print('  Case 1: The current inlet temperature can be directly measured.')
    print('  Case 2: The current inlet temperature is unavailable, so the initialized value is used instead.')
    print('test_measure_inlet_temperature() ran to completion.\n')

def test_model_water_use():
    print('Running test_model_water_use().')
    print('  Case 1: ')
    print('test_model_water_use() ran to completion.\n')


if __name__ == '__main__':
    test_get_cost_mode()
    test_get_current_lower_temperature()
    test_get_current_upper_temperature()
    test_get_risk_mode()
    test_model_water_use()
    test_schedule_power()
    test_set_cost_mode()
    test_set_risk_mode()




