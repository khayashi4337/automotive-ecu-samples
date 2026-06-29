# ECU Evaluation Report

| Item | Value |
|---|---|
| Environment | SiLS |
| Date        | 2026-06-29 17:02:48 |

## Overall Status

| Tool | Result |
|---|---|
| 01 Log Parser     | ✅ OK |
| 02 GTest Reporter | ⚠️ 1 FAILED |
| 03 CAN Parser     | ✅ OK |

## 1. ECU Log Parser

- Total log entries    : **7**
- ENGINE > 6000 alerts : **2**

## 2. GTest Reporter

- Result : **4/5 PASSED**

## Test Details

| Suite | Test | Requirement | Result | Time (ms) |
|---|---|---|---|---|
| EngineTest | NormalRPM_REQ001 | REQ001 | ✅ PASS | 0.01 |
| EngineTest | OverRPM_REQ002 | REQ002 | ❌ FAIL | 0.25 |
| BrakeTest | NormalPressure_REQ010 | REQ010 | ✅ PASS | 0.00 |
| BrakeTest | EmergencyBrake_REQ011 | REQ011 | ✅ PASS | 0.00 |
| ThermalTest | CoolantTemp_REQ020 | REQ020 | ✅ PASS | 0.00 |


## 3. CAN Parser

- Decoded frames : **4**
- Unknown frames : **1**

```
=== CAN Frame Decoder ===

Frame 0C1#1A005A00000000
  ENGINE_RPM       = 1664.00 rpm
  COOLANT_TEMP     = 50.00 degC
Frame 0C1#2000640000000000
  ENGINE_RPM       = 2048.00 rpm
  COOLANT_TEMP     = 60.00 degC
Frame 1A0#13880000000000
  BRAKE_PRESSURE   = 500.00 kPa
Frame 2B0#27100000000000
  VEHICLE_SPEED    = 100.00 km/h
[FFF#DEADBEEF00000000] → unknown ID
```
