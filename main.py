import logging
import piplates.DAQCplate as DAQC
import piplates.RELAYplate as RELAY
import re
import signal
import sys
import time
import threading
import yaml

from enum import Enum
from mqttBridge import MqttBridge
from os import path
from queue import Queue
from poller import analogPoller, digitalPoller
from time import sleep

class BoardType(Enum):
    NONE = 0
    RELAY = 1
    DAQC = 2

logging.basicConfig(
    filename='/home/pi/piplates/rpBridge/rpBridge.log',
    format='%(asctime)s %(levelname)s: %(message)s',
    #stream = sys.stdout,
    level=logging.DEBUG)

def signal_handling(signum, frame):
    bridge.disconnect()
    for p in pollers:
        p.stop()
        p.join()
    sys.exit("SIGINT received. Bye!")

def getConfig():
    global __allowAnalogPoller, __allowDigitalPoller
    __allowAnalogPoller = 1
    __allowDigitalPoller = 1
    if path.exists("config.yaml"):
        with open(r"config.yaml") as file:
            config = yaml.full_load(file)
            if "mqtt" in config:
                global __broker_address, __broker_port, __broker_topics
                if "address" in config["mqtt"]:
                    __broker_address = config["mqtt"]["address"]
                if "port" in config["mqtt"]:
                    __broker_port = config["mqtt"]["port"]
                if "clientName" in config["mqtt"]:
                    __broker_clientName = config["mqtt"]["clientName"]
                if "topics" in config["mqtt"]:
                    for topic in config["mqtt"]["topics"]:
                        for key, value in topic.items():
                            __broker_topics[key] = value
                logging.info("mqtt config: {0}:{1} (topics: {2})".format(__broker_address, __broker_port, __broker_topics))
            else:
                logging.warning("no valid mqtt config found")
            if "piplates" in config:
                if "analogPoller" in config["piplates"]:
                    __allowAnalogPoller = config["piplates"]["analogPoller"]
                if "digitalPoller" in config["piplates"]:
                    __allowDigitalPoller = config["piplates"]["digitalPoller"]

def getActiveBoards():
    activeBoards = [BoardType.NONE, BoardType.NONE, BoardType.NONE, BoardType.NONE, BoardType.NONE, BoardType.NONE, BoardType.NONE, BoardType.NONE ]
    for i, d in enumerate(DAQC.daqcsPresent):
        if d == 1:
            activeBoards[i] = BoardType.DAQC
    for i, r in enumerate(RELAY.relaysPresent):
        if r == 1:
            activeBoards[i] = BoardType.RELAY
    print(activeBoards)
    return activeBoards

def getRelayState(board, relay):
    return ("ON", "OFF") [RELAY.relaySTATE(board) & (1 << (relay - 1)) == 0]

def setRelayState(board, relay, newState):
    currentState = getRelayState(board, relay)
    if newState == "ON" and currentState == "OFF":
        RELAY.relayON(board, relay)
    elif newState == "OFF" and currentState == "ON":
        RELAY.relayOFF(board, relay)
    sleep(0.15)
    return getRelayState(board, relay)

def worker(commands_queue):
    while True:
        message = commands_queue.get()
        payload = str(message.payload.decode("utf-8"))
        if message.topic == bridge.topics["housekeeping"]:
            if payload == "exit":
                print("exit command received")
                bridge.disconnect()
                commands_queue.task_done()
                break
            elif payload == "bridgestatus":
                print(bridge)
                print("\t{0} message(s) in queue".format(commands_queue.qsize()))
            elif payload == "boardsstatus":
                print("Boards status: ")
                for i, board in enumerate(activeBoards):
                    print("\tboard {0}: {1}".format(i, board))
            elif payload == "relaystatus":
                print("RELAYplate states:")
                for i, board in enumerate(activeBoards):
                    if board == BoardType.RELAY:
                        print("\tplate {0}: {1}".format(i, RELAY.relaySTATE(i)))
            else:
                logging.warning("unknown housekeeping command: {0}".format(payload))
        elif message.topic == bridge.topics["commands"]:
            match = re.match("rp(?P<board>[0-7])\:(?P<relay>[1-7])(?P<state> - (ON|OFF))?", payload)
            if match:
                board = int(match.group("board"))
                relay = int(match.group("relay"))
                state = match.group("state")
                if activeBoards[board] == BoardType.RELAY:
                    if state is None:
                        RELAY.relayTOGGLE(board, relay)
                    else:
                        state = state.replace(" - ", "")
                        newState = setRelayState(board, relay, state)
                        retries = 0
                        # In case the new state is not correctly set, do up to 10 retries
                        while newState != state and retries < 10:
                            newState = setRelayState(board, relay, state)
                            retries = retries + 1

                    # publish the new state via MQTT
                    bridge.publish(bridge.topics["status"], "rp{0}:{1} - {2}".format(board, relay, newState))
                    logging.debug("requested: {0} vs. new: {1} ({2}), done in {3} retries".format(state, newState, RELAY.relaySTATE(board), retries))
                else:
                    logging.warning("board " + str(board) + " isn't active")
            else:
                logging.warning("incorrect payload format: " + payload)

        commands_queue.task_done()
        sleep(0.05)

signal.signal(signal.SIGINT, signal_handling) 

activeBoards = getActiveBoards()
if activeBoards.count(BoardType.NONE) < 8:
    logging.info ("The following RELAYplates have been found: {0}".format(activeBoards))
else:
    logging.error("No RELAYplates found")
    sys.exit("No RELAYplates found")

__commands_queue = Queue(0)
__broker_address = None
__broker_port = None
__broker_topics = {}
__broker_clientName = ""
getConfig()

bridge = MqttBridge(__broker_address, __broker_port, __broker_topics, __commands_queue, __broker_clientName)
bridge.connect()

# to begin with, send the initial state of all relays via MQTT
for i, board in enumerate(activeBoards):
    if board == BoardType.RELAY:
        for j in range(1, 7):
            bridge.publish(bridge.topics["status"], "rp{0}:{1} - {2}".format(i, j, getRelayState(i, j)))

pollers = []
lock = threading.Lock()
for i, b in enumerate(activeBoards):
    if b == BoardType.DAQC:
        if __allowAnalogPoller == 1:
            apoller = analogPoller(i, bridge, lock)
            apoller.start()
            pollers.append(apoller)
        if __allowDigitalPoller == 1:
            dpoller = digitalPoller(i, bridge, [0], lock)
            dpoller.start()
            pollers.append(dpoller)

worker(__commands_queue)
__commands_queue.join()
