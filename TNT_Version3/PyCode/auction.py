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
from logging import warning

from market import Market
from direction import Direction
from market_types import MarketTypes

class Auction(Market):
    """
    Auction class child of Market
    An Auction object may be a formal driver of myTransactiveNode's responsibilities within a formal auction. At least one
    Market must exist (see the firstMarket object) to drive the timing with which new TimeIntervals are created.
    """
    def __init__(self):
        # Properties and methods inherited from Market class:
        super(Auction, self).__init__(market_type=MarketTypes.auction)

    def while_in_negotiation(self, mtn):
        """"
        In an auction, market state "Negotiation" is simply used to schedule local assets. There is no iteration of
        these schedules in an auction, so the negotiation period should simply provide enough lead time for all the
        local assets to schedule themselves. The local asset models in an auction must know how to proceed when no
        prices are available for the market time intervals, as is the case for an auction (i.e. they must proceed
        using a statistical price model of some sort).
        The result of scheduling is that each local asset will create Vertex structs representing its inelastic or
        elastic power consumption. It may further provide at least two additional vertices that represent its price
        elasticity. In an auction, this scheduling is performed for only local assets. Exchanges with neighbor
        agents are determined in later states using time-coordinated transactive signals.
        These actions are conducted only until a satisfactory converged auction has been found.
        """
        if self.converged is False:

            # Each asset model is called upon to schedule itself:
            for x in range(len(mtn.localAssets)):
                local_asset = mtn.localAssets[x]                          # the indexed local asset

                # local_asset_model = x.model
                local_asset.schedule(self)

            #  The single scheduling of local assets was all there was to do in this state, so call the auction
            #  object converged.
            # TODO: Consider using return from local assets should scheduling be unsuccessful. Or confirm scheduling.
            self.converged = True

        else:  # While negotiations are converged, do these activities.
            # TODO: Consider logic that will recheck local asset schedules periodically or upon change.
            pass  # There's currently nothing to do here but wait.

    def while_in_market_lead(self, mtn):
        """
        For activities that should happen while a market object is in its "MarketLead" market state. This method may be
        overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param mtn: my transactive node agent object
        :return: None
        """
        # TODO: This needs a convergence flag logic to assert that all bids are received and offers sent.
        # Identify the set of neighbor agents that are identified as "upstream" and "downstream".
        upstream_agents = []
        downstream_agents = []

        for x in range(len(mtn.neighbors)):
            neighbor = mtn.neighbors[x]                                         # the indexed neighbor

            if neighbor.upOrDown == Direction.upstream:

                # list of neighbor agents that are "upstream" (i.e., toward electricity supply)
                upstream_agents.append(neighbor)

            elif neighbor.upOrDown == Direction.downstream:

                # list of neighbor agents that are "downstream" (i.e., toward electricity demand)
                downstream_agents.append(neighbor)

            else:

                print('Warning: Assigning neighbor ' + neighbor.name + ' the downstream direction')
                neighbor.upOrDown = Direction.downstream
                # raise Warning("A neighbor must be either 'upstream' nor 'downstream' for an auction market.")

        if len(upstream_agents) != 1:
            print('Warning: There should be precisely one upstream neighbor for an auction market')
            # raise Warning('There should be precisely one upstream neighbor for an auction market')

        # Initialize a flag true if all downstream bids have been received. An aggregate auction bid can be constructed
        # only after all bids have been received from downstream agents (and from local assets, of course):
        all_received = True                                                 # a local flag to this method

        # Index through the downstream agents.
        for da in range(len(downstream_agents)):
            downstream_agent = downstream_agents[da]                        # the indexed downstream agent

            # Establish a list for the time intervals for which records have been received by this downstream agent.
            received_time_interval_names = []

            for rs in range(len(downstream_agent.receivedSignal)):
                received_record = downstream_agent.receivedSignal[rs]       # the indexed received record

                received_time_interval_names.append(received_record.timeInterval)

            # Seek any active market time intervals that were not among the received transactive records.
            missing_interval_names = [x.name for x in self.timeIntervals
                                      if x.name not in received_time_interval_names]

            # If any time intervals are found to be missing for this downstream agent,
            if len(missing_interval_names):
                all_received = False

                # and call on the downstream agent model to try and receive the signal again:
                downstream_agent.receive_transactive_signal(mtn)

        # If all expected bids have been received from downstream agents, have the downstream neighbor models update
        # their vertices and schedule themselves. The result of this will be an updated set of active vertices for each
        # downstream agent.
        if all_received is True:

            # For each downstream agent,
            for da in range(len(downstream_agents)):
                downstream_agent = downstream_agents[da]            # the indexed downstream agent

                # Have each downstream agent model schedule itself. (E.g., schedule power and schedule elasticity via
                # active vertices.
                downstream_agent.schedule(self)

            # Prepare an aggregated bid for the upstream agent if it is a transactive agent. If the upstream agent is
            # transactive,

            if upstream_agents is None or len(upstream_agents) == 0:
                print('Warning: There must exist one upstream neighbor agent in an auction.')
                # raise Warning('There must exist one upstream neighbor agent in an auction.')

            else:

                upstream_agent = upstream_agents[0]                             # Clear indexing of lone upstream agent

                if upstream_agent.transactive is True:

                    # Call on the upstream agent model to prepare its transactive signal.
                    upstream_agent.prep_transactive_signal(mtn)

                # Send the transactive signal (i.e., aggregated bid) to the upstream agent if it is a transactive agent.
                    upstream_agent.send_transactive_signal(mtn)

    def while_in_delivery_lead(self, mtn):
        """
        For activities that should happen while a market object is in its "DeliveryLead" market state. This method may
        be overwritten by child classes of Market to create alternative market behaviors during this market state.
        mtn: my transactive node agent object
        """
        # Identify the set of neighbor agents that is identified as "downstream" (i.e., toward demand side) and the set
        # that is "upstream" (i.e., toward generation).
        downstream_agents = []
        upstream_agents = []

        for x in range(len(mtn.neighbors)):
            neighbor = mtn.neighbors[x]                             # the indexed neighbor agent

            if neighbor.upOrDown == Direction.downstream:
                downstream_agents.append(neighbor)

            elif neighbor.upOrDown == Direction.upstream:
                upstream_agents.append(neighbor)

            else:
                Warning('Assigning neighbor ' + neighbor.name + 'downstream direction.')
                neighbor.upOrDown = Direction.downstream
                raise warning("A neighbor must be neither 'upstream' nor 'downstream' for an auction market")

        assert len(upstream_agents) == 1, "An auction must have precisely one upstream agent"

        # Initialize a flag true if all downstream bids have been received. An aggregate auction bid can be constructed
        # only after all bids have been received from downstream agents (and from local assets, of course):
        all_received = True                                                 # a local parameter to this method

        # Clarify that we are referencing the lone upstream agent model.
        upstream_agent = upstream_agents[0]

        if upstream_agent.transactive is True:

            # Create a list of the time interval names among the received transactive signal:
            received_time_intervals = []

            for rts in range(len(upstream_agent.receivedSignal)):
                received_record = upstream_agent.receivedSignal[rts]        # the indexed received record

                received_time_intervals.append(received_record.timeInterval)

            # Check whether any active market time intervals are not among the received record intervals.
            missing_time_intervals = [x.name for x in self.timeIntervals if x.name not in received_time_intervals]

            # If time intervals are missing among the upstream agent's transactive records,
            if missing_time_intervals:

                all_received = False

                # Call on the upstream agent model to try and receive the signal again.
                upstream_agent.receive_transactive_signal(mtn)

        # If offers have been received for all active market time intervals from the upstream agent,
        if all_received is True:

            # have the upstream agent model schedule itself.
            upstream_agent.schedule(self)

            # For each downstream agent
            for x in range(len(downstream_agents)):
                downstream_agent = downstream_agents[x]                 # the indexed downstream agent

                # prepare an aggregated offer for the downstream agent,
                downstream_agent.prep_transactive_signal(mtn)

                # and send it a transactive signal (i.e., an offer).
                downstream_agent.send_transactive_signal(mtn)
