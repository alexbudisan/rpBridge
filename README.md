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

Most important information is logged in rpBridge.log, located in the same place as the app files.

## MQTT messages

Below is a list of all MQTT messages that flow through the app:

- `housekeeping` messages (world → app):
  - `exit`: disconnect the mqtt client and close the app/service
  - `bridgestatus`: returns information on the mqtt client, as well as number of mqtt messages in queue
  - `boardsstatus`: returns boards handled by the app
  - `relaystatus`: returns status of relays on all handled RELAYplates
- `commands` messages:
  - set relay status (HA → app): `rp<plate>:<relay> - (ON|OFF)`, where (RELAY)plate is between 0 and 7, relay is between 1 and 7
- `status` messages:
  - get relay status (app → HA): `rp<plate>:<relay> - (ON|OFF)`, where (RELAY)plate is between 0 and 7, relay is between 1 and 7
- `button` messages:
  - button state (app → HA): `daqc<plate>:<input> - (ON|OFF)`, where (DAQC)plate is between 0 and 7, input is between 0 and 7 for analog inputs, 8 and 15 for digital inputs

## Auto-running the app

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

## Home Assistant configuration

To configure a button (i.e. a DAQCplate input) in HA, add the following section in configuration.yaml:

``` yaml
binary_sensor:                    # duplicate this as many times as needed, for each button
  - platform: mqtt
    unique_id: daqc1_0            # set a unique name
    name: "DAQC1:0"               # user-friendly name, shown in the HA UI
    state_topic: "rpbutton"
    payload_on:  "daqc1:0 - ON"   # make sure the first part of the payload is consistent with the sensor name
    payload_off: "daqc1:0 - OFF"
    qos: 0
```

To configure a light (i.e. a RELAYplate relay) in HA, add the following section in configuration.yaml:

``` yaml
light:

  - platform: mqtt                # duplicate this as many times as needed, for each light
    unique_id: relayplates4-1
    name: "RELAYplates 4:1"       # user-friendly name, shown in the HA UI
    state_topic: "rpstatus"
    command_topic: "rpcommands"
    payload_on: "rp4:1 - ON"      # make sure the first part of the payload is consistent with the sensor name
    payload_off: "rp4:1 - OFF"
    optimistic: false
    qos: 0
    retain: false
```

Linking a button to a light is done via an automation script (HA → Configuration → Automation & Scenes → Automations):

``` yaml
id: 'unique ID'
alias: user-friendly name
description: ''
trigger:
  - platform: state
    entity_id: binary_sensor.daqc1_0    # button that triggers the light(s) toggle
    from: 'off'
    to: 'on'
condition: []
action:
  - service: light.toggle
    target:
      entity_id: light.relayplates_5_1  # light entity that gets toggled (multiple entities can be added)
mode: single
```
