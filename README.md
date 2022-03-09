# rpBridge
Handles any connected piplates:

- polls analog and/or digital inputs from DAQCplates
- allows turning relays ON/OFF on the RELAYplates

Any commands to/from the python application are sent via MQTT. The MQTT connection configuration is done through the config.yaml file. An example:

``` yaml
mqtt:
  address: 127.0.0.1                # mqtt broker IP address
  port: 1883                        # mqtt broker port; default is 1883
  topics:
    - commands: rpcommands          # subscription to commands received from HA
    - housekeeping: rphousekeeping  # subscription for obtaining basic information from the app
    - status: rpstatus              # subscription for sending/receiving status of relays on RELAYplates
    - button: rpbutton              # subscription for sending states of buttons connected to DAQCplates
  clientName: "rpDAQC"              # UNIQUE name of mqtt client
piplates:
  analogPoller: 1                   # 0 - no polling of analog inputs, 1 - poll analog inputs
  digitalPoller: 0                  # 0 - no polling of digital inputs, 1 - poll digital inputs
```

Most important information is logged in rpBridge.log, located in the same place as the python files.

To run the app as a service in linux, create a new service file in /etc/systemd/system. Below is a sample:

``` INI
[Unit]
Description = rpBridge service for handling piplates
After = multi-user.target

[Service]
WorkingDirectory = <location of code>
User = pi
Type = simple
Restart = always
ExecStart = /usr/bin/python3 <full path to main.py>

[Install]
WantedBy = multi-user.target
```

Once that's done, symply start it via ```sudo systemctl start nameOfService.service```
