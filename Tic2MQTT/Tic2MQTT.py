#! /usr/bin/env python3

import asyncio
import os
import logging
import json
import ssl
import hashlib

from async_pytictri import Teleinfo, Mode

import configparser
import argparse
import asyncio_mqtt as aiomqtt

from ha_mqtt.mqtt_device_base import MqttDeviceSettings
from ha_mqtt.ha_device import HaDevice
from ha_mqtt.mqtt_sensor import MqttSensor
from ha_mqtt.util import HaDeviceClass


def read_config(config_file: str):
    """
    This function reads a configuration file and adds any missing sections or options with default values
    :param config_file: file path to the config file
    """
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
    except configparser.Error as e:
        print(f"Error reading config file: {e}")

    if not config.has_section("Device"):
        config.add_section("Device")
    if not config.has_option("Device", "Path"):
        config.set("Device", "Path", "<Path to device>")
    if not config.has_option("Device", "Name"):
        config.set("Device", "Name", "Default")

    if not config.has_section("Global"):
        config.add_section("Global")
    if not config.has_option("Global", "Base_topic"):
        config.set("Global", "Base_topic", "ha_tic_mqtt")

    if not config.has_section("MQTT"):
        config.add_section("MQTT")
    if not config.has_option("MQTT", "Server"):
        config.set("MQTT", "Server", "<Ip or fqdn of the remote MQTT server>")
    if not config.has_option("MQTT", "Port"):
        config.set("MQTT", "Port", "1883")
    if not config.has_option("MQTT", "Username"):
        config.set("MQTT", "Username", "None")
    if not config.has_option("MQTT", "Password"):
        config.set("MQTT", "Password", "None")
    if not config.has_option("MQTT", "Topic"):
        config.set("MQTT", "Topic", "ha_tic_mqtt")
    if not config.has_option("MQTT", "Client_id"):
        config.set("MQTT", "Client_id", "HA_TIC_MQTT")
    if not config.has_option("MQTT", "Enable_TLS"):
        config.set("MQTT", "Enable_TLS", "False")

    with open(config_file, "w") as configfile:
        config.write(configfile)

    os.chmod(config_file, 0o600)

    return config


def string_var_convertor(value: str):
    """
    Convert a string to None, True, False, or int if possible; otherwise return the input string.

    :param value: A string to convert.
    :return: The converted value, or the input string if no conversion was possible.

    Examples:
    >>> string_var_convertor('None')
    None
    >>> string_var_convertor('true')
    True
    >>> string_var_convertor('10')
    10
    >>> string_var_convertor('hello')
    'hello'
    """

    # Convert input string to lowercase for case-insensitive comparisons
    value = value.lower()

    # Check if the input string matches any of the supported conversion types
    if value == "none":
        return None
    elif value == "true":
        return True
    elif value == "false":
        return False
    elif value.isdigit():
        return int(value)
    else:
        # If no conversion was possible, return the original input string
        return value

    # match value:
    #     case "none":
    #         return None
    #     case 'true':
    #         return True
    #     case 'false':
    #         return False
    #     case _:
    #         return value


class Teleinfo_module:
    def __init__(
        self,
        device: str,
        name: str,
        mqtt_client: object,
        base_topic: str,
        discovery: bool = False,
    ) -> None:
        """
        Push Teleinfo data from a usb device to mqtt
        :param device: The path to the usb device
        :param name: Unique name of the device
        :param mqtt_client: the mqtt client used to send back the data and publish the discovery
        :param base_topic: the racine to publish on. `name` will be added to it
        :param discovery: Enable Home Assistant MQTT discovery if set to True
        """
        self.device = device
        self.name = name
        self.mqtt_client = mqtt_client
        self.topic = f"{base_topic}/{name}"
        self.discovery = discovery
        self.last_data = {}
        self.running = True
        self.logger = logging.getLogger(__name__ + "Teleinfo")
        self.logger.level = logger_level
        self.discovery_device = HaDevice(
            self.name, hashlib.sha256((self.topic).encode("utf-8")).hexdigest()
        )
        self.discovery_sensors = {}

    async def listener(self) -> None:
        """
        Listen for Teleinfo data and publish it to MQTT.
        """
        with Teleinfo(self.device, mode=Mode.HISTORY) as teleinfo:
            while self.running:
                frame = await teleinfo.read_frame()
                self.logger.debug("Got data : {}".format(frame))
                for group in frame.groups:
                    self.last_data[group.info.name] = {
                        "value": group.value,
                        "description": group.info.description,
                        "unit": group.info.unit,
                    }
                await self.mqtt_client.publish(self.topic, json.dumps(self.last_data))
                self.__config_homeassistant_discovery__()
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """
        Stop the Teleinfo listener.
        """
        self.logger.info("Stopping {} Teleinfo device".format(self.name))
        self.running = False
        self.__clean_homeassistant_discovery__()

    async def start(self) -> None:
        """
        Start the Teleinfo listener.
        """
        self.logger.info("Starting {} Teleinfo device".format(self.name))
        self.running = True
        await self.listener()

    def __config_homeassistant_discovery__(self):
        """
        Configure Home Assistant MQTT discovery for each Teleinfo group.
        """

        devices_data_matching = {
            "ADCO": {
                "class": HaDeviceClass(None),
                "value_template": "{{ value_json.ADCO.value }}",
            },
            "OPTARIF": {
                "class": HaDeviceClass(None),
                "value_template": "{{ value_json.OPTARIF.value }}",
            },
            "ISOUSC": {
                "class": HaDeviceClass("current"),
                "value_template": "{{ value_json.ISOUSC.value }}",
            },
            "BASE": {
                "class": HaDeviceClass("energy"),
                "value_template": "{{ value_json.BASE.value }}",
            },
            "PTEC": {
                "class": HaDeviceClass(None),
                "value_template": "{{ value_json.PTEC.value }}",
            },
            "IINST": {
                "class": HaDeviceClass("current"),
                "value_template": "{{ value_json.IINST.value }}",
            },
            "IMAX": {
                "class": HaDeviceClass("current"),
                "value_template": "{{ value_json.IMAX.value }}",
            },
            "PAPP": {
                "class": HaDeviceClass("apparent_power"),
                "value_template": "{{ value_json.PAPP.value }}",
            },
            "ADPS": {
                "class": HaDeviceClass("current"),
                "value_template": "{{ value_json.ADPS.value }}",
            },
        }

        from paho.mqtt.client import Client as old_mqtt

        self.discovery_mqtt_client = old_mqtt(client_id=self.mqtt_client.client_id)
        self.discovery_mqtt_client.username_pw_set(
            self.mqtt_client.username, self.mqtt_client.password
        )
        self.discovery_mqtt_client.enable_logger(self.logger)
        self.discovery_mqtt_client.tls_set(
            ca_certs=None,
            certfile=None,
            keyfile=None,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS,
            ciphers=None,
        )

        for key, value in self.last_data.items():
            if key not in self.discovery_sensors:
                self.discovery_mqtt_client.connect(
                    host=self.mqtt_client.server,
                    port=self.mqtt_client.port,
                    keepalive=60,
                )
                self.discovery_mqtt_client.loop_start()
                self.logger.info(
                    "Creating {} discovery sensor for {} device".format(key, self.name)
                )
                self.discovery_sensors[key] = MqttSensorTic(
                    MqttDeviceSettings(
                        name="{}: {}".format(
                            self.name, self.last_data[key].get("description")
                        ),
                        unique_id="{}_{}".format(
                            hashlib.sha256((self.topic).encode("utf-8")).hexdigest(),
                            key,
                        ),
                        client=self.discovery_mqtt_client,
                        device=self.discovery_device,
                    ),
                    unit=value["unit"],
                    device_class=devices_data_matching[key]["class"],
                    state_topic=self.topic,
                    state_template=devices_data_matching[key]["value_template"],
                    send_only=True,
                )
                self.discovery_mqtt_client.loop_stop()
                self.discovery_mqtt_client.disconnect()

    def __clean_homeassistant_discovery__(self):
        """
        Clean Home Assistant MQTT discovery topic.
        """
        self.discovery_mqtt_client.connect(
            host=self.mqtt_client.server,
            port=self.mqtt_client.port,
            keepalive=60,
        )
        self.discovery_mqtt_client.loop_start()
        for key, value in self.discovery_sensors.items():
            self.logger.info(
                "Removing {} discovery sensor for {} device".format(key, self.name)
            )
            value.close()
        self.discovery_mqtt_client.loop_stop()
        self.discovery_mqtt_client.disconnect()


class Mqtt_server:
    def __init__(
        self,
        server: str,
        port: int,
        username=None,
        password=None,
        client_id=None,
        tls: bool = False,
    ) -> None:
        """
        Aiomqtt based MQTT Warper
        :param server: IP or Hostname of the remote mqtt server
        :param port: Port of the remote mqtt server
        :param username: Username used to log in to the remove mqtt server
        :param password: Password used to log in to the remove mqtt server
        :param client_id: Client id used to log in to the remote mqtt server
        :param tls: Enable basic TLS if self to True
        """
        self.server = server
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.running = True
        self.logger = logging.getLogger(__name__ + "mqtt")
        self.logger.level = logger_level
        self.tls_params = self.setup_tls(tls)

    def setup_tls(self, enabled: bool):
        if enabled:
            tls_params = aiomqtt.TLSParameters(
                ca_certs=None,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS,
                ciphers=None,
            )
        else:
            tls_params = None
        return tls_params

    async def setup_client(self) -> None:
        reconnect_interval = 5
        while self.running:
            try:
                self.client = aiomqtt.Client(
                    hostname=self.server,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    client_id=self.client_id,
                    tls_params=self.tls_params,
                    keepalive=60,
                )
                self.logger.info("Connecting to {} MQTT server".format(self.server))
                await self.client.__aenter__()
                await self.client._connected  # Wait for the client to connect
                self.logger.info("Connected to {} MQTT server".format(self.server))

                # Wait for the client to disconnect before reconnecting
                await self.client._disconnected
                self.logger.warning(
                    "Disconnected from {} MQTT server".format(self.server)
                )
                await self.client.__aexit__(None, None, None)

            except aiomqtt.MqttError as error:
                self.logger.error(
                    f'MQTT error "{error}". Reconnecting in {reconnect_interval} seconds.'
                )
                await asyncio.sleep(reconnect_interval)

    async def stop(self) -> None:
        self.logger.info("Stopping MQTT")
        self.running = False
        await self.client.__aexit__(None, None, None)

    async def publish(
        self,
        topic: str,
        payload=None,
        qos: int = 0,
        retain: bool = False,
        properties=None,
        *args,
        timeout: int = 10,
        **kwargs,
    ) -> None:
        retry_interval = 5
        data_sent = False
        max_retry = 5
        while not data_sent and max_retry > 0:
            try:
                await self.client.publish(
                    topic=topic,
                    payload=payload,
                    qos=qos,
                    retain=retain,
                    properties=properties,
                    timeout=timeout,
                    *args,
                    **kwargs,
                )
                data_sent = True
            except aiomqtt.MqttError as error:
                max_retry -= 1
                self.logger.error(
                    f'MQTT error "{error}". Rerying {max_retry} still in {retry_interval} seconds.'
                )
                await asyncio.sleep(retry_interval)

    async def get_client(self):
        return self


class MqttSensorTic(MqttSensor):
    def __init__(
        self,
        settings: MqttDeviceSettings,
        unit: str,
        device_class: HaDeviceClass,
        state_topic=None,
        state_template=None,
        send_only=False,
    ):
        """
        create TIC sensor instance
        """
        self.state_template = state_template
        self.custom_state_topic = state_topic
        super().__init__(settings, unit, device_class, send_only)

    def pre_discovery(self):
        super().pre_discovery()
        if self.custom_state_topic:
            self.state_topic = f"{self.custom_state_topic}"
            self.add_config_option("state_topic", f"{self.state_topic}")
        if self.state_template:
            self.add_config_option("value_template", f"{self.state_template}")


async def main():
    tasks = []

    parser = argparse.ArgumentParser(description="Process configuration file.")
    parser.add_argument(
        "-c",
        "--config_file",
        metavar="config_file",
        type=str,
        help="path to configuration file",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase logging verbosity"
    )
    args = parser.parse_args()

    global logger_level
    logger_level = logging.WARNING

    if args.verbose == 1:
        logger_level = logging.INFO
    elif args.verbose >= 2:
        logger_level = logging.DEBUG

    if args.config_file:
        config = read_config(args.config_file)
    else:
        raise argparse.ArgumentError(
            None,
            "Please specify a configuration file using the -c or --config_file flag.",
        )

    logger = logging.getLogger(__name__ + "main")
    logger.level = logger_level

    logger.debug("Config was read successfully")
    mqtt_server = Mqtt_server(
        server=string_var_convertor(config.get("MQTT", "Server")),
        port=string_var_convertor(config.get("MQTT", "Port")),
        username=string_var_convertor(
            config.get("MQTT", "Username"),
        ),
        password=string_var_convertor(
            config.get("MQTT", "Password"),
        ),
        client_id=string_var_convertor(config.get("MQTT", "Client_id")),
        tls=string_var_convertor(
            config.get("MQTT", "Enable_TLS"),
        ),
    )
    try:
        tasks.append(asyncio.create_task(mqtt_server.setup_client()))

        tic = Teleinfo_module(
            device=config.get("Device", "Path"),
            name=config.get("Device", "Name"),
            mqtt_client=await mqtt_server.get_client(),
            base_topic=config.get("Global", "Base_topic"),
        )

        tasks.append(asyncio.create_task(tic.start()))

        await asyncio.gather(*tasks)
    except Exception as error:
        logger.error(f'General error "{error}". Closing process')
    finally:
        await tic.stop()
        await mqtt_server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
