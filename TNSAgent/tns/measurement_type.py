# MeasurementType Enumeration
#   This enumeration is used by IntervalValue class to consistently
#   specify types of measurements being made, including their units of
#   measure. (Some further work may be needed to parse this enumeration
#   into still smaller parts.)

#   VERSION DATE    AUTHOR          CHANGES
#   0.1     2017-11 DJ Hammerstrom  Original draft
#   0.2     2019-05 NV Panossian    Added thermal energy types


class MeasurementType:
    Voltage = 1
    PowerReal = 2
    PowerReactive = 3
    PriceIncremental = 4
    PriceBlended = 5
    EnergyReal = 6
    EnergyReactive = 7
    PowerMinimum_real = 8
    PowerMaximum_real = 9
    PowerMinimum_reactive = 10
    PowerMaximum_reactive = 11
    ProdVertex = 12  # used by LocalResource
    Temperature = 13  # used by WeatherForecastModel
    IsolationDensity = 14
    RelativeHumidity = 15
    ScheduledPower = 16
    EngagementValue = 17
    ReserveMargin = 18
    TransitionCost = 19
    DualCost = 20
    ProductionCost = 21
    ActiveVertex = 22
    AverageDemandkW = 23
    Vertex = 24
    TestVertex = 25
    MarginalPrice = 26
    SystemVertex = 27
    BlendedPrice = 28
    TotalGeneration = 29
    TotalDemand = 30
    NetPower = 31
    EngagementSchedule = 32
    ConvergenceFlag = 33
    Unknown = 40
    Heat = 41
    Cooling = 42
