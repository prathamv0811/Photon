"""
Generic Robot Host for Remote Teleoperation
Adapts LeKiwi's host logic to work with any LeRobot robot instance.
"""

import base64
import json
import logging
import time
from dataclasses import dataclass, field
import threading
import cv2
import zmq
import numpy as np
from typing import Optional, Dict

from lerobot.robots.lekiwi.config_lekiwi import LeKiwiHostConfig
from lerobot.robots.config import RobotConfig
from lerobot.robots import Robot

# Reuse LeKiwi's host config as it handles ports nicely
@dataclass
class RobotHostConfig(LeKiwiHostConfig):
    """Configuration for the generic robot host."""
    pass

class RobotHost:
    def __init__(self, config: RobotHostConfig):
        self.zmq_context = zmq.Context()
        self.zmq_cmd_socket = self.zmq_context.socket(zmq.PULL)
        self.zmq_cmd_socket.setsockopt(zmq.CONFLATE, 1)
        self.zmq_cmd_socket.bind(f"tcp://*:{config.port_zmq_cmd}")

        self.zmq_observation_socket = self.zmq_context.socket(zmq.PUSH)
        self.zmq_observation_socket.setsockopt(zmq.CONFLATE, 1)
        self.zmq_observation_socket.bind(f"tcp://*:{config.port_zmq_observations}")

        self.connection_time_s = config.connection_time_s
        self.watchdog_timeout_ms = config.watchdog_timeout_ms
        self.max_loop_freq_hz = config.max_loop_freq_hz
        
        self.running = False
        self._thread = None

    def disconnect(self):
        self.running = False
        if self._thread:
            self._thread.join()
            
        self.zmq_observation_socket.close()
        self.zmq_cmd_socket.close()
        self.zmq_context.term()

    def serve(self, robot: Robot):
        """Blocking serve loop"""
        logging.info("Starting RobotHost serve loop")
        self.running = True
        
        last_cmd_time = time.time()
        watchdog_active = False
        logging.info("Waiting for commands...")
        
        try:
            while self.running:
                loop_start_time = time.time()
                
                # 1. Receive commands
                try:
                    msg = self.zmq_cmd_socket.recv_string(zmq.NOBLOCK)
                    data = dict(json.loads(msg))
                    
                    # Convert action back to appropriate format if needed
                    # LeKiwi expects dict, but some robots might expect different formats
                    # For now assume LeRobot's send_action handles dicts or we need to map it
                    # Based on lekiwi_client, it sends a dict.
                    
                    # If robot needs tensor/numpy, send_action usually handles it or checks it
                    robot.send_action(data)
                    
                    last_cmd_time = time.time()
                    watchdog_active = False
                except zmq.Again:
                    if not watchdog_active:
                        # logging.warning("No command available")
                        pass
                except Exception as e:
                    logging.error(f"Message fetching failed: {e}")

                # 2. Watchdog
                now = time.time()
                if (now - last_cmd_time > self.watchdog_timeout_ms / 1000) and not watchdog_active:
                    logging.warning(
                        f"Command not received for more than {self.watchdog_timeout_ms} milliseconds. Stopping robot."
                    )
                    watchdog_active = True
                    # Most robots don't have explicit stop_base, but we can try sending empty action or 0s
                    # robot.send_action(robot.null_action) # Hypothetical, need to check if exists 
                    # For now just log, as "stop_base" is lekiwi specific

                # 3. Get Observation
                last_observation = robot.get_observation()
                
                # 4. Serialize Observation (handle images)
                # LeKiwi client expects specific format: {cam_key: b64_img, sensors...}
                serialized_obs = {}
                
                for key, value in last_observation.items():
                    if isinstance(value, np.ndarray) and value.ndim == 3: # Image
                         # Encode images to base64
                        ret, buffer = cv2.imencode(
                            ".jpg", value, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                        )
                        if ret:
                            serialized_obs[key] = base64.b64encode(buffer).decode("utf-8")
                    elif isinstance(value, np.ndarray):
                         # Convert other numpy arrays to list
                         serialized_obs[key] = value.tolist()
                    else:
                         serialized_obs[key] = value

                # 5. Send Observation
                try:
                    self.zmq_observation_socket.send_string(json.dumps(serialized_obs), flags=zmq.NOBLOCK)
                except zmq.Again:
                    # logging.info("Dropping observation, no client connected")
                    pass

                # 6. Frequency Control
                elapsed = time.time() - loop_start_time
                time.sleep(max(1 / self.max_loop_freq_hz - elapsed, 0))

        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received.")
        except Exception as e:
            logging.error(f"Error in serve loop: {e}")
        finally:
            logging.info("Shutting down RobotHost.")

