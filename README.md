# Tic2MQTT by Vaarlion
My take on a TIC 2 MQTT python service that read and expose Teleinfo from the french powergrid provider to MQTT.

Not inspired by but named the same as https://github.com/JcDenis/tic2mqtt

## Requirements
The requirement file should have everything.
This is based on a fork of `pyticcom`, `asyncio`, `asyncio-mqtt`, `homeassistant-mqtt-binding`, and `paho-mqtt` because `homeassistant-mqtt-binding` don't work in async.

## Warning
I'm not a dev so this is a cobbled-together python script. It was quite clean before i tried to add home assistant mqtt discovery ... but for my need it will be good enough.

## TODO
 - [X] feature: Add systemd service file
 - [X] feature: Add makefile to install it cleanly
 - [ ] bugfix: Find out why automatic cleanup on close don't work
 - [ ] feature: Bring ADPS to 0 when not present
 - [ ] feature: Add a way to manage udev rule for the serial device
