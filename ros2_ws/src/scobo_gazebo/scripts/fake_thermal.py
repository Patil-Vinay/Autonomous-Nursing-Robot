#!/usr/bin/env python3
"""Fake MLX90640 for the sim.

Turns a depth camera with the same view into 32 x 24 temperatures in deg C: skin on
the head, clothing on the body and room temperature elsewhere.
"""
import math

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from tf2_ros import Buffer, TransformException, TransformListener

from sim_patients import load_patients

WIDTH, HEIGHT = 32, 24
HEAD_RADIUS = 0.12


def rotation(q):
    w, x, y, z = q.w, q.x, q.y, q.z
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


class FakeThermal(Node):
    def __init__(self):
        super().__init__('fake_thermal')
        # MLX90640 noise per pixel, deg C
        self.noise = self.declare_parameter('noise', 0.25).value
        self.cfg, self.patients = load_patients(self)
        self.bridge = CvBridge()
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, self)
        self.truth = None
        self.rays = None
        self.info = None

        self.pub = self.create_publisher(Image, 'thermal/image', 10)
        self.info_pub = self.create_publisher(CameraInfo, 'thermal/camera_info', 10)
        self.create_subscription(Odometry, 'ground_truth', self.on_truth, 10)
        self.create_subscription(CameraInfo, 'thermal_sim/depth/camera_info', self.on_info,
                                 qos_profile_sensor_data)
        self.create_subscription(Image, 'thermal_sim/depth/image_raw', self.on_depth,
                                 qos_profile_sensor_data)

    def on_truth(self, msg):
        self.truth = msg.pose.pose

    def on_info(self, msg):
        if self.rays is not None:
            return
        fx, fy, cx, cy = msg.k[0], msg.k[4], msg.k[2], msg.k[5]
        u, v = np.meshgrid(np.arange(msg.width), np.arange(msg.height))
        self.rays = np.dstack([(u - cx) / fx, (v - cy) / fy, np.ones(u.shape)])

        # same view at 32 x 24
        sx, sy = WIDTH / msg.width, HEIGHT / msg.height
        self.info = CameraInfo(width=WIDTH, height=HEIGHT, distortion_model='plumb_bob',
                               d=[0.0] * 5, r=list(msg.r))
        k = [fx * sx, 0.0, (cx + 0.5) * sx - 0.5, 0.0, fy * sy, (cy + 0.5) * sy - 0.5, 0.0, 0.0, 1.0]
        self.info.k = k
        self.info.p = k[:3] + [0.0] + k[3:6] + [0.0] + k[6:] + [0.0]

    def on_depth(self, msg):
        if self.truth is None or self.rays is None:
            return
        try:
            t = self.tf.lookup_transform('base_footprint', msg.header.frame_id, rclpy.time.Time())
        except TransformException:
            return

        depth = self.bridge.imgmsg_to_cv2(msg, '32FC1')
        hit = np.isfinite(depth)
        points = self.rays * np.where(hit, depth, 0.0)[..., None]

        # camera -> base_footprint -> world, base_footprint pose from the Gazebo ground truth
        tr = t.transform.translation
        points = points @ rotation(t.transform.rotation).T + [tr.x, tr.y, tr.z]
        p = self.truth.position
        points = points @ rotation(self.truth.orientation).T + [p.x, p.y, p.z]

        temp = np.full(depth.shape, self.cfg['ambient'], dtype=np.float32)
        for patient in self.patients.values():
            c, s = math.cos(patient['yaw']), math.sin(patient['yaw'])
            dx, dy = points[..., 0] - patient['x'], points[..., 1] - patient['y']
            lx, ly = c * dx + s * dy, -s * dx + c * dy
            lz = points[..., 2] - patient['z']
            head_x = self.cfg['models'][patient['model']]['head'][0]
            body = hit & (lx > head_x - 0.1) & (lx < 1.0) & (np.abs(ly) < 0.4) & (lz > 0.65)
            head = hit & (np.linalg.norm(points - patient['head'], axis=2) < HEAD_RADIUS)
            temp[body] = self.cfg['clothing']
            temp[head] = patient['temperature'] - self.cfg['skin_offset']

        # each sensor pixel sees the average of its area
        small = cv2.resize(temp, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)
        small += np.random.normal(0.0, self.noise, small.shape).astype(np.float32)

        out = self.bridge.cv2_to_imgmsg(small, '32FC1')
        out.header = msg.header
        self.pub.publish(out)
        self.info.header = msg.header
        self.info_pub.publish(self.info)


def main():
    rclpy.init()
    node = FakeThermal()
    rclpy.spin(node)


if __name__ == '__main__':
    main()
