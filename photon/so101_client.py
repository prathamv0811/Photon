"""
SO101 Remote Client for Wireless Teleoperation and Recording.
"""
import base64
import json
import logging
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Dict

import cv2
import numpy as np
import zmq

from lerobot.common.robot_devices.robots.config import RobotConfig
from lerobot.common.robot_devices.cameras.configs import CameraConfig
from lerobot.common.robot_devices.robots.robot import Robot
from lerobot.common.utils.utils import init_logging

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
    
    # Matching SO101 features, though used remotely
    use_degrees: bool = False


class SO101RemoteClient(Robot):
    """
    Client to control a remote SO101 robot over ZMQ.
    Mimics SO101Follower features for potential recording compatibility.
    """
    config_class = SO101RemoteClientConfig
    name = "so101_remote_client"
    
    def __init__(self, config: SO101RemoteClientConfig):
        super().__init__(config)
        self.config = config
        self.cameras = config.cameras # This is sufficient for Robot base class to know about cameras? 
        # Actually Robot base class expects self.cameras to be initialized objects if we use them locally.
        # But here they are remote. However, lerobot recorder might check them.
        # LeKiwiClient did `self.cameras = make_cameras_from_configs(config.cameras)` but those are local cameras.
        # We probably don't want to instantiate local cameras for a remote client.
        # LeKiwi example code simply used `self.cameras` as properties or from config.
        # Let's assume for now we don't need local camera objects, just feature definitions.
        
        self.remote_ip = config.remote_ip
        self.port_cmd = config.port_zmq_cmd
        self.port_obs = config.port_zmq_observations
        self.connect_timeout_s = config.connect_timeout_s
        self.polling_timeout_ms = config.polling_timeout_ms

        self.zmq_context = None
        self.zmq_cmd_socket = None
        self.zmq_observation_socket = None

        self._is_connected = False
        self.last_observation = None
        
        # Initialize internal cache
        self.last_frames = {}
        self.last_remote_state = {}

    @property
    def encoded_motors(self):
        # SO101 standard motors
        return [
            "shoulder_pan",
            "shoulder_lift",
            "elbow_flex",
            "wrist_flex",
            "wrist_roll",
            "gripper"
        ]

    @property
    def _motors_ft(self) -> dict[str, type]:
        return {f"{motor}.pos": float for motor in self.encoded_motors}

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        return {
            name: (cfg.height, cfg.width, 3) for name, cfg in self.config.cameras.items()
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._motors_ft

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect(self):
        logging.info(f"Connecting to remote SO101 at {self.remote_ip}...")
        self.zmq_context = zmq.Context()
        
        # CMD Socket (PUSH)
        self.zmq_cmd_socket = self.zmq_context.socket(zmq.PUSH)
        self.zmq_cmd_socket.setsockopt(zmq.CONFLATE, 1)
        self.zmq_cmd_socket.connect(f"tcp://{self.remote_ip}:{self.port_cmd}")
        
        # OBS Socket (PULL)
        self.zmq_observation_socket = self.zmq_context.socket(zmq.PULL)
        self.zmq_observation_socket.setsockopt(zmq.CONFLATE, 1)
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
             
        # SO101 actions are usually just numpy arrays, but we send as JSON keys/values
        # The host expects the same dictionary format as 'action'
        action_json = {}
        
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
            # Drain queue to get latest
            msg = None
            try:
                # Try to read multiple times to get the very last one
                while True:
                    msg = self.zmq_observation_socket.recv_string(zmq.NOBLOCK)
            except zmq.Again:
                pass
            
            # If we didn't get any message in the drain loop, wait for one
            if msg is None:
                msg = self.zmq_observation_socket.recv_string(zmq.NOBLOCK)

            data = json.loads(msg)
            
            processed_obs = {}
            frames = {}
            
            for k, v in data.items():
                 # Check if key is a configured camera
                 if k in self.config.cameras:
                     if isinstance(v, str) and len(v) > 0: # Base64 image
                         try:
                             jpg_data = base64.b64decode(v)
                             np_arr = np.frombuffer(jpg_data, dtype=np.uint8)
                             frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                             if frame is not None:
                                 frames[k] = frame
                             else:
                                 # Fallback empty frame matching config dim
                                 h, w = self.config.cameras[k].height, self.config.cameras[k].width
                                 frames[k] = np.zeros((h, w, 3), dtype=np.uint8)
                         except Exception as e:
                             logging.error(f"Error decoding image {k}: {e}")
                             h, w = self.config.cameras[k].height, self.config.cameras[k].width
                             frames[k] = np.zeros((h, w, 3), dtype=np.uint8)
                     else:
                        # Maybe empty string or failed encoding
                        h, w = self.config.cameras[k].height, self.config.cameras[k].width
                        frames[k] = np.zeros((h, w, 3), dtype=np.uint8)
                 elif isinstance(v, list):
                     processed_obs[k] = np.array(v, dtype=np.float32)
                 else:
                     processed_obs[k] = v
            
            # Merge frames and state data
            full_obs = {**processed_obs, **frames}
            
            self.last_observation = full_obs
            return full_obs
            
        except zmq.Again:
            if self.last_observation is not None:
                return self.last_observation
            # Only if totally empty
            return {} 
            
    def capture_observation(self):
        return self.get_observation()
