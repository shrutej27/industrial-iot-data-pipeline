"""
Industrial IoT Sensor Simulator

Publishes simulated factory sensor data to MQTT topics every 1-2 seconds.
Simulates 5 machines with temperature, RPM, and pressure metrics.
Injects ~5% anomalous readings for demo purposes.
"""

import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from dataclasses import dataclass

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
ANOMALY_RATE = float(os.getenv("ANOMALY_RATE", "0.05"))


@dataclass
class MetricConfig:
    """Configuration for a single sensor metric."""

    name: str
    unit: str
    normal_min: float
    normal_max: float
    anomaly_min: float
    anomaly_max: float


@dataclass
class MachineConfig:
    """Configuration for a simulated machine."""

    machine_id: str
    name: str
    metrics: list[MetricConfig]


METRIC_TEMPLATES = [
    MetricConfig(
        name="temperature",
        unit="°C",
        normal_min=70.0,
        normal_max=90.0,
        anomaly_min=95.0,
        anomaly_max=120.0,
    ),
    MetricConfig(
        name="rpm",
        unit="RPM",
        normal_min=1200.0,
        normal_max=1800.0,
        anomaly_min=500.0,
        anomaly_max=2500.0,
    ),
    MetricConfig(
        name="pressure",
        unit="bar",
        normal_min=2.0,
        normal_max=4.5,
        anomaly_min=5.0,
        anomaly_max=7.0,
    ),
]

MACHINES = [
    MachineConfig(
        machine_id=f"machine-{i}", name=f"CNC Machine {i}", metrics=METRIC_TEMPLATES
    )
    for i in range(1, 6)
]


class SensorSimulator:
    """Publishes simulated sensor readings to MQTT."""

    def __init__(self, broker: str, port: int, machines: list[MachineConfig]) -> None:
        self.broker = broker
        self.port = port
        self.machines = machines
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        rc: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        if rc.value == 0:
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
        else:
            logger.error(f"Connection failed with reason code: {rc}")

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.DisconnectFlags,
        rc: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        logger.warning(f"Disconnected from MQTT broker (rc={rc}). Reconnecting...")

    def _generate_reading(self, machine: MachineConfig, metric: MetricConfig) -> dict:
        """Generate a single sensor reading, with chance of anomaly."""
        is_anomaly = random.random() < ANOMALY_RATE

        if is_anomaly:
            value = round(random.uniform(metric.anomaly_min, metric.anomaly_max), 2)
        else:
            value = round(random.uniform(metric.normal_min, metric.normal_max), 2)

        return {
            "machine_id": machine.machine_id,
            "metric": metric.name,
            "value": value,
            "unit": metric.unit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _publish_reading(self, reading: dict) -> None:
        """Publish a reading to the appropriate MQTT topic."""
        topic = f"factory/{reading['machine_id']}/{reading['metric']}"
        payload = json.dumps(reading)
        result = self.client.publish(topic, payload, qos=1)
        result.wait_for_publish()
        logger.debug(f"Published to {topic}: {payload}")

    def run(self) -> None:
        """Connect to MQTT and start publishing sensor data in a loop."""
        logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()

        logger.info(
            f"Simulating {len(self.machines)} machines with {len(METRIC_TEMPLATES)} metrics each"
        )
        logger.info(f"Anomaly injection rate: {ANOMALY_RATE:.0%}")

        try:
            while True:
                for machine in self.machines:
                    for metric in machine.metrics:
                        reading = self._generate_reading(machine, metric)
                        self._publish_reading(reading)

                interval = random.uniform(1.0, 2.0)
                logger.info(
                    f"Published readings for {len(self.machines)} machines. Next in {interval:.1f}s"
                )
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Shutting down simulator...")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


def main() -> None:
    simulator = SensorSimulator(
        broker=MQTT_BROKER,
        port=MQTT_PORT,
        machines=MACHINES,
    )
    simulator.run()


if __name__ == "__main__":
    main()
