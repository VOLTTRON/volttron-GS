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
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
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

import logging
import os
import socket
import subprocess
import sys
import json
from datetime import datetime
from collections import defaultdict
from gevent import monkey, sleep
from inspect import getcallargs
import gevent

from math import modf
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

monkey.patch_socket()
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.scheduling import periodic

utils.setup_logging()
log = logging.getLogger(__name__)
SUCCESS = 'SUCCESS'
FAILURE = 'FAILURE'


class SocketServer:
    """
    Socket server class that facilitates communication with Modelica.
    """
    def __init__(self, port, host):
        #self.sock = socket.socket()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.client = None
        self.received_data = None
        self.size = 4096
        log.debug('Bound to %r on %r' % (port, host))

    def run(self):
        self.listen()

    def listen(self):
        self.sock.listen(10)
        log.debug('server now listening')
        self.client, addr = self.sock.accept()
        while True:
            self.client, addr = self.sock.accept()
            log.debug('Connected with ' + addr[0] + ':' + str(addr[1]))
            data = self.receive_data()
            data = data.decode("utf-8")
            log.debug("Modelica data %s", data)
            if data:
                self.received_data = data
                self.on_receive_data(data)

    def receive_data(self):
        if self.client is not None and self.sock is not None:
            try:
                data = self.client.recv(self.size)
            except Exception:
                log.error('We got an error trying to read a message')
                data = None
            return data

    def on_receive_data(self, data):
        log.debug('Received %s', data)


class ModelicaAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super().__init__(**kwargs)
        config = utils.load_config(config_path)
        self.remote_ip = config.get("remote_ip", "127.0.0.1")
        self.remote_port = config.get("remote_port", 8888)

        outputs = config.get("outputs", {})
        inputs = config.get("inputs", {})
        self.control_map = {}
        self.control_topic_map = {}
        self.controls_list_master = set()
        self.controls_list = []
        self.control_proceed = set()
        self.topic_map = None
        self.data_map = None
        self.data_map_master = None
        self.output_data = defaultdict(list)
        self.create_control_map(inputs)
        self.create_topic_map(outputs)
        self.current_control = None
        self.modelica_connection = None
        self.data = None
        self.timestep_interval = config.get("timestep_interval", 30)
        self.output_map = None
        self.socket_server = None
        self.test_topics = ["building/device/control_output", "building/device/control_setpoint"]
        self.test_topics_master = list(self.test_topics)

    def create_topic_map(self, outputs):
        topic_map = {}
        data_map = {}

        for modelica_name, info in outputs.items():
            topic = info["topic"]
            topic_map[modelica_name] = topic
            data_map[modelica_name] = info
            self.output_data[topic] = [{}, {}]
        self.topic_map = topic_map
        self.data_map = data_map
        self.data_map_master = dict(data_map)
        log.debug("topic %s -- data %s", self.topic_map, self.data_map)

    def create_control_map(self, inputs):
        for name, info in inputs.items():
            topic = "/".join([info["topic"], info["field"]])
            self.control_topic_map[topic] = name
            self.control_map[name] = {"value": 0, "nextSampleTime": 1, "enable": False}
            self.controls_list_master = set(self.control_map.keys())
            self.controls_list = list(self.controls_list_master)
            log.debug("Control map %s", self.control_map)

    @Core.schedule(periodic(30))
    def next_timestep(self):
        if self.data is None:
            return
        topic = self.test_topics.pop()
        value = self.set_point("me", topic, 1.0)
        if not self.test_topics:
            self.test_topics = list(self.test_topics_master)

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        self.start_socket_server()

    def start_socket_server(self):
        self.socket_server = SocketServer(port=self.remote_port, host=self.remote_ip)
        self.socket_server.on_receive_data = self.receive_data_dymola
        self.core.spawn(self.socket_server.run)

    def start_simulation(self):
        pass

    def send_control_modelica(self):
        pass

    def receive_data_dymola(self, data):
        data = json.loads(data)
        self.data = data
        log.debug("Modelica Agent receive data %s - %s", data, type(data))
        if isinstance(data, list):
            self.current_control = data
            name = data[0]
            self.control_proceed.add(name)
        else:
            self.publish_modelic_data(data)
        if not self.controls_list:
            if self.control_proceed == self.controls_list_master:
                self.reinit_control_lists()
            self.send_control_signal(self.current_control)
            log.debug("CONTROLS %s -------%s", self.control_proceed, self.controls_list_master)

    def reinit_control_lists(self):
        log.debug("REINIT CONTROLS LIST")
        self.controls_list = list(self.controls_list_master)
        self.control_proceed = set()

    def send_control_signal(self, control):
        msg = {}
        name = control[0]
        _time = control[1]
        self.control_map[name]["nextSampleTime"] = _time + self.timestep_interval - 1
        msg[name] = self.control_map[name]
        msg = json.dumps(msg)
        log.debug("SEND CONTROL: %s", msg)
        msg = json.dumps(msg)
        msg = msg + '\0'
        msg = msg.encode()
        self.socket_server.client.send(msg)

    def publish_modelic_data(self, data):
        log.debug("Modelica publish method %s", data)
        self.construct_data_payload(data)
        for key in data:
            self.data_map.pop(key)
        if self.data_map:
            return
        for topic, value in self.output_data.items():
            self.data_map = dict(self.data_map_master)
            headers = {"Timestep": self.time_step}
            log.debug("Publish - topic %s ----- payload %s", topic, value)
            self.vip.pubsub.publish("pubsub", topic, headers=headers, message=value)

    def construct_data_payload(self, data):
        for key, payload in data.items():
            topic = self.topic_map[key]
            data_map = self.data_map_master[key]
            name = data_map["field"]
            value = payload["value"]
            meta = data_map["meta"]
            self.time_step = payload["time"]
            self.output_data[topic][0].update({name: value})
            self.output_data[topic][1].update({name: meta})

    def exit(self, msg):
        self.stop()
        log.error(msg)

    def stop(self):
        if self.socket_server:
            self.socket_server.stop()
            self.socket_server = None

    @RPC.export
    def request_cancel_schedule(self, requester_id, task_id):
        """RPC method

        Requests the cancelation of the specified task id.
        In this agent, this does nothing!

        :param requester_id: Requester name.
        :param task_id: Task name.

        :type requester_id: str
        :type task_id: str
        :returns: Request result
        :rtype: dict

        """
        log.debug(requester_id + " canceled " + task_id)
        result = {'result': SUCCESS,
                  'data': {},
                  'info': ''}
        return result

    @RPC.export
    def get_point(self, topic, **kwargs):
        """RPC method

        Gets the value of a specific point on a device_name.
        Does not require the device_name be scheduled.

        :param topic: The topic of the point to grab in the
                      format <device_name topic>/<point name>
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :returns: point value
        :rtype: any base python type

        """
        pass

    @RPC.export
    def set_point(self, requester_id, topic, value, **kwargs):
        """RPC method

        Sets the value of a specific point on a device.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the point to set in the
                      format <device topic>/<point name>
        :param value: Value to set point to.
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str
        :type value: any basic python type
        :returns: value supplied
        :rtype: any base python type

        """
        log.debug("Modelica agent handle_set")
        log.debug("topic: %s -- value: %s", topic, value)
        try:
            name = self.control_topic_map[topic]
            self.control_map[name]["value"] = value
            self.control_map[name]["enable"] = True
        except KeyError as ex:
            log.debug("Topic does not match any know control points: %s", topic)
        #try:
        self.controls_list.remove(name)
        log.debug("Controls list %s", self.controls_list)
        if not self.controls_list:
            self.send_control_signal(self.current_control)
        #except ValueError as ex:
            #log.warning("Received duplicate set point for topic: %s - name: %s", topic, name)
            #self.send_control_signal(self.current_control)
        return value

    @RPC.export
    def revert_point(self, requester_id, topic, **kwargs):
        """RPC method

        Reverts the value of a specific point on a device to a default state.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the point to revert in the
                      format <device topic>/<point name>
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str

        """
        pass

    @RPC.export
    def revert_device(self, requester_id, device_name, **kwargs):
        """RPC method

        Reverts all points on a device to a default state.
        Does not require the device be scheduled.

        :param requester_id: Identifier given when requesting schedule.
        :param topic: The topic of the device to revert (without a point!)
        :param **kwargs: These get dropped on the floor
        :type topic: str
        :type requester_id: str

        """
        pass

    def advance_simulation(self, peer, sender, bus, topic, headers, message):
        pass


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(ModelicaAgent)
    except Exception as e:
        log.exception(e)


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())