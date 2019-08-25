
class AuctionState:
    # MarketState Enumeration
    # MarketState is an enumeration os states of TimeIntervals as defined by
    # the Market(s) in which myTransactiveNode transacts.
    Inactive = 1  # Unneeded, inactive
    Exploring = 2  # Actively negotiating. Not converged.
    Tender = 3  # A converged electricity allocation solution has been found
    Transaction = 4  # The market has cleared. Contractuals may exist
    Delivery = 5  # The systen is currently in the interval period
    Publish = 6  # The interval is over. Reconciliation may be under way
    Expired = 7  # Reconciliation is concluded. The interval is inactive