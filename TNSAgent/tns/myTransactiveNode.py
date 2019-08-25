
class myTransactiveNode:
    ## myTransactiveNode object
    # myTransactiveNode is the local persepctive of the computational agent
    # among a network of TransactiveNodes.

    def __init__(self):
        ## myTransactiveNode Basic Properties
        self.description = ''
        self.mechanism = 'consensus'
        self.name = ''
        self.status = 'unknown'  # future: will be enumeration

        ## myTransactiveNode List Properties
        # The agent must keep track of various devices and their models that are
        # listed among these properties.
        self.informationServiceModels = []  # InformationServiceModel.empty
        self.localAssets = []  # LocalAsset.empty
        self.markets = []  # Market.empty
        self.meterPoints = []  # MeterPoint.empty
        self.neighbors = []  # Neighbor.empty
