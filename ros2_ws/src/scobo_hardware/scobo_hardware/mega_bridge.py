#!/usr/bin/env python3
"""Link to the Mega 2560: wheels, pan-tilt, pill hoppers, BNO055, sonars and MAX30102.

Lines on the serial port look like $E 1200 10 12 -9 -11 0 0*5A, with the
NMEA checksum (XOR of the characters between $ and *).
"""
import math
import threading

import rclpy
import serial
from geometry_msgs.msg import Twist
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scobo_interfaces.msg import PulseOximeter
from scobo_interfaces.srv import Dispense
from sensor_msgs.msg import Imu, JointState, Range
from trajectory_msgs.msg import JointTrajectory

WHEELS = ['front_left_wheel_joint', 'rear_left_wheel_joint',
          'front_right_wheel_joint', 'rear_right_wheel_joint']
PAN, TILT = 'display_pan_joint', 'display_tilt_joint'
SONARS = {'r': 'rear', 'f': 'front'}
STATUS = ['pan home switch', 'BNO055', 'MAX30102']
# one pill is a swing out and back, 0.7 s each way
SECONDS_PER_PILL = 1.4


def checksum(body):
    cs = 0
    for c in body.encode():
        cs ^= c
    return cs


def diagonal(stddev):
    v = stddev * stddev
    return [v, 0.0, 0.0, 0.0, v, 0.0, 0.0, 0.0, v]


class MegaBridge(Node):
    def __init__(self):
        super().__init__('mega_bridge')
        param = self.declare_parameter
        port = param('port', '/dev/ttyACM0').value
        baud = param('baud', 250000).value
        self.counts_per_rev = param('counts_per_rev', 1000.0).value
        self.wheel_radius = param('wheel_radius', 0.0482).value
        self.wheel_separation = param('wheel_separation', 0.2838).value
        self.stock = list(param('stock', [30, 30, 30]).value)
        # HC-SR04 cone and range
        self.sonar_fov = param('sonar_fov', math.radians(15.0)).value
        self.sonar_min = param('sonar_min', 0.02).value
        self.sonar_max = param('sonar_max', 4.0).value
        # BNO055 noise, same as the sim
        self.orientation_cov = diagonal(param('orientation_stddev', 0.02).value)
        self.gyro_cov = diagonal(param('gyro_stddev', 0.0017).value)
        self.accel_cov = diagonal(param('accel_stddev', 0.0104).value)

        # opening the port resets the Mega, it answers once it has homed the pan
        self.serial = serial.Serial(port, baud, timeout=0)
        self.lock = threading.Lock()
        self.buffer = b''
        self.ready = False
        self.status = None
        self.pan_tilt = {PAN: 0.0, TILT: 0.0}
        self.dispensed = None
        self.dispense_done = threading.Event()
        self.handlers = {'E': self.on_encoders, 'I': self.on_imu, 'R': self.on_range,
                         'X': self.on_pulse, 'S': self.on_status, 'D': self.on_dispensed}

        self.joint_pub = self.create_publisher(JointState, 'joint_states', 10)
        self.imu_pub = self.create_publisher(Imu, 'imu/data', qos_profile_sensor_data)
        self.range_pubs = {
            key: self.create_publisher(Range, 'range/' + side, qos_profile_sensor_data)
            for key, side in SONARS.items()}
        self.pulse_pub = self.create_publisher(PulseOximeter, 'pulse_oximeter', 10)
        self.create_subscription(Twist, 'cmd_vel', self.on_cmd_vel, 10)
        self.create_subscription(JointTrajectory, 'pan_tilt_controller/joint_trajectory',
                                 self.on_trajectory, 10)
        # waits for the Mega while the serial timer keeps running
        self.create_service(Dispense, 'dispense', self.on_dispense,
                            callback_group=ReentrantCallbackGroup())
        self.create_timer(0.01, self.poll)

    def send(self, body):
        if not self.ready:
            return False
        line = '$%s*%02X\n' % (body, checksum(body))
        with self.lock:
            self.serial.write(line.encode())
        return True

    def poll(self):
        try:
            self.buffer += self.serial.read(self.serial.in_waiting or 1)
        except serial.SerialException as e:
            self.get_logger().error(f'serial port: {e}', throttle_duration_sec=5.0)
            return
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            self.handle_line(line.strip().decode('ascii', 'ignore'))
        if len(self.buffer) > 256:
            self.buffer = b''

    def handle_line(self, line):
        if not line.startswith('$') or '*' not in line:
            return
        body, _, cs = line[1:].rpartition('*')
        try:
            if int(cs, 16) != checksum(body):
                return
        except ValueError:
            return
        if not self.ready:
            self.ready = True
            self.get_logger().info('Mega ready')

        fields = body.split()
        handler = self.handlers.get(fields[0]) if fields else None
        if handler is not None:
            try:
                handler(fields[1:])
            except (ValueError, IndexError):
                self.get_logger().warn(f'bad line from the Mega: {line}')

    def header(self, msg, frame):
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = frame
        return msg

    def on_encoders(self, values):
        counts = [int(v) for v in values[1:5]]
        msg = self.header(JointState(), '')
        msg.name = WHEELS + [PAN, TILT]
        wheels = [c * 2 * math.pi / self.counts_per_rev for c in counts]
        msg.position = wheels + [int(values[5]) / 1000.0, int(values[6]) / 1000.0]
        self.joint_pub.publish(msg)

    def on_imu(self, values):
        ax, ay, az, gx, gy, gz, qw, qx, qy, qz = [int(v) for v in values]
        msg = self.header(Imu(), 'imu_link')
        q = msg.orientation
        q.w, q.x, q.y, q.z = qw / 16384.0, qx / 16384.0, qy / 16384.0, qz / 16384.0
        w = msg.angular_velocity
        w.x, w.y, w.z = [math.radians(g / 16.0) for g in (gx, gy, gz)]
        a = msg.linear_acceleration
        a.x, a.y, a.z = ax / 100.0, ay / 100.0, az / 100.0
        msg.orientation_covariance = self.orientation_cov
        msg.angular_velocity_covariance = self.gyro_cov
        msg.linear_acceleration_covariance = self.accel_cov
        self.imu_pub.publish(msg)

    def on_range(self, values):
        side = SONARS[values[0]]
        msg = self.header(Range(), f'ultrasonic_{side}_link')
        msg.radiation_type = Range.ULTRASOUND
        msg.field_of_view = self.sonar_fov
        msg.min_range = self.sonar_min
        msg.max_range = self.sonar_max
        # no echo means nothing up to the range limit, as in the sim
        mm = int(values[1])
        msg.range = mm / 1000.0 if 0 < mm < self.sonar_max * 1000 else self.sonar_max
        self.range_pubs[values[0]].publish(msg)

    def on_pulse(self, values):
        finger, valid, heart_rate, spo2 = [int(v) for v in values]
        msg = self.header(PulseOximeter(), 'max30102_link')
        msg.finger_detected = bool(finger)
        msg.valid = bool(valid)
        msg.heart_rate = float(heart_rate)
        msg.spo2 = float(spo2)
        self.pulse_pub.publish(msg)

    def on_status(self, values):
        status = [int(v) for v in values[:3]]
        if status != self.status:
            self.status = status
            for ok, name in zip(status, STATUS):
                if not ok:
                    self.get_logger().warn(f'{name} not found')

    def on_dispensed(self, values):
        self.dispensed = (int(values[0]), int(values[1]))
        self.dispense_done.set()

    def on_cmd_vel(self, msg):
        # wheel speeds in counts per second, both wheels on a side the same
        k = self.counts_per_rev / (2 * math.pi * self.wheel_radius)
        turn = msg.angular.z * self.wheel_separation / 2
        left = round((msg.linear.x - turn) * k)
        right = round((msg.linear.x + turn) * k)
        self.send(f'V {left} {left} {right} {right}')

    def on_trajectory(self, msg):
        if not msg.points:
            return
        for name, position in zip(msg.joint_names, msg.points[-1].positions):
            if name in self.pan_tilt:
                self.pan_tilt[name] = position
        self.send('P %d %d' % (round(self.pan_tilt[PAN] * 1000), round(self.pan_tilt[TILT] * 1000)))

    def on_dispense(self, req, res):
        hopper, count = req.hopper, req.count
        if not 1 <= hopper <= len(self.stock) or count == 0:
            res.message = f'bad request: hopper {hopper}, count {count}'
        elif self.stock[hopper - 1] < count:
            res.message = f'hopper {hopper} has only {self.stock[hopper - 1]} pills'
        else:
            self.dispense_done.clear()
            if not self.send(f'D {hopper} {count}'):
                res.message = 'Mega not ready'
            elif not self.dispense_done.wait(count * SECONDS_PER_PILL + 3.0):
                res.message = f'no answer from the Mega for hopper {hopper}'
            elif self.dispensed != (hopper, count):
                res.message = f'hopper {hopper} is busy'
            else:
                self.stock[hopper - 1] -= count
                res.success = True
                res.message = f'{count} from hopper {hopper}, {self.stock[hopper - 1]} left'

        if res.success:
            self.get_logger().info(res.message)
        else:
            self.get_logger().warn(res.message)
        return res


def main():
    rclpy.init()
    node = MegaBridge()
    rclpy.spin(node, MultiThreadedExecutor())


if __name__ == '__main__':
    main()
