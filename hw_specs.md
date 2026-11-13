# Hardware specs

Hardware used by Heat Pump Doctor. Values marked *(check)* come from vendor material, not measured on our board yet.

## Arduino UNO Q
| Part | Spec |
|---|---|
| MCU | STM32U585, Arm Cortex-M33 up to 160 MHz, 2 MB flash, 786 KB SRAM. Runs the Arduino sketch on Zephyr |
| MPU | Qualcomm QRB2210, 4x Arm Cortex-A53 up to 2.0 GHz, Adreno 702 GPU. Runs Debian Linux + Python |
| Memory (our board) | 2 GB RAM variant, 3.1 GB free on `/` (measured 2026-11-13) |
| OS (our board) | Debian 13 trixie, kernel 6.16, Python 3.13.5, hostname `uno-q`, user `arduino` |
| MCU ⇄ MPU link | Arduino Bridge (RPC, MsgPack). Send features, not raw samples |
| Radio | Wi-Fi 5 dual band, Bluetooth 5.1 *(check)* |
| USB | One USB-C port. With a hub attached the board is USB host and `adb` over USB is gone; work over Wi-Fi |
| Expansion | Qwiic (I²C) connector for Modulinos, UNO headers |
| On-board | 8x13 LED matrix *(check)* |

## Sensors and actuators
| Module | Chip | Use | Notes |
|---|---|---|---|
| Modulino Movement | LSM6DSOX 6-axis IMU | Vibration | Accel ±2/4/8/16 g, ODR up to 6.66 kHz, 9 KB FIFO, I²C up to 1 MHz *(check)*. We plan ODR ~1.66–3.33 kHz, FIFO burst reads, I²C 400 kHz |
| Modulino Thermo | HS3003 *(check)* | Temperature, humidity: operating point, frost risk | ~1 Hz is enough |
| Modulino Buzzer | — | Alarm | |
| Modulino Pixels | 8 RGB LEDs | Status LED | If available |
| USB microphone | — | Sound anomalies | Linux side, check with `arecord -l` |
| USB camera | — | Coil icing / frost | Linux side, OpenCV, check with `v4l2-ctl --list-devices` |
| USB-C hub (powered) | — | Camera + mic | |

## Software versions (pinned)
- Mac: `arduino-cli` 1.6.0, core `arduino:zephyr` 1.1.0, FQBN `arduino:zephyr:unoq`
- Board image at first connection: Zephyr core 0.51.0, `arduino-app-cli` 0.6.6 (needs App Lab update)
- Libraries: see `sketch/sketch.yaml` (`Arduino_Modulino` 0.10.0, `Arduino_RouterBridge` 0.4.4, `Arduino_LSM6DSOX` 1.1.2, …)

## Demo rig
- Desk fan as the "heat pump"
- Faults: coin or tape on a blade (imbalance), loose mount, cardboard over the intake (blocked coil, 10 → 50 % covered)
- Optional Jetson for training only; the demo runs on the UNO Q
