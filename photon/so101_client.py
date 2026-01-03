"""
SO101 Remote Client for Wireless Teleoperation and Recording.
"""
import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict

import cv2
import numpy as np
import zmq

from lerobot.common.robot_devices.robots.config import RobotConfig
from lerobot.common.robot_devices.cameras.configs import CameraConfig
from lerobot.common.robot_devices.robots.robot import Robot

# Config for SO101 Remote Client
@RobotConfig.register_subclass("so101_remote_client")
@dataclass
class SO101RemoteClientConfig(RobotConfig):
    # Network Configuration
    remote_ip: str
    port_zmq_cmd: int = 5555
    port_zmq_observations: int = 5556

    # SO101 default dictionary logic
    cameras: dict[str, CameraConfig] = field(default_factory=dict)
    
    polling_timeout_ms: int = 15
    connect_timeout_s: int = 5


class SO101RemoteClient(Robot):
    """
    Client to control a remote SO101 robot over ZMQ.
    """
    
    def __init__(self, config: SO101RemoteClientConfig):
        self.config = config
        # robot.py expects cameras dict
        self.cameras = config.cameras
        
        self.remote_ip = config.remote_ip
        self.port_cmd = config.port_zmq_cmd
        self.port_obs = config.port_zmq_observations
        self.connect_timeout_s = config.connect_timeout_s
        self.polling_timeout_ms = config.polling_timeout_ms

        self.zmq_context = zmq.Context()
        self.zmq_cmd_socket = self.zmq_context.socket(zmq.PUSH)
        self.zmq_cmd_socket.setsockopt(zmq.CONFLATE, 1)

        self.zmq_observation_socket = self.zmq_context.socket(zmq.PULL)
        self.zmq_observation_socket.setsockopt(zmq.CONFLATE, 1)

        self._is_connected = False
        self.last_observation = None
        
        # Initialize internal cache
        self.last_frames = {}
        self.last_remote_state = {}

    def connect(self):
        logging.info(f"Connecting to remote SO101 at {self.remote_ip}...")
        self.zmq_cmd_socket.connect(f"tcp://{self.remote_ip}:{self.port_cmd}")
        self.zmq_observation_socket.connect(f"tcp://{self.remote_ip}:{self.port_obs}")
        
        # Wait for first observation to confirm connection
        logging.info("Waiting for first observation...")
        poller = zmq.Poller()
        poller.register(self.zmq_observation_socket, zmq.POLLIN)
        
        socks = dict(poller.poll(self.connect_timeout_s * 1000))
        if self.zmq_observation_socket not in socks:
            raise TimeoutError(f"Could not connect to {self.remote_ip}")
            
        self._is_connected = True
        logging.info("Connected!")

    def disconnect(self):
        if self._is_connected:
            self.zmq_cmd_socket.close()
            self.zmq_observation_socket.close()
            self.zmq_context.term()
            self._is_connected = False

    def send_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Send action dict to remote host"""
        if not self._is_connected:
             raise RuntimeError("Not connected")
             
        # Convert numpy actions to list for JSON serialization if needed
        # SO101 actions are usually just numpy arrays, but we send as JSON keys
        action_json = {}
        
        # Handle simple action structure
        # actions is often a dict with 'action': np.array or separate joint keys
        # We assume standard dictionary passing
        for k, v in action.items():
            if isinstance(v, np.ndarray):
                action_json[k] = v.tolist()
            else:
                action_json[k] = v
                
        self.zmq_cmd_socket.send_string(json.dumps(action_json))
        return action

    def get_observation(self) -> Dict[str, Any]:
        """Receive observation dict from remote host"""
        if not self._is_connected:
             raise RuntimeError("Not connected")
             
        # Poll for latest message
        try:
            msg = self.zmq_observation_socket.recv_string(zmq.NOBLOCK)
            # Drain queue to get latest
            while True:
                try:
                   msg = self.zmq_observation_socket.recv_string(zmq.NOBLOCK)
                except zmq.Again:
                    break
                    
            data = json.loads(msg)
            
            processed_obs = {}
            frames = {}
            
            for k, v in data.items():
                 # Detect if this key matches a known camera
                 if k in self.config.cameras:
                     if isinstance(v, str) and len(v) > 100: # Base64 image
                         try:
                             jpg_data = base64.b64decode(v)
                             np_arr = np.frombuffer(jpg_data, dtype=np.uint8)
                             frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                             if frame is not None:
                                 frames[k] = frame
                             else:
                                 frames[k] = np.zeros((480, 640, 3), dtype=np.uint8)
                         except:
                             frames[k] = v
                     else:
                        frames[k] = v
                 elif isinstance(v, list):
                     processed_obs[k] = np.array(v, dtype=np.float32)
                 else:
                     processed_obs[k] = v
            
            # Merge frames and state data
            # Robot class usually expects a unified dictionary
            full_obs = {**processed_obs, **frames}
            
            self.last_observation = full_obs
            return full_obs
            
        except zmq.Again:
            if self.last_observation is not None:
                return self.last_observation
            # Only if totally empty
            return {} 
    
    def teleop_step(self, record_data=False):
        pass
        
    def capture_observation(self):
        return self.get_observation()
