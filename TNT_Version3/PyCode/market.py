# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# 'AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}


# import gevent  # Comment out if Volttron environment is available
from datetime import datetime, timedelta
# import logging  # Comment out if Volttron environment is available
# TODO: Reenable logging throughout Market

# from volttron.platform.agent import utils  # Comment out if Volttron environment is available
# TODO: Reenable volttrom import in Market

from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from interval_value import IntervalValue
from meter_point import MeterPoint
from market_state import MarketState
from time_interval import TimeInterval
from timer import Timer

# utils.setup_logging()
# _log = logging.getLogger(__name__)


class Market:
    # Market Base Class
    # A Market object may be a formal driver of myTransactiveNode's responsibilities within a formal market. At least
    # one Market must exist (see the firstMarket object) to drive the timing with which new TimeIntervals are created.

    def __init__(self):

        # NEW 1911DJH
        # The original Matlab design did not perform this degree of construction, and doing so was not necessary
        # because these properties were automatically provided with their default values. The new version must provide
        # greater flexibility in the definitions of markets. Market objects will be instantiated for every market
        # clearing, and most of these Market properties must be redefined upon instantiation. Certain of these, like
        # the priceModel list, should be adopted rather than overwritten.
        self.activationLeadTime = timedelta(hours=0)
        self.deliveryLeadTime = timedelta(hours=0)  # See new MarketStates and market state diagram
        self.marketLeadTime = timedelta(hours=0) 
        self.negotiationLeadTime = timedelta(hours=0)
        self.marketName = ''
        self.marketState = MarketState.Inactive
        self.priorMarket = None
        self.reconciled = False

        average_price = 0.06 #Initialization [$/kWh]
        st_dev_price = 0.01 #Initialization [$/kWh] 
        self.priceModel = [(average_price, st_dev_price) * 24]  # Each hour's tuplet average and st. dev. price.
        # ..............................................................................................1911DJH NEW

        self.name = ''
        self.initialMarketState = MarketState.Inactive  # enumeration

        self.commitment = False
        self.converged = False

        self.method = 2  # Calculation method {1: subgradient, 2: interpolation}
        self.marketOrder = 1  # ordering of sequential markets [pos. integer]

        self.activeVertices = []  # IntervalValue.empty  # values are vertices
        self.blendedPrices1 = []  # IntervalValue.empty  # future
        self.blendedPrices2 = []  # IntervalValue.empty  # future

        self.defaultPrice = 0.05  # [$/kWh]        
        self.dualCosts = []  # IntervalValue.empty  # values are [$]
        self.dualityGapThreshold = 0.01  # [dimensionless, 0.01 = 1%]
        self.netPowers = []  # IntervalValue.empty  # values are [avg.kW]
        self.marginalPrices = []  # IntervalValue.empty  # values are [$/kWh]
        self.productionCosts = []  # IntervalValue.empty  # values are [$]

        self.totalDemand = []  # IntervalValue.empty  # [avg.kW]
        self.totalDualCost = 0.0  # [$]
        self.totalGeneration = []  # IntervalValue.empty  # [avg.kW]
        self.totalProductionCost = 0.0  # [$]

        self.marketClearingInterval = timedelta(hours=1)  # [h]
        self.marketClearingTime = None  # datetime.empty  # when market clears
        self.nextMarketClearingTime = None  # datetime.empty  # start of pattern
        self.futureHorizon = timedelta(hours=24)
        self.intervalDuration = timedelta(hours=1)
        self.intervalsToClear = 1  # positive integer
        self.timeIntervals = []  # TimeInterval.empty

        self.new_data_signal = False

    # NEW 1911DJH ******************************************************************************************************
    def events(self, mtn):
        """
        This is the market state machine. Activities should be assigned to state transition events and to the states
        themselves using the supplied methods. This state machine should not itself be modified by implementers because
        doing so may affect alternative market methods' state models.
        :param mtn: my transactive node agent that keeps track of market objects
        :return: None
        """

        current_time = datetime.now()

        # EVENT 1A: % A NEW MARKET OBJECT BECOMES ACTIVE ***************************************************************
        # This is the instantiation of a market object in market state "Active." This transition occurs at a time when
        # a new market object is needed, as specified relative to its market clearing time. Specifically, a new market
        # object is instantiated in its "Active" state a specified negotiation lead time and market lead time prior to
        # the market's clearing time. Note that this logic seems a little backward because the state's start must be
        # determined *before* the needed market object exists.

        future_clearing_time = current_time + self.activationLeadTime + self.negotiationLeadTime + self.marketLeadTime

        # The object may be among a sequence of similar market objects that have the same market name. Such "similar"
        # market objects have the same role and type (e.g., real-time auction). We need to review the list of existing
        # market objects of this type to see if they adequately provide the needed lead times for negotiation and
        # market calculations. If not, a new market object must be created. Find all similar active markets.
        similar_markets = []
        for x in range(len(mtn.markets)):
            if mtn.markets[x].marketName == self.marketName:
                similar_markets.append(mtn.markets[x])

        # Pick out the similar market having the latest market clearing time.
        latest_clearing_time = []
        for x in range(len(similar_markets)):
            latest_clearing_time.append(similar_markets[x].nextMarketClearingTime)

        if len(latest_clearing_time) > 1:
            latest_clearing_time = max(latest_clearing_time)
        elif len(latest_clearing_time) == 0:
            raise Warning('market name was not defined')
        elif len(latest_clearing_time) == 1:
            latest_clearing_time = latest_clearing_time[0]

        if latest_clearing_time < future_clearing_time:

            # A market object is instantiated by this following method. It will normally be unwise for casual users to
            # modify this method, but it can be overwritten or modified by child classes of class Market.
            self.transition_to_active(mtn, latest_clearing_time)

        # EVENT 1B: ACTIONS WHILE IN THE ACTIVE STATE ******************************************************************
        # These are actions to be taken while the market object is in its initial "Active" market state.

        if self.marketState == MarketState.Active:

            # Place actions to be taken in this state in the following method. The method may be overwritten by child
            # classes of class Market.
            self.while_in_active(mtn)

        # EVENT 2A: TRANSITION FROM ACTIVE TO NEGOTIATION STATE ********************************************************
        # This is the transition from "Active" to "Negotiation" market states. Market state "Negotiation" begins at a
        # time specified before an upcoming market clearing of a market object. Specifically, it begins a specified
        # market lead time, less another negotiation lead time, prior to the clearing of the market object.

        negotiation_start_time = self.marketClearingTime - self.marketLeadTime - self.negotiationLeadTime

        if self.marketState == MarketState.Active and current_time >= negotiation_start_time:

            # Change the market state to "Negotiation."
            self.marketState = MarketState.Negotiation

            # Place other transition actions in this following method. The method may be overwritten by child classes
            # of class Market.
            self.transition_from_active_to_negotiation(mtn)

        # EVENT 2B: ACTIONS WHILE IN MARKET STATE NEGOTIATION **********************************************************
        # These are the actions while in the "Negotiation" market state.

        if self.marketState == MarketState.Negotiation:

            # Place actions to be completed during this market state in the following method. The method may be
            # overwritten by child classes of class Market. Note that the actions during this state may be made
            # dependent upon a convergence flag.

            self.while_in_negotiation(mtn)

        # EVENT 3A: TRANSITION FROM NEGOTIATION TO MARKET LEAD STATE ***************************************************
        # This is the transition from "Negotiation" to "MarketLead" market states.
        # The transition occurs at a time relative to the market object's market clearing time. Specifically, it starts
        # a defined lead time prior to the market clearing time.

        market_lead_start_time = self.marketClearingTime - self.marketLeadTime

        if self.marketState == MarketState.Negotiation and current_time >= market_lead_start_time:

            # Change the market state to "MarketLead."
            self.marketState = MarketState.MarketLead

            #  Place other transition actions in this following method. The method may be overwritten by child classes
            #  of class Market.
            self.transition_from_negotiation_to_market_lead(mtn)

        # EVENT 3B: ACTIONS WHILE IN THE MARKET LEAD STATE *************************************************************
        # These are the actions while in the "MarketLead" market state.

        if self.marketState == MarketState.MarketLead:

            #  Specify actions for the market state "MarketLead" in this following method. The method may be
            #  overwritten by child classes of class Market.
            self.while_in_market_lead(mtn)

        # EVENT 4A: TRANSITION FROM MARKET LEAD TO DELIVERY LEAD STATE *************************************************
        # This is the transition from "MarketLead" to "DeliveryLead" market states.

        # This transition is simply the market clearing time.
        delivery_lead_start_time = self.marketClearingTime

        if self.marketState == MarketState.MarketLead and current_time >= delivery_lead_start_time:

            # Set the market state to "DeliveryLead."
            self.marketState = MarketState.DeliveryLead

            # Place other transition actions here. This following method may be overwitten by child classes of class
            # Market.
            self.transition_from_market_lead_to_delivery_lead(mtn)

        # EVENT 4B: ACTIONS WHILE IN MARKET STATE DELIVERY LEAD ********************************************************
        # These are the actions while in the "DeliveryLead" market state.

        if self.marketState == MarketState.DeliveryLead:

            # Place actions in this following method if they are to occur during market state "DeliveryLead." This
            # method may be overwritten by child classes of class Market.
            self.while_in_delivery_lead(mtn)

        # EVENT 5A: TRANSITION FROM DELIVERY LEAD TO DELIVERY **********************************************************
        # This is the transition from "DeliveryLead" to "Delivery" market states. The start of market state "Delivery"
        # is timed relative to the market object's market clearing time. Specifically, it begins a delivery lead time
        # after the market has cleared.

        delivery_start_time = self.marketClearingTime + self.deliveryLeadTime

        if self.marketState == MarketState.DeliveryLead and current_time >= delivery_start_time:

            # Change the market state from "DeliverLead" to "Delivery."
            self.marketState = MarketState.Delivery

            # Other actions for this transition should be placed in the following method, which can be overwritten by
            # child classes of Market.
            self.transition_from_delivery_lead_to_delivery(mtn)

        # EVENT 5B: ACTIONS WHILE IN MARKET STATE DELIVERY *************************************************************
        # These are the actions while in the "Delivery" market state.

        if self.marketState == MarketState.Delivery:

            # Place any actions to be conducted in market state "Delivery" in this following method. The method may be
            # overwritten by child classes of class Market.
            self.while_in_delivery(mtn)

        # EVENT 6A: TRANSITION FROM DELIVERY TO RECONCILE **************************************************************
        # This is the transition from "Delivery" to "Reconcile" market states. The Reconcile market state begins at a
        # time referenced from the market object's clearing time. Specifically, reconciliation begins after all the
        # market object's market intervals and an additional delivery lead time have expired after the market clears.

        reconcile_start_time = self.marketClearingTime + self.deliveryLeadTime \
                               + self.intervalsToClear * self.intervalDuration

        if self.marketState == MarketState.Delivery and current_time >= reconcile_start_time:

            # Change the market state to "Reconcile."
            self.marketState = MarketState.Reconcile

            # Other transition actions may be placed in this method.
            self.transition_from_delivery_to_reconcile(mtn)

        # EVENT 6A: ACTIONS WHILE IN MARKET STATE RECONCILE ************************************************************
        # These are the actions while in the "DeliveryLead" market state.

        if self.marketState == MarketState.Reconcile:

            # Place actions in this following method if they should occur during market state "Reconcile." This method
            # may be overwritten by children of the Market class.
            self.while_in_reconcile(mtn)

        # EVENT 7A: TRANSITION FROM RECONCILE TO EXPIRED ***************************************************************
        # This is the transition from "Reconcile" to "Expired" market states.
        if self.marketState == MarketState.Reconcile and self.reconciled is True:

            # Change the market state to "Expired".
            self.marketState = MarketState.Expired

            # Replace this method for other transitional actions.
            self.transition_from_reconcile_to_expired(mtn)

        # EVENT 7B: WHILE EXPIRED **************************************************************************************
        # These are the actions while in the "Expired" market state. It should be pretty standard that market objects
        # are deleted after they expire, so it is unlikely that alternative actions will be needed by child Market
        # classes.

        if self.marketState == MarketState.Expired:

            # Delete market intervals that are defined by this market object.
            self.timeIntervals = []

            # Remove the expired market object from the agent's list of markets.
            mtn.markets.remove(self)

            # Delete the expired market object handle and clear it from memory.
            # self = None # LOOK. DOES THIS WORK?
        # ************************************************************************************************* 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def transition_to_active(self, mtn, new_market_clearing_time):
        """
        For activities that should accompany a market object's instantiation into market state "Active." A market
        object is instantiated by this following method. It will normally be unwise for casual users to modify this
        method, but it can be overwritten by child classes of class Market.
        mtn: my transactive node agent object
        new_market_clearing_time: new market objects market clearing time
        :return: None
        """

        # A new market object must be instantiated. Many of its properties are the same as that of the called market
        # or can be derived therefrom.
        new_market = Market()  # This uses a constructor, but most properties must be redefined.

        new_market.marketName = self.marketName
        new_market.marketClearingTime = new_market_clearing_time
        new_market.nextMarketClearingTime = new_market.marketClearingTime + self.marketClearingInterval
        new_market.deliveryLeadTime = self.deliveryLeadTime
        new_market.marketLeadTime = self.marketLeadTime
        new_market.negotiationLeadTime = self.negotiationLeadTime
        new_market.commitment = self.commitment
        new_market.defaultPrice = self.defaultPrice
        new_market.futureHorizon = self.futureHorizon
        new_market.initialMarketState = self.initialMarketState
        new_market.intervalDuration = self.intervalDuration
        new_market.intervalsToClear = self.intervalsToClear
        new_market.marketClearingInterval = self.marketClearingInterval
        new_market.marketOrder = self.marketOrder
        new_market.method = self.method
        new_market.priceModel = self.priceModel  # It must be clear that this is a copy, not a reference.
        new_market.marketState = MarketState.Active

        # The market instance is named by concatenating the market name and its market clearing time. There MUST be a
        # simpler way to format this in Python!
        dt = str(new_market.marketClearingTime)
        new_market.name = new_market.marketName + dt[:19]

        # Append the new market object to the list of market objects that is maintained by the agent.
        mtn.markets.append(new_market)

        # Initialize the Market object's time intervals.
        # new_market.check_intervals()
        # TODO: Scrub and test market method check_intervals()

        # Initialize the marginal prices in the Market object's time intervals.
        # new_market.check_marginal_prices(mtn)
        # TODO: Scrub and test market method check_marginal_prices()
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def while_in_active(self, mtn):
        """
        For activities that should happen while a market object is in its initial "Active" market state. This method
        may be overwritten by child classes of Market to create alternative market behaviors during this market state.
        It will be rare for a market object to have actions in its Active state. It usually will immediately enter its
        Negotiation state.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def transition_from_active_to_negotiation(self, mtn):
        """
        For activities that should accompany a market object's transition from market state "Active" to "Negotiation."
        This method may be overwritten by child classes of Market to create alternative market behaviors during this
        transition.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def while_in_negotiation(self, mtn):
        """
        For activities that should happen while a market object is in its "Negotiation" market state. This method may
        be overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param mtn: my transactive node agent object
        :return: None
        """

        # A convergence flag is available to distinguish actions to be undertaken while actively negotiating and others
        # while convergence has been obtained.
        if not self.converged:
            self.balance(mtn)  # A consensus method conducts negotiations while in the negotiation state.

        else:
            # This is most likely a wait state while converged in the negotiation state.
            pass

        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def transition_from_negotiation_to_market_lead(self, mtn):
        """
        For activities that should accompany a market object's transition from market state "Negotiation" to
        "MarketLead." This method may be overwritten by child classes of Market to create alternative market behaviors
        during this transition.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def while_in_market_lead(self, mtn):
        """
        For activities that should happen while a market object is in its "MarketLead" market state. This method may
        be overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def transition_from_market_lead_to_delivery_lead(self, mtn):
        """
        For activities that should accompany a market object's transition from market state "MarketLead" to
        "DeliveryLead," (i.e., the clearing of the market). This method may be overwritten by child classes of Market
        to create alternative market behaviors during this transition.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def while_in_delivery_lead(self, mtn):
        """
        For activities that should happen while a market object is in its "DeliveryLead" market state. This method may
        be overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def transition_from_delivery_lead_to_delivery(self, mtn):
        """
        For activities that should accompany a market object's transition from market state "DeliveryLead" to
        "Delivery." This method may be overwritten by child classes of Market to create alternative market behaviors
        during this transition.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def while_in_delivery(self, mtn):
        """
        For activities that should happen while a market object is in its "Delivery" market state. This method may be
        overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param mtn: my transactive node agent object
        :return: None
        """

        # TBD: These actions will be common to most transactive systems during the delivery market state:
        # - monitor and meter assets and power exchanges
        # - control assets to negotiated average power
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def transition_from_delivery_to_reconcile(self, mtn):
        """
        For activities that should accompany a market object's transition from market state "Delivery" to "Reconcile."
        This method may be overwritten by child classes of Market to create alternative market behaviors during this
        transition.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def while_in_reconcile(self, mtn):
        """
        For activities that should happen while a market object is in its "Reconcile" market state. This method may be
        overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param mtn: my transactive node agent object
        :return: None
        """

        # Save market object data:

        # Create a table for market object data.
        data = []

        # Append data for active market vertices:
        for x in range(len(self.activeVertices)):
            datum = [self.name,
                     self.activeVertices.timeInterval.name,
                     self.activeVertices[x].value.marginalPrice,
                     self.activeVertices[x].value.power]
            data.append(datum)

        # Append data for local assets:
        for x in range(len(mtn.localAssets)):
            vertices = [y for y in mtn.localAssets[x].model.activeVertices
                        if y.model.activeVertices.timeInterval.market == self]

            for z in range(len(vertices)):
                datum = [mtn.localAssets[x].name,
                         vertices[z].timeInterval.name,
                         vertices[z].value.marginalPrice,
                         vertices[z].value.power]
                data.append(datum)

        # Append data for neighbor data:
        for x in range(len(mtn.neighbors)):
            vertices = [y for y in mtn.neighbors[x].model.activeVertices
                        if y.model.activeVertices.timeInterval.market == self]

            for z in range(len(vertices)):
                datum = [mtn.neighbors[x].name,
                         vertices[z].timeInterval.name,
                         vertices[z].value.marginalPrice,
                         vertices[z].value.power]
                data.append(datum)

        # Write the vertex data into a csv file

        filename = self.marketName + ".csv"
        data_folder = "C:\\Users\\D3H843\\Documents\\transactivenetwork\\TNT_Version3\\Market_Data\\"
        full_filename = data_folder + filename

        import csv

        my_file = open(full_filename, 'w+')
        with my_file:
            writer = csv.writer(my_file)
            writer.writerows(data)

        # Gather simpler marginal price data:
        price_data = []

        for x in self.marginalPrices:  # LOOK. DOES THIS DIRECT INDEXING WORK?
            datum = [self.name,
                      x.timeInterval.startTime,
                      x.value]
            price_data.append(datum)

        filename = self.name + ".csv"
        full_filename = data_folder + filename

        my_file = open(full_filename, 'w+')
        with my_file:
            writer = csv.writer(my_file)
            writer.writerows(price_data)

        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def transition_from_reconcile_to_expired(self, mtn):
        """
        For activities that should accompany a market object's transition from market state "Reconcile" to "Expired."
        This method may be overwritten by child classes of Market to create alternative market behaviors during this
        transition.
        :param mtn: my transactive node agent object
        :return: None
        """
        pass
        return None
        # ************************************************************************************************** 1911DJH NEW

    # NEW 1911DJH ******************************************************************************************************
    def model_prices(self, date_time, new_price=None, k=14.0):
        """
        Returns the average and standard deviation prices 
        for the provided datetime in this market. If a price is provided, too,
        then the price model is updated using this price in the given date and 
        time.
        Note: In order for this to work, the Market.priceModel table must be
        initialized from its preceeding Market object of the same type, i.e., 
        sharing the same market name.
        INPUTS:
            self: this market object
            date_time: the date and time of the prediction or update. Only the hour
                of this datetime is used in the current implementation.

            new_price: [$/kWh] (optional) price provided to update the model for
                the given date and time
        OUTPUTS:
            avg_price: [$/kWh] average model price for the given date and time
            sd_price: [$/kWh] standard price deviation for given date and time
        """

        h = int(date_time.hour)  # Extract the hour in [0,24] from referenced date_time.

        # Find the current average and standard deviation prices for this market object.
        avg_price = self.priceModel[h][1]
        sd_price = self.priceModel[h][2]

        if new_price is not None:
            sd_price = (((k - 1.0) * sd_price**2 + (avg_price - new_price)**2) / k)**0.5
            avg_price = ((k - 1.0) * avg_price + new_price) / k
            self.priceModel[h] = (avg_price, sd_price)

        return [avg_price, sd_price]
        # ************************************************************************************************** 1911DJH NEW

    def assign_system_vertices(self, mtn):
        # Collect active vertices from neighbor and asset models and reassign them with aggregate system information
        # for all active time intervals.
        #
        # ASSUMPTIONS:
        # - Active time intervals exist and are up-to-date
        # - Local convergence has occurred, meaning that power balance, marginal
        # price, and production costs have been adequately resolved from the
        # local agent's perspective
        # - The active vertices of local asset models exist and are up-to-date.
        # The vertices represent available power flexibility. The vertices
        # include meaningful, accurate production-cost information.
        # - There is agreement locally and in the network concerning the format
        # and content of transactive records
        # - Calls method mkt.sum_vertices in each time interval.
        #
        # INPUTS:
        # mtn - myTransactiveNode object
        #
        # OUTPUTS:
        # - Updates mkt.activeVertices - vertices that define the net system balance and flexibility. The meaning of
        #   the vertex properties are
        # - marginalPrice: marginal price [$/kWh]
        # - cost: total production cost at the vertex [$]. (A locally meaningful blended electricity price is (total
        #   production cost / total production)).
        # - power: system net power at the vertex (The system "clears" where system net power is zero.)

        time_interval_values = [t.startTime for t in self.timeIntervals]

        # Delete any active vertices that are not in active time intervals. This
        # prevents time intervals from accumulating indefinitely.
        self.activeVertices = [x for x in self.activeVertices if x.timeInterval.startTime in time_interval_values]

        for ti in self.timeIntervals:
            # Find and delete existing aggregate active vertices in the indexed
            # time interval. These shall be recreated.
            self.activeVertices = [x for x in self.activeVertices if x.timeInterval.startTime != ti.startTime]

            # Call the utility method mkt.sum_vertices to recreate the
            # aggregate vertices in the indexed time interval. (This method is
            # separated out because it will be used by other methods.)
            s_vertices = self.sum_vertices(mtn, ti)

            # Create and store interval values for each new aggregate vertex v
            for sv in s_vertices:
                iv = IntervalValue(self, ti, self, MeasurementType.SystemVertex, sv)
                self.activeVertices.append(iv)

    def balance(self, mtn):
        """
        Balance current market
        :param mtn: my transactive node object
        :return:
        """
        self.new_data_signal = False

        # Check and update the time intervals at the begining of the process.
        # This should not need to be repeated in process iterations.
        self.check_intervals()

        # Clean up or initialize marginal prices. This should not be
        # repeated in process iterations.
        self.check_marginal_prices(mtn)

        # Set a flag to indicate an unconverged condition.
        self.converged = False

        # Iterate to convergence. "Convergence" here refers to the status of the
        # local convergence of (1) local supply and demand and (2) dual costs.
        # This local convergence says nothing about the additional convergence
        # between transactive neighbors and their calculations.

        # Initialize the iteration counter k
        k = 1

        while not self.converged and k < 100:
            if self.new_data_signal:
                self.converged = False
                return

            # Invite all neighbors and local assets to schedule themselves
            # based on current marginal prices
            self.schedule(mtn)

            # Update the primal and dual costs for each time interval and
            # altogether for the entire time horizon.
            self.update_costs(mtn)

            # Update the total supply and demand powers for each time interval.
            # These sums are needed for the sub-gradient search and for the
            # calculation of blended price.
            self.update_supply_demand(mtn)

            # Check duality gap for convergence.
            # Calculate the duality gap, defined here as the relative difference
            # between total production and dual costs
            if self.totalProductionCost == 0:
                dg = float("inf")
            else:
                dg = self.totalProductionCost - self.totalDualCost  # [$]
                dg = dg / self.totalProductionCost  # [dimensionless. 0.01 is 1#]

            # Display the iteration counter and duality gap. This may be
            # commented out once we have confidence in the convergence of the
            # iterations.
            """
            _log.debug("Market balance iteration %i: (tpc: %f, tdc: %f, dg: %f)" %
                       (k, self.totalProductionCost, self.totalDualCost, dg))
            """

            # Check convergence condition
            if abs(dg) <= self.dualityGapThreshold:  # Converged
                # 1.3.1 System has converged to an acceptable balance.
                self.converged = True

            # System is not converged. Iterate. The next code in this
            # method revised the marginal prices in active intervals to drive
            # the system toward balance and convergence.

            # Gather active time intervals ti
            tis = self.timeIntervals  # TimeIntervals

            # A parameter is used to determine how the computational agent
            # searches for marginal prices.
            #
            # Method 1: Subgradient Search - This is the most general solution
            # technique to be used on non-differentiable solution spaces. It uses the
            # difference between primal costs (mostly production costs, in this case)
            # and dual costs (which are modified using gross profit or consumer cost)
            # to estimate the magnitude of power imbalance in each active time
            # interval. Under certain conditions, a solution is guaranteed. Many
            # iterations may be needed. The method can be fooled, so I've found, by
            # interim oscillatory solutions. This method may fail when large
            # assets have linear, not quadratic, cost functions.
            #
            # Methods 2: Interpolation - If certain requirements are met, the solution
            # might be greatly accelerated by interpolating between the inflection
            # points of the net power curve.
            # Requirement 1: All Neighbors and LocalAssets are represented by linear
            # or quadratic cost functions, thus ensuring that the net power curve
            # is perfectly linear between its inflection points.
            # Requirement 2: All Neighbors and Assets update their active vertices in
            # a way that represents their residual flexibility, which can be none,
            # thus ensuring a meaningful connection between balancing in time
            # intervals and scheduling of the individual Neighbors and LocalAssets.
            # This method might fail when many assets do complex scheduling of
            # their flexibility.

            if self.method == 2:
                self.assign_system_vertices(mtn)
                av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
#                _log.debug("{} market active vertices are: {}".format(self.name, av))

            # Index through active time intervals.
            for i in range(len(tis)):
                # Find the marginal price interval value for the
                # corresponding indexed time interval.
                mp = find_obj_by_ti(self.marginalPrices, tis[i])

                # Extract its  marginal price value.
                xlamda = mp.value  # [$/kWh]

                if self.method == 1:
                    # Find the net power corresponding to the indexed time interval.
                    np = find_obj_by_ti(self.netPowers, tis[i])
                    tg = find_obj_by_ti(self.totalGeneration, tis[i])
                    td = find_obj_by_ti(self.totalDemand, tis[i])

                    np = np.value / (tg.value - td.value)

                    # Update the marginal price using subgradient search.
                    xlamda = xlamda - (np * 1e-1) / (10 + k)  # [$/kWh]

                elif self.method == 2:
                    # Get the indexed active system vertices
                    av = [x.value for x in self.activeVertices if x.timeInterval.startTime == tis[i].startTime]

                    # Order the system vertices in the indexed time interval
                    av = order_vertices(av)

                    try:
                        # Find the vertex that bookcases the balance point from the lower side.
                        # Fix a case where all intersection points are on X-axis by using < instead of <=
                        lower_av = [x for x in av if x.power < 0]
                        if len(lower_av) == 0:
                            err_msg = "At {}, there is no point having power < 0".format(tis[i].name)
                        else:
                            lower_av = lower_av[-1]

                        # Find the vertex that bookcases the balance point from the upper side.
                        upper_av = [x for x in av if x.power >= 0]
                        if len(upper_av) == 0:
                            err_msg = "At {}, there is no point having power >= 0".format(tis[i].name)
                        else:
                            upper_av = upper_av[0]

                        # Interpolate the marginal price in the interval using a
                        # principle of similar triangles.
                        power_range = upper_av.power - lower_av.power
                        mp_range = upper_av.marginalPrice - lower_av.marginalPrice
                        if power_range == 0:
                            err_msg = "At {}, power range is 0".format(tis[i].name)
                        xlamda = - mp_range * lower_av.power / power_range + lower_av.marginalPrice
                    except:
                        """
                        _log.error(err_msg)
                        _log.error("{} failed to find balance point. "
                                   "Market active vertices: {}".format(mtn.name,
                                                                       [(tis[i].name, x.marginalPrice, x.power)
                                                                        for x in av]))
                        """

                        self.converged = False
                        return

                # Regardless of the method used, variable "xlamda" should now hold
                # the updated marginal price. Assign it to the marginal price
                # value for the indexed active time interval.
                mp.value = xlamda  # [$/kWh]

            # Increment the iteration counter.
            k = k + 1
            if k == 100:
                self.converged = True

            if self.new_data_signal:
                self.converged = False
                return

    def calculate_blended_prices(self):
        # Calculate the blended prices for active time intervals.
        #
        # The blended price is the averaged weighted price of all locally
        # generated and imported energies. A sum is made of all costs of
        # generated and imported energies, which are prices weighted by their
        # corresponding energy. This sum is divided by the total generated and
        # imported energy to get the average.
        #
        # The blended price does not include supply surplus and may therefore be
        # a preferred representation of price for local loads and friendly
        # neighbors, for which myTransactiveNode is not competitive and
        # profit-seeking.

        # Update and gather active time intervals ti. It's simpler to
        # recalculate the active time intervals than it is to check for
        # errors.

        self.check_intervals()
        ti = self.timeIntervals

        # Gather primal production costs of the time intervals.
        pc = self.productionCosts

        # Perform checks on interval primal production costs to ensure smooth
        # calculations. NOTE: This does not check the veracity of the
        # primal costs.

        # CASE 1: No primal production costs have been populated for the various
        # assets and neighbors. This results in termination of the
        # process.

        if pc is None or len(pc) == 0:  # isempty(pc)
            #            _log.warning('Primal costs have not yet been calculated.')
            return

        # CASE 2: There is at least one active time interval for which primal
        # costs have not been populated. This results in termination of the
        # process.

        elif len(ti) > len(pc):
            #            _log.warning('Missing primal costs for active time intervals.')
            return

        # CASE 3: There is at least one extra primal production cost that does
        # not refer to an active time interval. It will be removed.

        elif len(ti) < len(pc):
            #            _log.warning('Removing primal costs that are not among active time intervals.')
            self.productionCosts = [x for x in self.productionCosts if x.timeInterval in self.timeIntervals]

        for i in range(len(ti)):
            pc = find_obj_by_ti(self.productionCosts, ti[i])
            tg = find_obj_by_ti(self.totalGeneration, ti[i])
            bp = pc / tg

            self.blendedPrices1 = [x for x in self.blendedPrices1 if x != ti[i]]

            val = bp
            iv = IntervalValue(self, ti[i], self, MeasurementType.BlendedPrice, val)

            # Append the blended price to the list of interval values
            self.blendedPrices1.append(iv)

    # 1911DJH: This next code is really unnecessary now that market timing logic has been simplified. Knowing one
    # market clearing time, one may find the next by simply adding the market clearing interval.
    def update_market_clearing_time(self, cur_time):
        self.marketClearingTime = cur_time.replace(minute=0, second=0, microsecond=0)
        self.nextMarketClearingTime = self.marketClearingTime + timedelta(hours=1)

    # CHANGED 1911DJH **************************************************************************************************
    def check_intervals(self):
        # Check or create the set of instantiated TimeIntervals in this Market

        # Create the array "steps" of interval's starting times that should be active. Assign the first based
        # on the known market clearing time.
        steps = [self.marketClearingTime + self.deliveryLeadTime]  # First market interval start time

        # The end of the market delivery time may be found from the first starting time.
        end_time = steps[0] + self.intervalDuration * self.intervalsToClear

        # Assign the remaining interval start times in the market delivery period.
        while steps[-1] < end_time:
            steps.append(steps[-1] + self.intervalDuration)

        # Index through the needed TimeIntervals based on their start times.
        for i in range(len(steps)):
            # This is a test to see whether the interval exists.
            # Case 0: a new interval must be created
            # Case 1: There is one match, the TimeInterval exists
            # Otherwise: Duplicates exists and should be deleted.
            tis = [x for x in self.timeIntervals if x.startTime == steps[i]]
            tis_len = len(tis)

            # No match was found. Create a new TimeInterval and append it to the list of time intervals.
            if tis_len == 0:
                #ti = TimeInterval(Timer.get_cur_time(), self.intervalDuration, self, self.marketClearingTime, steps[i])
                ti = TimeInterval(datetime.now(), self.intervalDuration, self, self.marketClearingTime, steps[i])
                self.timeIntervals.append(ti)

            # The TimeInterval already exists. There is really no problem. 
            elif tis_len == 1:
                # All OK. No action to take.
                pass

            # Duplicate time intervals exist. Remove all but one.
            else:
                self.timeIntervals = [x for x in self.timeIntervals if x.startTime != steps[i]]
                self.timeIntervals.append(tis[0])
            # ****************************************************************************************** 1911DJH CHANGED

    # CHANGED 1911DJH **************************************************************************************************
    def check_marginal_prices(self, mtn):
        # todo: Scrub and test market method check_marginal_prices.
        """ 
        1911DJH revision:
        Check that marginal prices exist for active time intervals. 
        Updated Oct. 2019. Focusses now on initializing marginal prices for the market's time intervals. A priority is
        established for the best available prices from which to initialize new market periods:
        1. If the market interval already has a price, stop. 
        2. If the same time interval exists from a prior market clearing, its price may be used. This can be the case
           where similar successive markets' delivery periods overlap, e.g., a rolling window of 24 hours.
        3. If this market corrects another prior market, its cleared price should be used, e.g., a real-time market
           that corrects day-ahead market periods.
        4. If there exists a price forecast model for this market, this model should be used to forecast price. See
           method Market.model_prices().
        5. If all above methods fail, market periods should be assigned the market's default price. See property
           Market.defaultPrice.
        INPUTS:
           mtn      agent myTransactiveNode object
        OUTPUTS:
           populates list of active marginal prices (see class IntervalValue)
        """

        ti = self.timeIntervals

        # Clean up the list of active marginal prices. Remove any active
        # marginal prices that are not in active time intervals.
        self.marginalPrices = [x for x in self.marginalPrices if x.timeInterval in ti]

        # Index through active time intervals ti
        for i in range(len(ti)):
            # Check to see if a marginal price exists in the active time interval
            iv = find_obj_by_ti(self.marginalPrices, ti[i])

            # METHOD #1. If the market interval already has a price, you're done.
            if iv is None:

                try:  # METHOD #2

                    # METHOD #2. If the same time interval exists from a prior market clearing, 
                    # its price may be used. This can be the case where similar successive
                    # markets' delivery periods overlap, e.g., a rolling window of 24
                    # hours.

                    similar_markets = [x for x in mtn.markets if x.marketName == self.marketName
                                       and x is not self and x.marketClearingTime < self.marketClearingTime]

                    if similar_markets is None:
                        raise NameError("No similar markets were found")  # raise error

                    else:
                        most_recent_market = [x for x in similar_markets
                                              if x.marketClearingTime == max(x.marketClearingTime)]

                        mps = most_recent_market[0].marginalPrices

                        if mps is None:
                            raise NameError("No marginal price was found")  # raise error

                        else:
                            value = [x for x in mps
                                     if mps.timeInterval.startTime < ti[i].startTime < mps.timeInterval.startTime
                                     + most_recent_market.intervalDuration][0].value

                except NameError:
                    pass

                    try:  # METHOD #3

                        # METHOD #3. If this market corrects another prior market,  
                        # its cleared price should be used, e.g., a real-time market that
                        # corrects day-ahead market periods.

                        prior_market = self.priorMarket
                        if prior_market is None:
                            raise NameError("No prior market was found")  # raise error

                        else:
                            mps = prior_market.marginalPrices

                            if mps is None:
                                raise NameError("No marginal prices are found")

                            else:
                                value = [x for x in mps if mps.timeInterval.startTime <=
                                         ti[i].startTime < mps.timeInterval.startTime
                                         + prior_market.intervalDuration][0].value

                    except NameError:
                        pass

                        try:  # METHOD #4

                            # METHOD #4. If there exists a price forecast model for this market, this model should be
                            # used to forecast price. See method Market.model_prices().

                            value = self.model_prices(ti[i].startTime)

                        except NameError:
                            pass
                 
                            try:  # METHOD #5

                                # METHOD 5. If all above methods fail, market periods should be assigned the market's
                                # default price. See property Market.defaultPrice. However, if there is not default
                                # price, then the price should be assigned as NaN.

                                if self.defaultPrice is None:
                                    raise NameError("No default price was found")  # raise error

                                else:
                                    value = 'NaN'

                            except NameError:
                                value = 'NaN'

                # Create an interval value for the new marginal price in the indexed time interval with either the
                # default price or the marginal price from the previous active time interval.
                iv = IntervalValue(self, ti[i], self, MeasurementType.MarginalPrice, value)

                # Append the marginal price value to the list of active marginal prices
                self.marginalPrices.append(iv)

            return None
            # ****************************************************************************************** 1911DJH CHANGED

    def schedule(self, mtn):
        # Process called to
        # (1) invoke all models to update the scheduling of their resources, loads, or neighbor
        # (2) converge to system balance using sub-gradient search.
        #
        # mkt - Market object
        # mtn - my transactive node object

        # 1.2.1 Call resource models to update their schedules
        # Call each local asset model m to schedule itself.
        for la in mtn.localAssets:
            la.model.schedule(self)

        # 1.2.2 Call neighbor models to update their schedules
        # Call each neighbor model m to schedule itself
        for n in mtn.neighbors:
            n.model.schedule(self)

    def sum_vertices(self, mtn, ti, ote=None):
        # Create system vertices with system information for a single time interval. An optional argument allows the
        # exclusion of a transactive neighbor object, which is useful for transactive records and their corresponding
        # demand or supply curves. This utility method should be used for creating transactive signals (by excluding
        # the neighbor object), and for visualization tools that review the local system's net supply/demand curve.

        # Initialize a list of marginal prices mps at which vertices will be created.
        mps = []

        # Index through the active neighbor objects
        for i in range(len(mtn.neighbors)):

            # Change the reference to the corresponding neighbor model
            nm = mtn.neighbors[i].model

            # Jump out of this iteration if neighbor model nm happens to be the
            # "object to exclude" ote
            if ote is not None and nm == ote:
                continue

            # Find the neighbor model's active vertices in this time interval
            mp = find_objs_by_ti(nm.activeVertices, ti)  # IntervalValues

            if len(mp) > 0:
                # At least one active vertex was found in the time interval
                # Extract the vertices from the interval values
                mp = [x.value for x in mp]  # Vertices

                if len(mp) == 1:
                    # There is one vertex. This means the power is constant for
                    # this neighbor. Enforce the policy of assigning infinite
                    # marginal price to constant vertices.
                    mp = [float("inf")]  # marginal price [$/kWh]

                else:
                    # There are multiple vertices. Use the marginal price values
                    # from the vertices themselves.
                    mp = [x.marginalPrice for x in mp]  # marginal prices [$/kWh]

                mps.extend(mp)  # marginal prices [$/kWh]

        for i in range(len(mtn.localAssets)):
            # Change the reference to the corresponding local asset model
            nm = mtn.localAssets[i].model  # a local asset model

            # Jump out of this iteration if local asset model nm happens to be
            # the "object to exclude" ote
            if ote is not None and nm == ote:
                continue

            # Find the local asset model's active vertices in this time interval
            mp = find_objs_by_ti(nm.activeVertices, ti)

            if len(mp) > 0:
                # At least one active vertex was found in the time interval
                # Extract the vertices from the interval values
                mp = [x.value for x in mp]  # mp = [mp.value]  # Vertices

                # Extract the marginal prices from the vertices
                if len(mp) == 1:
                    # There is one vertex. This means the power is constant for
                    # this local asset. Enforce the policy of assigning infinite
                    # marginal price to constant vertices.
                    mp = [float("inf")]  # marginal price [$/kWh]

                else:
                    # There are multiple vertices. Use the marginal price values
                    # from the vertices themselves.
                    mp = [x.marginalPrice for x in mp]  # marginal prices [$/kWh]

                mps.extend(mp)  # marginal prices [$/kWh]

        # Trim mps, which was originally padded with zeros.
        # mps = mps(1:mps_cnt)  # marginal prices [$/kWh]

        # A list of vertex marginal prices have been created.

        # Sort the marginal prices from least to greatest
        mps.sort()  # marginal prices [$/kWh]

        # Ensure that no more than two vertices will be created at the same
        # marginal price. The third output of function unique() is useful here
        # because it is the index of unique entries in the original vector.
        # [~, ~, ind] = unique(mps)  # index of unique vector contents

        # Create a new vector of marginal prices. The first two entries are
        # accepted because they cannot violate the two-duplicates rule. The
        # vector is padded with zeros, which should be computationally efficient.
        # A counter is used and should be incremented with new vector entries.
        mps_new = None
        if len(mps) >= 3:
            mps_new = [mps[0], mps[1]]
        else:
            mps_new = list(mps)

        # Index through the indices and append the new list only when there are
        # fewer than three duplicates.
        for i in range(2, len(mps)):
            if mps[i] != mps[i - 1] or mps[i - 1] != mps[i - 2]:
                mps_new.append(mps[i])

        # Trim the new list of marginal prices mps_new that had been padded with
        # zeros and rename it mps
        # mps = mps_new  # marginal prices [$/kWh]

        # [180907DJH: THIS CONDITIONAL (COMMENTED OUT) WAS NOT QUITE RIGHT. A
        # MARGINAL PRICE AT INFINITY IS MEANINGFUL ONLY IF THERE IS EXACTLY ONE
        # VERTEX-NO FLEXIBILITY. OTHERWISE, IT IS SUPERFLUOUS AND SHOULD BE
        # ELIMINATED. THIS MUCH SIMPLER APPROACH ENSURES THAT INFINITY IS RETAINED
        # ONLY IF THERE IS A SINGLE MARGINAL PRICE. OTHERWISE, INFINITY MARGINAL
        # PRICES ARE TRIMMED FROM THE SET.]
        mps = [mps_new[0]]
        for i in range(1, len(mps_new)):
            if mps_new[i] != float('inf'):
                mps.append(mps_new[i])

        # if len(mps) >= 2:
        # There are at least two marginal prices. (This is a condition that is unlikely but was found in testing of
        # version 1.1.)
        #     if mps[-1] == float('inf') and mps[-2] == float('inf'):
        #         # A duplicate infinite marginal price, which is used to indicate a
        #         # constant, inelastic power, is not meaningful and must be deleted
        #         # from the end of the list of marginal prices mps.
        #         mps.pop()

        # A clean list of marginal prices has been created

        # Correct assignment of vertex power requires a small offset of any
        # duplicate values. Index through the new list of marginal prices again.
        for i in range(1, len(mps)):
            if mps[i] == mps[i - 1]:
                # A duplicate has been found. Offset the first of the two by a
                # very small number
                mps[i - 1] = mps[i - 1] - 1e-10  # marginal prices [$/kWh]

        # Create vertices at the marginal prices
        # Initialize the list of vertices
        vertices = []

        # Index through the cleaned list of marginal prices
        for i in range(len(mps)):
            # Create a vertex at the indexed marginal price value
            iv = Vertex(mps[i], 0, 0)

            # Initialize the net power pwr and total production cost pc at the
            # indexed vertex
            pwr = 0.0  # net power [avg.kW]
            pc = 0.0  # production cost [$]

            # Include power and production costs from neighbor models
            # Index through the active neighbor models
            for k in range(len(mtn.neighbors)):
                nm = mtn.neighbors[k].model

                if nm == ote:
                    continue

                # Calculate the indexed neighbor model's power at the indexed
                # marginal price and time interval. NOTE: This must not corrupt
                # the "scheduled power" at the converged system's marginal price.
                p = production(nm, mps[i], ti)  # power [avg.kW]

                # Calculate the neighbor model's production cost at the indexed
                # marginal price and time interval, and add it to the sum
                # production cost pc. NOTE: This must not corrupt the "scheduled"
                # production cost for this neighbor model.
                pc = pc + prod_cost_from_vertices(nm, ti, p)  # production cost [$]

                # Add the neighbor model's power to the sum net power at this vertex.
                pwr = pwr + p  # net power [avg.kW]

            # Include power and production costs from local asset models
            # Index through the local asset models
            for k in range(len(mtn.localAssets)):
                nm = mtn.localAssets[k].model

                if nm == ote:
                    continue

                # Calculate the power for the indexed local asset model at the
                # indexed marginal price and time interval.
                p = production(nm, mps[i], ti)  # power [avg.kW]

                # Find the indexed local asset model's production cost and add it
                # to the sum of production cost pc for this vertex.
                pc = pc + prod_cost_from_vertices(nm, ti, p)  # production cost [$]

                # Add local asset power p to the sum net power pwr for this vertex.
                pwr = pwr + p  # net power [avg.kW]

            # Save the sum production cost pc into the new vertex iv
            iv.cost = pc  # sum production cost [$]

            # Save the net power pwr into the new vertex iv
            iv.power = pwr  # net power [avg.kW]

            # Append Vertex iv to the list of vertices
            vertices.append(iv)

        return vertices

    def update_costs(self, mtn):
        # Sum the production and dual costs from all modeled local resources, local
        # loads, and neighbors, and then sum them for the entire duration of the
        # time horizon being calculated.
        #
        # PRESUMPTIONS:
        # - Dual costs have been created and updated for all active time
        # intervals for all neighbor objects
        # - Production costs have been created and updated for all active time
        # intervals for all asset objects
        #
        # INTPUTS:
        # mtn - my Transactive Node object
        #
        # OUTPUTS:
        # - Updates Market.productionCosts - an array of total production cost in each active time interval
        # - Updates Market.totalProductionCost - the sum of production costs for the entire future time horizon of
        #   active time intervals
        # - Updates Market.dualCosts - an array of dual cost for each active time interval
        # - Updates Market.totalDualCost - the sum of all the dual costs for the entire future time horizon of active
        #   time intervals

        # Call each LocalAssetModel to update its costs
        for la in mtn.localAssets:
            la.model.update_costs(self)

        # Call each NeighborModel to update its costs
        for n in mtn.neighbors:
            n.model.update_costs(self)

        for i in range(1, len(self.timeIntervals)):
            ti = self.timeIntervals[i]
            # Initialize the sum dual cost sdc in this time interval
            sdc = 0.0  # [$]

            # Initialize the sum production cost spc in this time interval
            spc = 0.0  # [$]

            for la in mtn.localAssets:
                iv = find_obj_by_ti(la.model.dualCosts, ti)
                sdc = sdc + iv.value  # sum dual cost [$]

                iv = find_obj_by_ti(la.model.productionCosts, ti)
                spc = spc + iv.value  # sum production cost [$]

            for n in mtn.neighbors:
                iv = find_obj_by_ti(n.model.dualCosts, ti)
                sdc = sdc + iv.value  # sum dual cost [$]

                iv = find_obj_by_ti(n.model.productionCosts, ti)
                spc = spc + iv.value  # sum production cost [$]

            # Check to see if a sum dual cost exists in the indexed time interval
            iv = find_obj_by_ti(self.dualCosts, ti)

            if iv is None:
                # No dual cost was found for the indexed time interval. Create
                # an IntervalValue and assign it the sum dual cost for the
                # indexed time interval
                iv = IntervalValue(self, ti, self, MeasurementType.DualCost, sdc)  # an IntervalValue

                # Append the dual cost to the list of interval dual costs
                self.dualCosts.append(iv)  # = [mkt.dualCosts, iv]  # IntervalValues

            else:
                # A sum dual cost value exists in the indexed time interval.
                # Simply reassign its value
                iv.value = sdc  # sum dual cost [$]

            # Check to see if a sum production cost exists in the indexed time interval
            iv = find_obj_by_ti(self.productionCosts, ti)

            if iv is None:
                # No sum production cost was found for the indexed time
                # interval. Create an IntervalValue and assign it the sum
                # production cost for the indexed time interval
                iv = IntervalValue(self, ti, self, MeasurementType.ProductionCost, spc)

                # Append the production cost to the list of interval production costs
                self.productionCosts.append(iv)

            else:
                # A sum production cost value exists in the indexed time
                # interval. Simply reassign its value
                iv.value = spc  # sum production cost [$]

        # Sum total dual cost for the entire time horizon
        self.totalDualCost = sum([x.value for x in self.dualCosts])  # [$]

        # Sum total primal cost for the entire time horizon
        self.totalProductionCost = sum([x.value for x in self.productionCosts])  # [$]

    def update_supply_demand(self, mtn):
        # For each time interval, sum the power that is generated, imported,
        # consumed, or exported for all modeled local resources, neighbors, and
        # local load.

        # Extract active time intervals
        time_intervals = self.timeIntervals  # active TimeIntervals

        time_interval_values = [t.startTime for t in time_intervals]
        # Delete netPowers not in active time intervals
        self.netPowers = [x for x in self.netPowers if x.timeInterval.startTime in time_interval_values]

        # Index through the active time intervals ti
        for i in range(1, len(time_intervals)):
            # Initialize total generation tg
            tg = 0.0  # [avg.kW]

            # Initialize total demand td
            td = 0.0  # [avg.kW]

            # Index through local asset models m.
            m = mtn.localAssets

            for k in range(len(m)):
                mo = find_obj_by_ti(m[k].model.scheduledPowers, time_intervals[i])

                # Extract and include the resource's scheduled power
                p = mo.value  # [avg.kW]

                if p > 0:  # Generation
                    # Add positive powers to total generation tg
                    tg = tg + p  # [avg.kW]

                else:  # Demand
                    # Add negative powers to total demand td
                    td = td + p  # [avg.kW]

            # Index through neighbors m
            m = mtn.neighbors

            for k in range(len(m)):
                # Find scheduled power for this neighbor in the indexed time interval
                mo = find_obj_by_ti(m[k].model.scheduledPowers, time_intervals[i])

                # Extract and include the neighbor's scheduled power
                p = mo.value  # [avg.kW]

                if p > 0:  # Generation
                    # Add positive power to total generation tg
                    tg = tg + p  # [avg.kW]

                else:  # Demand
                    # Add negative power to total demand td
                    td = td + p  # [avg.kW]

            # At this point, total generation and importation tg, and total
            # demand and exportation td have been calculated for the indexed
            # time interval ti[i]

            # Save the total generation in the indexed time interval

            # Check whether total generation exists for the indexed time interval
            iv = find_obj_by_ti(self.totalGeneration, time_intervals[i])

            if iv is None:
                # No total generation was found in the indexed time interval.
                # Create an interval value.
                iv = IntervalValue(self, time_intervals[i], self, MeasurementType.TotalGeneration, tg)  # IntervalValue

                # Append the total generation to the list of total generations
                self.totalGeneration.append(iv)

            else:
                # Total generation exists in the indexed time interval. Simply
                # reassign its value.
                iv.value = tg

            # Calculate and save total demand for this time interval.
            # NOTE that this formulation includes both consumption and
            # exportation among total load.

            # Check whether total demand exists for the indexed time interval

            iv = find_obj_by_ti(self.totalDemand, time_intervals[i])
            if iv is None:
                # No total demand was found in the indexed time interval. Create
                # an interval value.
                iv = IntervalValue(self, time_intervals[i], self, MeasurementType.TotalDemand, td)  # an IntervalValue

                # Append the total demand to the list of total demands
                self.totalDemand.append(iv)

            else:
                # Total demand was found in the indexed time interval. Simply reassign it.
                iv.value = td

            # Update net power for the interval
            # Net power is the sum of total generation and total load.
            # By convention generation power is positive and consumption
            # is negative.

            # Check whether net power exists for the indexed time interval
            iv = find_obj_by_ti(self.netPowers, time_intervals[i])

            if iv is None:
                # Net power is not found in the indexed time interval. Create an interval value.
                iv = IntervalValue(self, time_intervals[i], self, MeasurementType.NetPower, tg + td)

                # Append the net power to the list of net powers
                self.netPowers.append(iv)
            else:
                # A net power was found in the indexed time interval. Simply reassign its value.
                iv.value = tg + td

        np = [(x.timeInterval.name, x.value) for x in self.netPowers]
        #        _log.debug("{} market netPowers are: {}".format(self.name, np))
