"""
Teleoperation utilities for LeRobot
"""

import typer
from rich.prompt import Confirm, Prompt
from typing import Dict, Optional

from photon.config import (
    get_robot_config_classes,
    create_follower_config,
    get_known_ids,
    save_lerobot_config,
)
from photon.mode_config import use_preconfigured_args
from photon.ports import detect_arm_port, detect_and_retry_ports
from lerobot.scripts.lerobot_teleoperate import teleoperate, TeleoperateConfig
from photon.config import validate_lerobot_config

def teleoperation(config: dict = None, auto_use: bool = False) -> bool:
    leader_id = None
    follower_id = None
    camera_config = None

    preconfigured = use_preconfigured_args(config, 'teleop', 'Teleoperation', auto_use=auto_use)
    if preconfigured:
        leader_port = preconfigured.get('leader_port')
        follower_port = preconfigured.get('follower_port')
        robot_type = preconfigured.get('robot_type')
        camera_config = preconfigured.get('camera_config')
        leader_id = preconfigured.get('leader_id')
        follower_id = preconfigured.get('follower_id')
    

    if not preconfigured:
        # Validate configuration using utility function
        leader_port, follower_port, leader_calibrated, follower_calibrated, robot_type = validate_lerobot_config(config)
        
        if not robot_type:
            # Ask for robot type
            typer.echo("\n🤖 Select your robot type:")
            typer.echo("1. SO100")
            typer.echo("2. SO101")
            typer.echo("3. LeKiwi")
            robot_choice = int(Prompt.ask("Enter robot type", default="2"))
            if robot_choice == 1:
                robot_type = "so100"
            elif robot_choice == 2:
                robot_type = "so101"
            else:
                robot_type = "lekiwi"
            config['robot_type'] = robot_type
        if not leader_port and robot_type != "lekiwi":
            leader_port = detect_arm_port("leader")
            config['leader_port'] = leader_port
            
        if not follower_port:
            if robot_type == "lekiwi":
                follower_port = Prompt.ask("Enter LeKiwi IP address", default="192.168.1.100")
            else:
                follower_port = detect_arm_port("follower")
                if not follower_port:
                    # Provide option for remote connection
                     if Confirm.ask(f"Could not find local {robot_type} follower. Connect to remote robot (IP)?", default=False):
                          follower_port = Prompt.ask(f"Enter {robot_type} IP address")
            config['follower_port'] = follower_port
    
        # Prompt/select ids if not provided
        known_leader_ids, known_follower_ids = get_known_ids(config)
        default_leader_id = config.get('lerobot', {}).get('leader_id') or f"{robot_type}_leader"
        default_follower_id = config.get('lerobot', {}).get('follower_id') or f"{robot_type}_follower"

        if not leader_id:
            if known_leader_ids:
                typer.echo("📇 Known leader ids:")
                for i, kid in enumerate(known_leader_ids, 1):
                    typer.echo(f"   {i}. {kid}")
            leader_id = Prompt.ask("Enter leader id", default=default_leader_id)
        if not follower_id and robot_type != "lekiwi": # LeKiwi usually doesn't need explicit ID prompt if IP is used, or maybe it does? default is fine.
            # Actually keep prompt for consistency or specific configs
            pass
        if not follower_id:
            if known_follower_ids:
                typer.echo("📇 Known follower ids:")
                for i, kid in enumerate(known_follower_ids, 1):
                    typer.echo(f"   {i}. {kid}")
            follower_id = Prompt.ask("Enter follower id", default=default_follower_id)
        
        # Setup cameras if not provided
        if camera_config is None:
            use_camera = Confirm.ask("Would you like to setup cameras?", default=True)
            if use_camera:
                from photon.cameras import setup_cameras
                camera_config = setup_cameras()
            else:
                # Set empty camera config when user chooses not to use cameras
                camera_config = {'enabled': False, 'cameras': []}

    try:
        # Determine config classes based on robot type
        leader_config_class, follower_config_class = get_robot_config_classes(robot_type)
        
        if follower_config_class is None:
            typer.echo(f"❌ Unsupported robot type for teleoperation: {robot_type}")
            return False
            
        # Handle optional leader for LeKiwi
        if robot_type == "lekiwi" and leader_config_class is None:
            use_leader = Confirm.ask("Do you want to use a physical leader arm?", default=False)
            if use_leader:
                 typer.echo("Select leader arm type:")
                 typer.echo("1. SO100")
                 typer.echo("2. SO101")
                 l_choice = int(Prompt.ask("Leader type", default="2"))
                 l_type = "so100" if l_choice == 1 else "so101"
                 leader_config_class, _ = get_robot_config_classes(l_type)
                 
                 if not leader_port:
                     leader_port = detect_arm_port("leader")
                     
                 if not leader_id:
                      leader_id = Prompt.ask("Enter leader id", default=f"{l_type}_leader")

        # Create configurations
        if leader_config_class:
            leader_config = leader_config_class(port=leader_port, id=leader_id)
        else:
            leader_config = None
        
        # Create robot config with cameras if enabled
        if robot_type == "lekiwi":
             # LeKiwi uses remote_ip
             if camera_config:
                 follower_config = follower_config_class(
                    remote_ip=follower_port,
                    id=follower_id or f"{robot_type}_follower",
                    cameras=camera_config
                 )
             else:
                 follower_config = follower_config_class(
                    remote_ip=follower_port,
                    id=follower_id or f"{robot_type}_follower"
                 )
        else:
            follower_config = create_follower_config(
            follower_config_class,
            follower_port,
            robot_type,
            camera_config,
            follower_id=follower_id,
        )
        
        # Create teleoperation config
        teleop_config = TeleoperateConfig(
            teleop=leader_config,
            robot=follower_config,
            fps=60,
            display_data=True
        )
        
        # Save configuration before execution (if not using preconfigured settings)
        if config and not preconfigured:
            from .mode_config import save_teleop_config
            save_teleop_config(
                config,
                leader_port,
                follower_port,
                robot_type,
                camera_config,
                leader_id,
                follower_id,
            )
        
        typer.echo("🎮 Starting teleoperation... Press Ctrl+C to stop.")
        typer.echo("📋 Move the leader arm to control the follower arm.")
        
        # Start teleoperation with retry logic
        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                teleoperate(teleop_config)
                
                return True
                
            except Exception as e:
                error_msg = str(e)
                # Check if it's a port connection error
                if "Could not connect on port" in error_msg or "Make sure you are using the correct port" in error_msg:
                    if attempt < max_retries:
                        typer.echo(f"❌ Connection failed: {error_msg}")
                        typer.echo("🔄 Attempting to detect new ports...")
                        
                        # Detect new ports and retry
                        new_leader_port, new_follower_port = detect_and_retry_ports(leader_port, follower_port, config)
                        
                        if new_leader_port != leader_port or new_follower_port != follower_port:
                            # Update ports and recreate configs
                            leader_port, follower_port = new_leader_port, new_follower_port
                            leader_config = leader_config_class(port=leader_port, id=leader_id)
                            follower_config = create_follower_config(
                                follower_config_class,
                                follower_port,
                                robot_type,
                                camera_config,
                                follower_id=follower_id,
                            )
                            teleop_config = TeleoperateConfig(
                                teleop=leader_config,
                                robot=follower_config,
                                fps=60,
                                display_data=True
                            )
                            typer.echo("🔄 Retrying teleoperation with new ports...")
                            continue
                        else:
                            typer.echo("❌ Could not find new ports. Please check connections.")
                            return False
                    else:
                        typer.echo(f"❌ Teleoperation failed after retry: {error_msg}")
                        return False
                else:
                    # Non-port related error
                    typer.echo(f"❌ Teleoperation failed: {error_msg}")
                    return False
        
    except KeyboardInterrupt:
        typer.echo("\n🛑 Teleoperation stopped by user.")
        return True
