from auction import Auction


class RealTimeAuction(object, Auction):

    def __init__(self):
        super(RealTimeAuction, self).__init__()

    def spawn_markets(self, this_transactive_node=None, new_market_clearing_time=None):
        # In this case, the real-time auctions are spawned by the day-ahead markets. Therefore, the real-time markets
        # should not instantiate ANY market objects. The base class method is replaced.
        pass
