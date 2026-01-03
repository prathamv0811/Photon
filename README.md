# Photon CLI

<div align="center">

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/license/apache-2-0)

**Distributed Robotic Communication & Training with LeRobot**

</div>

Photon CLI manages distributed robotic setups, enabling teleoperation between a **Host** (Follower arm) and a **Client** (Leader arm), multi-camera dataset recording, and training on Nvidia Brev.

## Installation

```bash
git clone https://github.com/prathamv0811/Photon.git
cd photon-cli
pip install -e .
```

## Commands

### `photon calibrate`
Auto-detects the connected arm (Leader by default) and runs calibration.

```bash
# Auto-detect leader and calibrate
photon calibrate

# Calibrate specific arm
photon calibrate --arm follower
```

### `photon host`
Start the Follower Arm Server. Run this on the machine connected to the robot (follower).

```bash
photon host
```

### `photon client`
Start the Leader Arm Client for Teleoperation. Run this on the machine with the leader arm.

```bash
photon client
```

### `photon record`
Record a dataset with multi-camera support.

```bash
photon record
```

### `photon train`
Train a policy. Supports local training or Nvidia Brev.

```bash
# Train locally
photon train --compute local

# Train on Nvidia Brev
photon train --compute brev
```

## Configuration
Configuration is stored in `~/.photon/config.json`.
Port detection is automatic.
