#!/usr/bin/env python3
"""Fake pill dispenser for the sim, one servo turn of seconds_per_pill per pill."""
import time

import rclpy
from rclpy.node import Node
from scobo_interfaces.srv import Dispense


class FakeDispenser(Node):
    def __init__(self):
        super().__init__('fake_dispenser')
        self.stock = list(self.declare_parameter('stock', [30, 30, 30]).value)
        self.seconds_per_pill = self.declare_parameter('seconds_per_pill', 2.0).value
        self.create_service(Dispense, 'dispense', self.on_dispense)

    def on_dispense(self, req, res):
        hopper, count = req.hopper, req.count
        if not 1 <= hopper <= len(self.stock) or count == 0:
            res.message = f'bad request: hopper {hopper}, count {count}'
        elif self.stock[hopper - 1] < count:
            res.message = f'hopper {hopper} has only {self.stock[hopper - 1]} pills'
        else:
            for _ in range(count):
                time.sleep(self.seconds_per_pill)
                self.stock[hopper - 1] -= 1
            res.success = True
            res.message = f'{count} from hopper {hopper}, {self.stock[hopper - 1]} left'

        if res.success:
            self.get_logger().info(res.message)
        else:
            self.get_logger().warn(res.message)
        return res


def main():
    rclpy.init()
    node = FakeDispenser()
    rclpy.spin(node)


if __name__ == '__main__':
    main()
