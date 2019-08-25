# BPA_RATE: BPA 2018-19 energy and demand rate tables
# BPA establishes load-following energy and demand rates for two-year
# periods. Use this class to simply refer to the appropriate table and its
# month number(row) and hour type (row). Row 1 is HLH, row 2 is LLH.
#
# Examples: bpa_rate.energy(2,1) returns the HLH rate for February.
#           bpa_rate.demand(3,2) returns the LLH demand rate for March.

## Constant bpa_rate properties

bpa_energy_rate = [
    #HLH,     LLH       # [$/kWh]
    [0.04196, 0.03660],  # Jan
    [0.04120, 0.03660],  # Feb
    [0.03641, 0.03346],  # Mar
    [0.03233, 0.03020],  # Apr
    [0.02929, 0.02391],  # May
    [0.03037, 0.02197],  # Jun
    [0.03732, 0.03171],  # Jul
    [0.04077, 0.03527],  # Aug
    [0.04060, 0.03485],  # Sep
    [0.03940, 0.03515],  # Oct
    [0.03993, 0.03740],  # Nov
    [0.04294, 0.03740]  # dec
]

bpa_demand_rate = [
    # HLH,     LLH       # [$/kWh]
    [11.45, 0.00],  # Jan
    [11.15, 0.00],  # Feb
    [9.28, 0.00],  # Mar
    [7.68, 0.00],  # Apr
    [6.49, 0.00],  # May
    [6.92, 0.00],  # Jun
    [9.63, 0.00],  # Jul
    [10.98, 0.00],  # Aug
    [10.91, 0.00],  # Sep
    [10.45, 0.00],  # Oct
    [10.65, 0.00],  # Nov
    [11.83, 0.00]  # dec
]
