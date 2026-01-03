"""
Remote Host utilities for LeRobot
"""
import typer
from rich.console import Console
from rich.prompt import Prompt

from photon.remote_host import RobotHost, RobotHostConfig
from photon.config import (
    validate_lerobot_config,
    get_robot_config_classes,
    create_follower_config,
    create_robot_configs
)
from photon.ports import detect_arm_port
from lerobot.robots import make_robot_from_config
from photon.cameras import setup_cameras

console = Console()

def serve_robot(config: dict, auto_use: bool = False):
    """
    Start a RobotHost to serve a robot over the network.
    """
    typer.echo("🚀 Starting Robot Remote Host...")

    # 1. Reuse existing config detection logic from teleoperation/motor setup
    # We want to host the robot, so we treat it as a "follower" (even if it's the only one)
    # or just a "robot". The terminology in config.py uses 'follower' for the manipulated robot.
    
    lerobot_config = config.get('lerobot', {})
    existing_robot_type = lerobot_config.get('robot_type')
    existing_follower_port = lerobot_config.get('follower_port')
    
    # Select Robot Type
    if not existing_robot_type:
        typer.echo("\n🤖 Select robot to host:")
        typer.echo("1. SO100")
        typer.echo("2. SO101")
        # LeKiwi already has its own host script usually, but we can wrap it if we want genericism.
        # But LeKiwi user likely already setup LeKiwi on the pi.
        # This command is for hosting OTHER robots.
        robot_choice = int(Prompt.ask("Enter robot type", default="2"))
        robot_type = "so100" if robot_choice == 1 else "so101"
        config['robot_type'] = robot_type
    else:
        robot_type = existing_robot_type
        
    # Select Port
    follower_port = existing_follower_port
    if not follower_port:
         follower_port = detect_arm_port("follower")
         
    if not follower_port:
        typer.echo("❌ Failed to detect robot arm port.")
        # Optional: Ask user to enter port manually?
        follower_port = Prompt.ask("Enter robot port manually (e.g. /dev/ttyUSB0)")
        
    # Camera Setup (Crucial for remote teleop)
    camera_config = lerobot_config.get('camera_config')
    if not camera_config:
         typer.echo("\n📷 Camera Setup")
         from rich.prompt import Confirm
         if Confirm.ask("Do you want to setup cameras for streaming?", default=True):
             camera_config = setup_cameras()
         else:
             camera_config = {'enabled': False, 'cameras': []}

    # Create Robot Config
    # We use create_follower_config to get the device config
    _, follower_config_class = get_robot_config_classes(robot_type)
    
    if not follower_config_class:
        typer.echo(f"❌ Unsupported robot type: {robot_type}")
        return

    # Create the internal robot configuration
    robot_config = create_follower_config(
        follower_config_class,
        follower_port,
        robot_type,
        camera_config,
        follower_id=f"{robot_type}_remote" 
    )
    
    # Initialize Robot
    try:
        typer.echo(f"🔌 Connecting to {robot_type} on {follower_port}...")
        robot = make_robot_from_config(robot_config)
        robot.connect()
        typer.echo("✅ Robot connected successfully.")
    except Exception as e:
        typer.echo(f"❌ Failed to connect to robot: {e}")
        return
        
    # Configure Host
    # Use standard LeKiwi ports by default
    host_config = RobotHostConfig(
        port_zmq_cmd=5555,
        port_zmq_observations=5556,
        max_loop_freq_hz=60
    )
    
    host = RobotHost(host_config)
    
    typer.echo(f"📡 Serving robot on port {host_config.port_zmq_cmd} (CMD) and {host_config.port_zmq_observations} (OBS)")
    typer.echo("Press Ctrl+C to stop serving.")
    
    try:
        host.serve(robot)
    except KeyboardInterrupt:
        pass
    finally:
        robot.disconnect()
        host.disconnect()
        typer.echo("🛑 Server stopped.")
