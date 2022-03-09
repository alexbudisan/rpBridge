from datetime import datetime
import logging
import piplates.DAQCplate as DAQC
import threading
import time

class analogPoller (threading.Thread):
    def __init__(self, __address, __bridge, __lock):
        threading.Thread.__init__(self)
        self.address = __address
        self.bridge = __bridge
        self.lock = __lock
        self.requestToStop = False
        print ("Analog poller created for board {0}".format(self.address))

    def run(self):
        states = [False, False, False, False, False, False, False, False]
        while self.requestToStop == False:
            voltages = [-1, -1, -1, -1, -1, -1, -1, -1]
            # try to get all voltages in one go, while locking access (getADC influences DINs)
            self.lock.acquire()
            for i in range(0, 8):
                voltages[i] = DAQC.getADC(self.address, i)
            self.lock.release()

            for i, v in enumerate(voltages):
                if v != 0:
                    if v < 0.2:
                        if states[i] == False:
                            states[i] = True
                            print ("[{0}]: AN{1} is pushed ({2})".format(datetime.now(), i, v))
                            self.bridge.publish(self.bridge.topics["button"], "daqc{0}:{1} - ON".format(self.address, i))
                    elif states[i] == True:
                        states[i] = False
                        print ("[{0}]: AN{1} is NOT pushed ({2})".format(datetime.now(), i, v))
                        self.bridge.publish(self.bridge.topics["button"], "daqc{0}:{1} - OFF".format(self.address, i))

            time.sleep(.05)

    def stop(self):
        print ("Analog poller STOPPED for board {0}".format(self.address))
        self.requestToStop = True

class digitalPoller (threading.Thread):
    def __init__(self, __address, __bridge, __mask, __lock):
        threading.Thread.__init__(self)
        self.address = __address
        self.bridge = __bridge
        self.mask = __mask
        self.lock = __lock
        self.requestToStop = False
        print ("Digital poller created for board {0}".format(self.address))

    def run(self):
        states = [False, False, False, False, False, False, False, False]
        while self.requestToStop == False:
            # try to get all DINs in one go
            self.lock.acquire()
            dinAll = DAQC.getDINall(self.address)
            self.lock.release()
            
            for i in self.mask:
                s = (dinAll >> i) & 0x01
                if s == 1 and states[i] == True:
                    states[i] = False
                    print ("[{0}]: DIN{1} is NOT pushed".format(datetime.now(), i))
                    self.bridge.publish(self.bridge.topics["button"], "daqc{0}:{1} - OFF".format(self.address, i + 8))
                elif s == 0 and states[i] == False:
                    states[i] = True
                    print ("[{0}]: DIN{1} is pushed".format(datetime.now(), i))
                    self.bridge.publish(self.bridge.topics["button"], "daqc{0}:{1} - ON".format(self.address, i + 8))
                
            time.sleep(.2)

    def stop(self):
        print ("Digital poller STOPPED for board {0}".format(self.address))
        self.requestToStop = True
