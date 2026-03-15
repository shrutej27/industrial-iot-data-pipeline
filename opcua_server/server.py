"""OPC-UA server exposing machine status & energy, with a client that writes to InfluxDB."""

import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from enum import IntEnum

from asyncua import Server, ua
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("opcua-server")

# ── Configuration ────────────────────────────────────────────────────────────
OPCUA_PORT = int(os.getenv("OPCUA_PORT", "4840"))
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.environ["INFLUXDB_TOKEN"]
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "factory")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "iot")
POLL_INTERVAL = int(os.getenv("OPCUA_POLL_INTERVAL", "5"))

NAMESPACE = "urn:factory:opcua:server"
MACHINES = ["machine-1", "machine-2", "machine-3", "machine-4", "machine-5"]


class MachineStatus(IntEnum):
    RUNNING = 0
    IDLE = 1
    FAULT = 2


# ── OPC-UA Server Setup ─────────────────────────────────────────────────────
async def create_opcua_server() -> tuple[Server, dict]:
    """Initialise OPC-UA server with machine status and energy variables."""
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{OPCUA_PORT}/freeopcua/server/")
    server.set_server_name("Factory OPC-UA Server")

    idx = await server.register_namespace(NAMESPACE)

    # Build an object node per machine with two variables
    nodes: dict[str, dict[str, ua.NodeId]] = {}
    objects = server.nodes.objects
    for mid in MACHINES:
        machine_obj = await objects.add_object(idx, mid)
        status_var = await machine_obj.add_variable(
            idx, "Status", int(MachineStatus.RUNNING)
        )
        energy_var = await machine_obj.add_variable(idx, "EnergyKWh", 0.0)
        await status_var.set_writable()
        await energy_var.set_writable()
        nodes[mid] = {"status": status_var, "energy": energy_var}

    return server, nodes


# ── Simulation Loop (updates OPC-UA variables) ──────────────────────────────
async def simulate_opcua_values(nodes: dict) -> None:
    """Periodically update OPC-UA variable values with simulated data."""
    while True:
        for mid, vars_ in nodes.items():
            # 85 % running, 10 % idle, 5 % fault
            r = random.random()
            status = (
                MachineStatus.RUNNING
                if r < 0.85
                else (MachineStatus.IDLE if r < 0.95 else MachineStatus.FAULT)
            )
            energy = (
                round(random.uniform(5.0, 50.0), 2)
                if status == MachineStatus.RUNNING
                else 0.0
            )

            await vars_["status"].write_value(int(status))
            await vars_["energy"].write_value(energy)
        await asyncio.sleep(POLL_INTERVAL)


# ── Client Poller (reads OPC-UA → writes InfluxDB) ──────────────────────────
async def poll_and_write(nodes: dict) -> None:
    """Read current OPC-UA values and write points to InfluxDB."""
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    while True:
        await asyncio.sleep(POLL_INTERVAL)
        now = datetime.now(timezone.utc)
        points: list[Point] = []
        for mid, vars_ in nodes.items():
            status_val = await vars_["status"].read_value()
            energy_val = await vars_["energy"].read_value()

            points.append(
                Point("opcua_status")
                .tag("machine_id", mid)
                .field("status", int(status_val))
                .time(now, WritePrecision.S)
            )
            points.append(
                Point("opcua_energy")
                .tag("machine_id", mid)
                .field("energy_kwh", float(energy_val))
                .time(now, WritePrecision.S)
            )

        try:
            write_api.write(bucket=INFLUXDB_BUCKET, record=points)
            logger.info("Wrote %d OPC-UA points to InfluxDB", len(points))
        except Exception:
            logger.exception("Failed to write OPC-UA points to InfluxDB")


# ── Main ─────────────────────────────────────────────────────────────────────
async def main() -> None:
    server, nodes = await create_opcua_server()

    async with server:
        logger.info("OPC-UA server running on opc.tcp://0.0.0.0:%d", OPCUA_PORT)
        await asyncio.gather(
            simulate_opcua_values(nodes),
            poll_and_write(nodes),
        )


if __name__ == "__main__":
    asyncio.run(main())
