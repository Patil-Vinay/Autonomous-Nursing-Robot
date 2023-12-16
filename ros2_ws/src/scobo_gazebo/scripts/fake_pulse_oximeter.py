#!/usr/bin/env python3
"""Fake MAX30102 for the sim.

After the robot stops at an occupied bed the finger goes on, and after warmup
seconds it publishes the readings from config/patients.yaml with some noise.
"""
import math
import random

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from scobo_interfaces.msg import PulseOximeter

from sim_patients import load_patients


class FakePulseOximeter(Node):
    def __init__(self):
        super().__init__('fake_pulse_oximeter')
        # seconds standing still before the finger goes on
        self.finger_delay = self.declare_parameter('finger_delay', 5.0).value
        # seconds of finger contact before the reading is steady
        self.warmup = self.declare_parameter('warmup', 6.0).value
        # the patient's head must be this close to the robot centre, metres
        self.reach = self.declare_parameter('reach', 1.6).value
        _, self.patients = load_patients(self)

        self.pose = None
        self.moving = True
        self.still_since = None
        self.pub = self.create_publisher(PulseOximeter, 'pulse_oximeter', 10)
        self.create_subscription(Odometry, 'ground_truth', self.on_truth, 10)
        self.create_timer(1.0, self.publish)

    def on_truth(self, msg):
        self.pose = msg.pose.pose.position
        v, w = msg.twist.twist.linear, msg.twist.twist.angular
        self.moving = math.hypot(v.x, v.y) > 0.02 or abs(w.z) > 0.05

    def patient_nearby(self):
        for patient in self.patients.values():
            hx, hy, _ = patient['head']
            if math.hypot(hx - self.pose.x, hy - self.pose.y) < self.reach:
                return patient
        return None

    def publish(self):
        if self.pose is None:
            return
        now = self.get_clock().now().nanoseconds * 1e-9
        patient = None if self.moving else self.patient_nearby()
        if patient is None:
            self.still_since = None
        elif self.still_since is None:
            self.still_since = now

        msg = PulseOximeter()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'max30102_link'
        contact = -1.0 if self.still_since is None else now - self.still_since - self.finger_delay
        msg.finger_detected = contact >= 0.0
        if contact >= self.warmup:
            msg.valid = True
            msg.heart_rate = float(round(patient['heart_rate'] + random.gauss(0.0, 1.5)))
            msg.spo2 = float(min(100, round(patient['spo2'] + random.gauss(0.0, 0.5))))
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = FakePulseOximeter()
    rclpy.spin(node)


if __name__ == '__main__':
    main()
