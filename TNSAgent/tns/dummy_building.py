##### dummy building model
# this building model serves as a response model to the dispatch commands
# the transactive node signals
#


def building_response_model(Temp_set = [23]*24, T_init=23):
    # INPUTS: Temp_set is a list of temperature setpoints for each timestep
    #   in the horizon
    #   T_init is the initial condition for temperature, i.e. the temperature
    #   of the building at the previous timestep.
    # OUTPUTS: T_actual is how the building will respond given the new
    #   temperature setpoints
    #
    # figure out how the building will respond to the new temperature setpoint

    T_actual = Temp_set
    return T_actual

T_actual = building_response_model()