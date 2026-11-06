"""
Vertebrate PLC simulator.

Stands in for the CODESYS demo PLC (project "ISPERome") so the demo runs
without the Windows server. It serves the same OPC UA node IDs the bridges
(PLC2Nexus.py / Nexus2PLC.py) already use and re-implements the CFC logic
from the PLCopenXML export, cycle by cycle (100 ms task, like the PLC):

  Main          BLINK + Randomizer blocks generate slow sine signals
                while Scene1 or Scene2 is TRUE. StopPhase1 := NOT StartPhase1
  CM001_MTemp   Scene1: 5.0 + Scene1_Sin2   Scene2: 8.0 + Scene2_Sin
  CM002_Speed   Scene1: 350 + Scene1_Sin    Scene2: 300 + Scene2_Sin
  CM003_Press.  Scene1: 1.5 + Scene1_Sin    Scene2: 0.0 + Scene2_Sin
  CM004_AmbTemp Scene1: 15  + Scene1_Sin    Scene2: 20  + Scene2_Sin
  (an Add block with EN=FALSE keeps its last output, as in CODESYS)

A read-only status page is served on http://localhost:8081 for the video.
"""
import asyncio
import json
import logging
import math
import os
from datetime import datetime, timezone

from asyncua import Server, ua

CYCLE_S = float(os.environ.get("PLC_CYCLE_S", "0.1"))   # Task interval PT0.1S
OPC_PORT = int(os.environ.get("OPC_PORT", "4840"))
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8081"))
# Demo only: shifts CM003_Pressure so it stays plausible on camera (the CODESYS logic goes below 0 bar)
PRESSURE_OFFSET = float(os.environ.get("PRESSURE_OFFSET", "0"))
PREFIX = "|var|CODESYS Control Win V3 x64.Application."
NS = 4  # the bridges address ns=4

logging.basicConfig(level=logging.INFO, format="%(asctime)s PLC-SIM %(message)s")
log = logging.getLogger("plcsim")
logging.getLogger("asyncua").setLevel(logging.WARNING)


# ---------------------------------------------------------------- function blocks
class Blink:
    """CODESYS Util.BLINK: OUT toggles HIGH for TIMEHIGH, LOW for TIMELOW while ENABLE."""
    def __init__(self, time_low, time_high):
        self.low, self.high = time_low, time_high
        self.out, self.t = False, 0.0

    def __call__(self, enable, dt):
        if not enable:
            self.out, self.t = False, 0.0
            return
        self.t += dt
        if self.out and self.t >= self.high - 1e-9:
            self.out, self.t = False, 0.0
        elif not self.out and self.t >= self.low - 1e-9:
            self.out, self.t = True, 0.0


class Randomizer:
    """FB 'Randomizer' from the project (LCG + sine), only runs when EN is TRUE."""
    def __init__(self):
        self.seed, self.a, self.c, self.m = 5, 525, 904223, 214748364
        self.frequency, self.phase, self.times = 1.0, 0.1, 0.0
        self.random_number, self.sine_value = 0, 0.0

    def __call__(self, en, lower, upper):
        if not en:
            return
        self.seed = (self.a * self.seed + self.c) % self.m
        rng = upper - lower + 1
        self.random_number = lower + self.seed % rng
        self.times += 0.01
        amplitude = upper - lower + 1
        self.sine_value = amplitude * math.sin(2 * 3.142 * self.frequency * self.times + self.phase)


class PlcLogic:
    def __init__(self):
        # inputs written by Vertebrate (Nexus2PLC)
        self.Scene1 = self.Scene2 = self.StartPhase1 = False
        self.StopPhase1 = True
        # Main internals
        self.blink_s1 = Blink(3.0, 0.2)
        self.blink_s2 = Blink(3.0, 0.2)
        self.blink2_s1 = Blink(3.0, 1.0)
        self.rand_s1, self.rand_s2, self.sinrand_s1 = Randomizer(), Randomizer(), Randomizer()
        self.Scene1_Sin = self.Scene1_Sin2 = self.Scene2_Sin = 0.0
        # CM outputs + held Add outputs (index 0 = Scene1 branch, 1 = Scene2 branch)
        self.add = {k: [0.0, 0.0] for k in ("MTemp", "Speed", "Pressure", "AmbTemp")}
        self.CM001_MTemp = self.CM002_Speed = self.CM003_Pressure = self.CM004_AmbTemp = 0.0

    def cycle(self, dt):
        # --- Main, in the CFC execution order
        self.Scene1_Sin2 = self.sinrand_s1.sine_value                       # [1]
        self.rand_s1(self.blink_s1.out, 0, 3)                                # [3]
        self.sinrand_s1(self.blink2_s1.out, 0, 1)                            # [4]
        self.blink_s1(self.Scene1, dt)                                       # [5]
        self.Scene1_Sin = self.rand_s1.sine_value                            # [6]
        self.rand_s2(self.blink_s2.out, 3, 10)                               # [7]
        self.Scene2_Sin = self.rand_s2.sine_value                            # [8]
        self.blink_s2(self.Scene2, dt)                                       # [9]
        self.blink2_s1(self.Scene1, dt)                                      # [12]
        self.StopPhase1 = not self.StartPhase1                               # [11],[13]

        # --- CM programs: ADD(EN=Scene) per branch, SEL(G=NOT Scene1, IN0=Scene1 branch, IN1=Scene2 branch)
        def cm(key, base1, sin1, base2, sin2):
            if self.Scene2:
                self.add[key][1] = base2 + sin2
            if self.Scene1:
                self.add[key][0] = base1 + sin1
            return self.add[key][0] if self.Scene1 else self.add[key][1]

        self.CM001_MTemp = cm("MTemp", 5.0, self.Scene1_Sin2, 8.0, self.Scene2_Sin)
        self.CM002_Speed = cm("Speed", 350.0, self.Scene1_Sin, 300.0, self.Scene2_Sin)
        self.CM003_Pressure = cm("Pressure", 1.5, self.Scene1_Sin, 0.0, self.Scene2_Sin) + PRESSURE_OFFSET
        self.CM004_AmbTemp = cm("AmbTemp", 15.0, self.Scene1_Sin, 20.0, self.Scene2_Sin)


# tag name in OPC UA -> (attribute on PlcLogic, type, writable)
TAGS = {
    "Main.Scene1": ("Scene1", ua.VariantType.Boolean, True),
    "Main.Scene2": ("Scene2", ua.VariantType.Boolean, True),
    "Main.StartPhase1": ("StartPhase1", ua.VariantType.Boolean, True),
    "Main.StopPhase1": ("StopPhase1", ua.VariantType.Boolean, False),
    "CM001_Mat_Temp.CM001_MTemp": ("CM001_MTemp", ua.VariantType.Float, False),
    "CM002_Speed.CM002_Speed": ("CM002_Speed", ua.VariantType.Float, False),
    "CM003_Pressure.CM003_Pressure": ("CM003_Pressure", ua.VariantType.Float, False),
    "CM004_Amb_Temp.CM004_AmbTemp": ("CM004_AmbTemp", ua.VariantType.Float, False),
}


# ---------------------------------------------------------------- status page
PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Data Vertebrate · PLC Simulator</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%2302000e'/%3E%3Crect x='6' y='5' width='20' height='6' rx='3' fill='%23ffffff'/%3E%3Crect x='8' y='13' width='16' height='6' rx='3' fill='%23ffffff'/%3E%3Crect x='10' y='21' width='12' height='6' rx='3' fill='%23ffffff'/%3E%3C/svg%3E">
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:32px}
h1{font-size:20px;margin:0 0 4px}p{color:#94a3b8;margin:0 0 24px}
table{border-collapse:collapse;min-width:520px}td,th{padding:10px 16px;border-bottom:1px solid #334155;text-align:left}
th{color:#94a3b8;font-weight:500}.on{color:#22c55e;font-weight:600}.off{color:#64748b}.num{font-variant-numeric:tabular-nums}</style>
</head><body><h1>CODESYS PLC (simulated) &middot; ISPE Filling Machine 1</h1>
<p>OPC UA opc.tcp://plc-sim:4840 &middot; task cycle 100 ms &middot; <span id="ts"></span></p>
<table><thead><tr><th>Tag</th><th>Value</th></tr></thead><tbody id="b"></tbody></table>
<script>
async function tick(){try{const r=await fetch('/api/tags');const d=await r.json();
document.getElementById('ts').textContent=d.timestamp;
document.getElementById('b').innerHTML=Object.entries(d.tags).map(([k,v])=>
`<tr><td>${k}</td><td class="${typeof v==='boolean'?(v?'on':'off'):'num'}">${typeof v==='boolean'?(v?'TRUE':'FALSE'):v.toFixed(2)}</td></tr>`).join('');}catch(e){}}
setInterval(tick,500);tick();</script></body></html>"""


async def http_server(logic):
    async def handle(reader, writer):
        try:
            line = (await reader.readline()).decode(errors="ignore")
            while (await reader.readline()) not in (b"\r\n", b"\n", b""):
                pass
            path = line.split(" ")[1] if " " in line else "/"
            if path.startswith("/api/tags"):
                body = json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "tags": {name: getattr(logic, attr) for name, (attr, _, _) in TAGS.items()},
                }).encode()
                ctype = "application/json"
            else:
                body, ctype = PAGE.encode(), "text/html; charset=utf-8"
            writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
            await writer.drain()
        finally:
            writer.close()
    srv = await asyncio.start_server(handle, "0.0.0.0", HTTP_PORT)
    log.info("status page on http://0.0.0.0:%s", HTTP_PORT)
    async with srv:
        await srv.serve_forever()


# ---------------------------------------------------------------- OPC UA server
async def main():
    logic = PlcLogic()
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{OPC_PORT}")
    server.set_server_name("Vertebrate PLC Simulator (CODESYS ISPERome)")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    # pad the namespace array so the CODESYS namespace lands on index 4
    for uri in ("urn:plcsim:ns2", "urn:plcsim:ns3", "http://www.3s-software.com/plcopenxml/codesys"):
        idx = await server.register_namespace(uri)
    assert idx == NS, f"namespace index is {idx}, expected {NS}"

    folder = await server.nodes.objects.add_folder(ua.NodeId("Application", NS), "Application")
    nodes = {}
    for name, (attr, vtype, writable) in TAGS.items():
        node = await folder.add_variable(ua.NodeId(PREFIX + name, NS), name, getattr(logic, attr), vtype)
        if writable:
            await node.set_writable()
        nodes[name] = node

    asyncio.create_task(http_server(logic))
    async with server:
        log.info("OPC UA server on opc.tcp://0.0.0.0:%s (ns=%s)", OPC_PORT, NS)
        last = {}
        while True:
            # read inputs written by clients
            for name, (attr, _, writable) in TAGS.items():
                if writable:
                    v = bool(await nodes[name].read_value())
                    if v != getattr(logic, attr):
                        log.info("input %s -> %s", name, v)
                    setattr(logic, attr, v)
            logic.cycle(CYCLE_S)
            # publish outputs with a fresh source timestamp
            now = datetime.now(timezone.utc)
            for name, (attr, vtype, writable) in TAGS.items():
                if writable:
                    continue
                val = getattr(logic, attr)
                if last.get(name) != val:
                    dv = ua.DataValue(ua.Variant(val, vtype), SourceTimestamp=now, ServerTimestamp=now)
                    await server.write_attribute_value(nodes[name].nodeid, dv)
                    last[name] = val
            await asyncio.sleep(CYCLE_S)


if __name__ == "__main__":
    asyncio.run(main())
