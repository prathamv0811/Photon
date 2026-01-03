"""
Generic Remote Robot Client for Remote Teleoperation.
Acts as a local proxy for a remote robot served by RobotHost.
"""

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import zmq
import cv2

from lerobot.robots.lekiwi.config_lekiwi import LeKiwiClientConfig
from lerobot.robots import Robot

@dataclass
class RemoteRobotClientConfig(LeKiwiClientConfig):
    """Configuration for the remote robot client."""
    # We reuse LeKiwiClientConfig as it has the necessary network fields (ip, ports)
    pass

class RemoteRobotClient(Robot):
    """
    Generic client to control a remote robot over ZMQ.
    Mimics the LeKiwiClient structure but for generic robots.
    """
    
    def __init__(self, config: RemoteRobotClientConfig):
        # We don't call super().__init__ because Robot might expect physical hardware config
        # Instead we just store the config and initialize minimal state
        self.config = config
        self.camera_config = config.cameras
        
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
        
        # Cache for last received data
        self.last_observation = None
        
        # We need to know features for teleop?
        # Typically Robot classes define features like 'action_features'
        # For a generic remote client, we might need to dynamically discover them or default to something?
        # For now, let's assume we are mostly just passing dictionaries through.
        # But lerobot processor pipelines might check features.
        # Let's see if we can get away without defining them strictly or infer them.
        self.action_features = getattr(config, 'action_features', {}) 
        self.state_features = getattr(config, 'state_features', {})
        self.cameras = getattr(config, 'cameras', {})

    def connect(self):
        logging.info(f"Connecting to remote robot at {self.remote_ip}...")
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
             
        # Convert numpy actions to list if needed for JSON serialization
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
            msg = self.zmq_observation_socket.recv_string(zmq.NOBLOCK)
            # Drain queue to get latest
            while True:
                try:
                   msg = self.zmq_observation_socket.recv_string(zmq.NOBLOCK)
                except zmq.Again:
                    break
                    
            data = json.loads(msg)
            
            # Decode images
            processed_obs = {}
            for k, v in data.items():
                 # Heuristic to detect base64 images? 
                 # Or rely on config.cameras keys?
                 if k in self.camera_config: # keys matching camera names
                     if isinstance(v, str) and len(v) > 100: # likely b64
                         try:
                             jpg_data = base64.b64decode(v)
                             np_arr = np.frombuffer(jpg_data, dtype=np.uint8)
                             frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                             if frame is not None:
                                 processed_obs[k] = frame
                             else:
                                 # Fallback empty frame?
                                 processed_obs[k] = np.zeros((480, 640, 3), dtype=np.uint8)
                         except:
                            processed_obs[k] = v
                     else:
                        processed_obs[k] = v
                 elif isinstance(v, list):
                     processed_obs[k] = np.array(v, dtype=np.float32)
                 else:
                     processed_obs[k] = v
            
            self.last_observation = processed_obs
            return processed_obs
            
        except zmq.Again:
            if self.last_observation is not None:
                return self.last_observation
            return {} # Should ideally block or wait?

    def teleop_step(self, record_data=False):
        pass
        
    def capture_observation(self):
        pass
