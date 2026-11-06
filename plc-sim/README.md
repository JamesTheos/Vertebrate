# PLC simulator (demo without CODESYS)

Replaces the CODESYS demo PLC (project `ISPERome`) with a small Python OPC UA server.
It serves the same node IDs the bridges use (`ns=4;s=|var|CODESYS Control Win V3 x64.Application...`)
and re-implements the CFC logic from the PLCopenXML export, so Vertebrate behaves as with the real PLC.

## Run

```
docker compose --profile sim up --build
```

Starts Kafka, Postgres, the app (http://localhost:5001), the simulator and both bridges
(`PLC2Nexus.py`, `Nexus2PLC.py`). Without `--profile sim` everything works as before (real PLC).

- OPC UA: `opc.tcp://localhost:4840` (no security)
- Status page for the video: http://localhost:8081

## Behaviour (from the CODESYS project)

| Tag | Process Simulation 1 (Scene1) | Process Simulation 2 (Scene2) |
|---|---|---|
| CM001_MTemp | 5.0 + sine, amplitude 2 | 8.0 + sine, amplitude 8 |
| CM002_Speed | 350 + sine, amplitude 4 | 300 + sine, amplitude 8 |
| CM003_Pressure | 1.5 + sine, amplitude 4 | 0.0 + sine, amplitude 8 |
| CM004_AmbTemp | 15 + sine, amplitude 4 | 20 + sine, amplitude 8 |

Values only move while a scene is active and hold their last value otherwise.
`StartPhase1` is written by the workflow; `StopPhase1 = NOT StartPhase1`. Task cycle 100 ms.
