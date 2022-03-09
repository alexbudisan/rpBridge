import logging
import paho.mqtt.client as mqtt

class MqttBridge:
    def __init__(self, address="127.0.0.1", port=1883, \
            topics = { "commands": "rp/commands", "housekeeping": "rp/housekeeping", "status": "rp/status" }, \
            commands_queue=None,
            clientName = "rpBridge"):
        self.address = address
        self.port = port
        self.topics = topics
        self.__client = None
        self.client_name = clientName
        self.commands_queue = commands_queue
        self.__connected = False

    def connect(self):
        try:
            self.__client = mqtt.Client(self.client_name)  # create new instance
            self.__client.on_connect = lambda client, userdata, flags, rc: self.__on_connect(
                client, userdata, flags, rc)
            self.__client.on_message = lambda client, userdata, msg: self.__on_message(
                client, userdata, msg)
            self.__client.on_disconnect = lambda client, userdata, msg: self.__on_disconnect(
                client, userdata, msg)

            self.__client.connect(self.address, self.port)  # connect to broker
            self.__connected = True

            for topic in self.topics:
                self.__client.subscribe(self.topics[topic])
                logging.info("subscribed to {0}".format(self.topics[topic]))

            self.__client.loop_start()
        except ConnectionRefusedError:
            logging.error("Connection refused")
        except Exception as ex:
            logging.error("Exception while mqtt-ing: {0}".format(ex))
    
    def publish(self, topic, payload):
        self.__client.publish(topic, payload)

    def __str__(self):
        return "MqttBridge {0}: {1}:{2} (topics: {3})\r\n\tconnected: {4}".format(self.client_name, self.address, self.port, self.topics, self.__connected)

    def disconnect(self):
        try:
            logging.info("requested to disconnect")
            self.__client.disconnect()
            self.__connected = False
        except Exception as ex:
            logging.error("Exception disconnecting from mqtt: {0}".format(ex))

    def __on_connect(self, client, userdata, flagc, rc):
        if rc == 0:
            client.connected_flag = True
            logging.info("connected ok")
        else:
            logging.error("Bad connection returned code: " + str(rc))
            client.bad_connection_flag = True

    def __on_message(self, client, userdata, message):
        for topic in self.topics:
            if message.topic == self.topics[topic]:
                if self.commands_queue != None:
                    self.commands_queue.put(message)
                else:
                    logging.warning("commands queue is not defined. Messages will be lost")
                break
        else:
            logging.warning("unknown topic (message will be ignored): " + message.topic)

    def __on_disconnect(self, client, userdata, rc=0):
        logging.info("disconnect receive code: " + str(rc))
        client.loop_stop()
