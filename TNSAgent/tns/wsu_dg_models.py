

####################### Script that creates all WSU components ########################
# these are response models
# fit curves for boilers, gas turbines, and chillers
# the fits create relationships between power output setpoint and fuel/electricity input
# for example: a gas turbine will recieve an electrical power setpoint
#               that power setpoint will be turned into a fuel consumption using the fit
# another example: a chiller will receive a cooling power setpoint
#               that power setpoint will be turned into an electrical consumption using
#               the fit curve

# these component models are made using class definitions created to work with the TNT
# the TNT is no longer useful, so these models may be stripped down to only include the fits

# these models may also need to be separated into their own script files instead of being 
# created in one script

import numpy as np
from boiler import Boiler
from chiller import Chiller
from gas_turbine import GasTurbine

# boilers and chillers use function self.use_fit_curve(setpoint)
# boiler1_fuel_use = boiler1Model.use_fit_curve(heat_setpoint)
# chiller1_electric_use = chiller1Model.use_fit_curve(cooling_setpoint)

# gas turbines use function self.use_fit_curve(coefs, setpoint)
# gt1heat = gt1Model.use_fit_curves(self.fit_curve['coefs_h'], electric_generation_setpoint)
# gt1_fuel_use = gt1Model.use_fit_curves(self.fit_curve['coefs_e'], electric_generation_setpoint)

# add GT1
gt1Model = GasTurbine()
gt1Model.name = 'gt1'
gt1Model.size = 2500
gt1Model.ramp_rate = 1.3344e3
gt1Model.make_fit_curve()

# add gas turbine 2
gt2Model = GasTurbine()
gt2Model.name = 'gt2'
gt2Model.size = 2187.5
gt2Model.ramp_rate = 1.3344e3
gt2Model.make_fit_curve()

# add gt3
gt3Model = GasTurbine()
gt3Model.name = 'gt2' # gt3 has the same normalized efficiency curve as gt2
gt3Model.size = 1375
gt3Model.ramp_rate = 1.3344e3
gt3Model.make_fit_curve()

# add gt3
gt4Model = GasTurbine()
gt4Model.name = 'gt2' # gt4 has the same normalized efficiency curve as gt2
gt4Model.size = 1375
gt4Model.ramp_rate = 1.3344e3
gt4Model.make_fit_curve()

# add boiler1
boiler1Model = Boiler(name ='boiler1', size =20000)
boiler1Model.ramp_rate = 1333.3
boiler1Model.make_fit_curve()

# add boiler 2
boiler2Model = Boiler(name = 'boiler2')
boiler2Model.size = 20000
boiler2Model.ramp_rate = 1333.3
boiler2Model.make_fit_curve()

# add boiler 3
boiler3Model = Boiler(name='boiler3')
boiler3Model.size = 20000
boiler3Model.ramp_rate = 1333.3
boiler3Model.make_fit_curve()

# add boiler 4
boiler4Model = Boiler(name = 'boiler1', size = 20000)
boiler4Model.ramp_rate = 1333.3
boiler4Model.make_fit_curve()

# add boiler 5
boiler5Model = Boiler()
boiler5Model.name = 'boiler5'
boiler5Model.size = 20000
boiler5Model.ramp_rate = 1333.3
boiler5Model.make_fit_curve()

# add west campus chillers: carrier chiller1, york chiller1, york chiller3
carrierchiller1Model = Chiller(name='carrierchiller1', size = 7.279884675000000e+03)
carrierchiller1Model.ramp_rate = 4.8533e3
carrierchiller1Model.make_fit_curve()

# add york chiller 1
yorkchiller1Model = Chiller(name='yorkchiller1',size=5.268245045000001e+03)
yorkchiller1Model.ramp_rate = 3.5122e3
yorkchiller1Model.make_fit_curve()

# add york chiller 3
yorkchiller3Model = Chiller(name='yorkchiller3', size=5.268245045000001e+03)
yorkchiller3Model.ramp_rate = 3.5122e3
yorkchiller3Model.make_fit_curve()

# add east campus chillers: carrier chiller 2, and carrier chiller 3
# add carrier chiller 2
cc2Model = Chiller(name='carrierchiller2', size=4.853256450000000e+03)
cc2Model.ramp_rate = 3.2355e3
cc2Model.make_fit_curve()

# add carrier chiller 3
cc3Model = Chiller(name='carrierchiller3', size=4.853256450000000e+03)
cc3Model.ramp_rate = 3.2355e3
cc3Model.make_fit_curve()

# add carrier chiller 4
cc3Model = Chiller(name='carrierchiller4', size=1.758426250000000e+03)
cc3Model.ramp_rate = 1.1723e3
cc3Model.make_fit_curve()

# add carrier chiller 7
cc3Model = Chiller(name='carrierchiller7', size=5.275278750000000e+03)
cc3Model.ramp_rate = 3.5169e3
cc3Model.make_fit_curve()

# add carrier chiller 8
cc3Model = Chiller(name='carrierchiller8', size=5.275278750000000e+03)
cc3Model.ramp_rate = 3.5169e3
cc3Model.make_fit_curve()

# add trane chiller
tranechillerModel = Chiller(name = 'tranechiller', size = 1.415462794200000e+03)
tranechillerModel.ramp_rate = 943.6419
tranechillerModel.make_fit_curve()