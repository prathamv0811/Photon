from pathlib import Path
import os
import sys
import typer
import subprocess
from rich.console import Console
from rich.prompt import Prompt, Confirm

# Photon modules are imported lazily inside commands to speed up CLI startup

app = typer.Typer()
console = Console()

@app.callback()
def callback():
    """
    Photon: Distributed Robotic Communication CLI.
    """
    pass

@app.command()
def calibrate(
    arm: str = typer.Option("leader", help="Arm to calibrate: 'leader', 'follower', or 'all'"),
    auto: bool = typer.Option(True, "--auto/--manual", help="Auto-detect SO101 arms"),
):
    """
    Calibrate SO101 robot arms for distributed control.
    """
    console.print(f"🔧 Starting calibration for {arm} arm...")
    from photon.config import load_config, save_lerobot_config
    from photon.calibration import calibration
    config = load_config()
    
    # Run calibration
    # function signature: calibration(main_config, arm_type)
    updated_config = calibration(config, arm)
    
    # Save config
    # calibration() returns a dict with 'leader_port', 'robot_type', etc.
    # It seems to return *just* the lerobot config part or the whole thing?
    # Checking calibration.py: returns `config` (dict).
    # And inside it calls `add_known_id` which saves to disk immediately.
    # But it also returns a config dict.
    # We should ensure `save_lerobot_config` is called if needed, but `calibration` seems to do some saving.
    # Actually `calibration.py` logic:
    # `add_known_id` saves.
    # But `leader_port` etc might not be saved if we don't call `save_lerobot_config`.
    # Let's save it to be safe.
    save_lerobot_config(config, updated_config)
    console.print(f"✅ Configuration saved.")

@app.command()
def host(
    auto_use: bool = typer.Option(False, "--yes", "-y", help="Automatically use saved settings"),
):
    """
    Start the follower arm server (Host mode).
    """
    console.print("🤖 Starting Photon Host (Follower Robot)...")
    from photon.config import load_config
    from photon.serve_robot import serve_robot as run_serve_robot
    config = load_config()
    run_serve_robot(config, auto_use)

@app.command()
def client(
    auto_use: bool = typer.Option(False, "--yes", "-y", help="Automatically use saved settings"),
):
    """
    Start the leader arm client (Teleoperation mode).
    """
    console.print("🎮 Starting Photon Client (Leader Teleoperation)...")
    from photon.config import load_config
    from photon.teleoperation import teleoperation as run_teleoperation
    config = load_config()
    run_teleoperation(config, auto_use)

@app.command()
def record(
    auto_use: bool = typer.Option(False, "--yes", "-y", help="Automatically use saved settings"),
):
    """
    Record dataset with multi-camera support.
    """
    console.print("📷 Starting recording session...")
    from photon.config import load_config
    from photon.recording import recording_mode
    config = load_config()
    recording_mode(config, auto_use)

@app.command()
def train(
    compute: str = typer.Option("local", "--compute", help="Compute backend: 'local' or 'brev'"),
    auto_use: bool = typer.Option(False, "--yes", "-y", help="Automatically use saved settings"),
):
    """
    Train a policy. Use --compute brev to run on Nvidia Brev.
    """
    console.print(f"🎓 Starting training mode (Compute: {compute})...")
    
    if compute.lower() == "brev":
        console.print("🚀 Initializing Nvidia Brev integration...")
        
        # 1. Guide User to Console
        console.print("\n🌐 Step 1: Navigating to Brev Console")
        console.print("   Please go to [bold blue]https://console.brev.dev[/bold blue]")
        console.print("   1. Log in to your account.")
        console.print("   2. Select or create a GPU instance.")
        console.print("   3. Start the instance.")
        typer.launch("https://console.brev.dev")
        Prompt.ask("Press Enter once your instance is RUNNING")

        # 2. Install CLI
        console.print("\n💻 Step 2: Install Brev CLI")
        # Check if already installed
        is_installed = False
        try:
            subprocess.run(["brev", "--version"], check=True, capture_output=True)
            console.print("✅ Brev CLI is already installed.")
            is_installed = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        if not is_installed:
            install_cmd = Prompt.ask("Paste the 'Install CLI' command from Brev console (or press Enter to skip if installed)")
            if install_cmd.strip():
                console.print("Running install command...")
                subprocess.run(install_cmd, shell=True)
            else:
                console.print("Skipping installation step.")

        # 3. Login CLI
        console.print("\n🔐 Step 3: Login to Brev CLI")
        console.print("Please run [bold green]brev login[/bold green] in a separate terminal, or I can run it here.")
        if Confirm.ask("Run 'brev login' now?", default=True):
             subprocess.run(["brev", "login"])
        else:
             Prompt.ask("Press Enter after you have logged in via terminal")

        # 4. Connect and Setup
        console.print("\n🖥️  Step 4: Connect to Brev Instance")
        machine_name = Prompt.ask("Enter your Brev machine name (e.g. 'verdant-gpu')")
        
        console.print(f"\n📝 Instructions for {machine_name}:")
        console.print("1. The CLI will open a shell to your remote machine.")
        console.print("2. Once connected, run these commands to set up Photon:")
        console.print("\n   # Clone and install Photon")
        console.print("   git clone https://github.com/GetSoloTech/photon-cli.git")
        console.print("   cd photon-cli")
        console.print("   pip install -e .")
        console.print("\n   # Start Training")
        console.print("   photon train")
        console.print("\n   ℹ️ The training script will guide you through:")
        console.print("   • HuggingFace Login")
        console.print("   • Dataset Selection")
        console.print("   • Model Selection (SmolVLA, ACT, etc.)")
        
        if Confirm.ask(f"\nReady to connect to {machine_name}?", default=True):
            console.print(f"🚀 Connecting to {machine_name}...")
            subprocess.run(["brev", "shell", machine_name])
        else:
            console.print("Aborted.")
            
    else:
        from photon.config import load_config
        from photon.recording import training_mode
        config = load_config()
        training_mode(config, auto_use)

if __name__ == "__main__":
    app()
