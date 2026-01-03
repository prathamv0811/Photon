# Photon CLI - User Guide

Photon is a command-line interface for distributed robotic communication, data collection, and training, built on top of [LeRobot](https://github.com/huggingface/lerobot).

## Features

- **Distributed Control**: Control a follower robot (e.g., SO100, SO101) using a leader arm over a network.
- **Data Recording**: Collect datasets with multi-camera support.
- **Training**: Train policies locally or on Nvidia Brev cloud instances.
- **Model Support**: Train various models including SmolVLA, ACT, Diffusion, TDMPC, VQ-BeT, and SARM.

---

## Installation

### Prerequisites
- Python 3.10+ (Recommended: 3.12)
- `uv` package manager (recommended) or `pip`

### Install with uv (Recommended)

```bash
git clone https://github.com/prathamv0811/Photon.git
cd photon-cli
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

### Install with pip

```bash
git clone https://github.com/prathamv0811/Photon.git
cd photon-cli
pip install -e .
```

---

## Usage Workflow

### 1. Calibration

Before using your robots, calibrate them to identify ports and motor IDs.

```bash
photon calibrate --arm choice  # choice: leader, follower, or all
```

- Follow the on-screen instructions to set the arm to zero position.
- This creates a configuration file in `~/.photon/config.json`.

### 2. Data Recording

Collect demonstration data for training.

```bash
photon record
```

- You will be prompted for:
    - **Robot Type**: SO100 or SO101.
    - **Dataset Name**: e.g., `my-pick-place-task`.
    - **Task Description**: e.g., "Pick up the red cube".
    - **Episode Duration**: e.g., 60 seconds.
    - **Number of Episodes**: e.g., 50.
- Use the leader arm to demonstrate the task.
- Press `Right Arrow` to finish an episode early.
- Press `Left Arrow` to discard the current episode.
- Press `Esc` to stop recording.

### 3. Training

Train a policy using your collected dataset.

#### Local Training

```bash
photon train
```

- **HuggingFace Auth**: Log in to access datasets and push models.
- **Dataset**: Select your dataset (local or HuggingFace ID).
- **Model Selection**: Choose from:
    1. **SmolVLA**: Vision-Language-Action model (powerful, requires more VRAM).
    2. **ACT**: Action Chunking with Transformers (good for precise manipulation).
    3. **PI0**: Policy Iteration Zero.
    4. **TDMPC**: Model-based RL.
    5. **Diffusion**: Diffusion Policy (robust, generally good performance).
    6. **VQ-BeT**: Vector Quantized Behavior Transformer.
    7. **SARM**: State-Action Reward Model.
- **Configuration**: Set training steps (default 20,000) and batch size.

#### Remote Training (Nvidia Brev)

Train on a powerful cloud GPU instance.

```bash
photon train --compute brev
```

1.  **Navigating to Brev**: The CLI will guide you to [console.brev.dev](https://console.brev.dev) to start an instance.
2.  **Login & Connect**: It handles Brev CLI login and connection.
3.  **Remote Setup**: Once connected, it provides commands to run on the remote machine:
    ```bash
    git clone https://github.com/prathamv0811/Photon.git
    cd photon-cli
    pip install -e .
    photon train
    ```
4.  **Training**: Run `photon train` inside the remote shell to start the interactive training process described above.

### 4. Evaluation / Inference

Run your trained policy on the robot.

```bash
photon client
```
(Note: Specific inference command might vary depending on implementation, check `photon --help` for `client` or `host` modes if meant for teleoperation, or if `inference_mode` is exposed).

### 5. Running on Nvidia Jetson (Host Mode)

To control a robot arm connected to an Nvidia Jetson device (Follower):

1.  **Setup**: SSH into your Jetson.
    ```bash
    ssh user@jetson-ip-address
    ```

2.  **Permissions**: Ensure you have access to the USB ports (usually `/dev/ttyUSB0`).
    ```bash
    sudo usermod -a -G dialout $USER
    # You may need to logout and login again
    sudo chmod 666 /dev/ttyUSB*
    ```

3.  **Installation**:
    ```bash
    git clone https://github.com/prathamv0811/Photon.git
    cd Photon
    pip install -e .
    ```

4.  **Start Host**:
    ```bash
    photon host
    ```
    The Jetson is now ready to receive commands from the leader arm.

---

## FAQ

### What are the maximum parameters or number of episodes I can collect?

**There is no hard-coded limit** in Photon or LeRobot for the number of episodes or parameters. The limits are determined by your hardware:

*   **Storage**: A 50-episode dataset with video at 30fps might be a few GBs. Ensure you have enough disk space.
*   **RAM**: Loading very large datasets into memory (if not streamed) requires sufficient RAM. LeRobot supports streaming datasets (`--streaming` flag in underlying scripts, though Photon defaults to downloading).
*   **Training**:
    *   **Number of Episodes**: More episodes generally lead to better generalization. Common datasets range from 50 to 1000+ episodes. 50 is a good starting point for simple tasks.
    *   **Model Parameters**:
        *   **ACT / Diffusion**: Typically tens or hundreds of millions of parameters. trainable on consumer GPUs (e.g., RTX 3090/4090).
        *   **SmolVLA**: Uses a VLM backbone (e.g., 2B+ parameters). Training (fine-tuning) requires significant VRAM (24GB+ recommended, or A100/H100 on cloud).
    *   **Max Episodes**: Technically, you can collect thousands. The bottleneck is usually your time and patience!

### Troubleshooting

- **`env: ‘photon’: No such file or directory`**: Ensure you have installed the package and your virtual environment is active (`source .venv/bin/activate`).
- **Import Errors**: Ensure you are using a compatible version of `lerobot` and Python 3.10+.
- **Robot Connection**: Check USB connections and permissions (`sudo chmod 666 /dev/ttyUSB*`).
