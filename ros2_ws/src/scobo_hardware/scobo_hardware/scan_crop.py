#!/usr/bin/env python3
"""Keeps the front of the RPLidar scan, the frame posts behind it block the rear."""
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class ScanCrop(Node):
    def __init__(self):
        super().__init__('scan_crop')
        # same 260 deg as the sim
        self.half_angle = math.radians(self.declare_parameter('half_angle', 130.0).value)
        self.pub = self.create_publisher(LaserScan, 'scan', qos_profile_sensor_data)
        self.create_subscription(LaserScan, 'scan_raw', self.on_scan, qos_profile_sensor_data)

    def on_scan(self, msg):
        if msg.angle_increment <= 0.0:
            return
        first = max(0, math.ceil((-self.half_angle - msg.angle_min) / msg.angle_increment))
        last = min(len(msg.ranges) - 1,
                   math.floor((self.half_angle - msg.angle_min) / msg.angle_increment))
        if last < first:
            return
        msg.angle_min += first * msg.angle_increment
        msg.angle_max = msg.angle_min + (last - first) * msg.angle_increment
        msg.ranges = msg.ranges[first:last + 1]
        if msg.intensities:
            msg.intensities = msg.intensities[first:last + 1]
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = ScanCrop()
    rclpy.spin(node)


if __name__ == '__main__':
    main()
