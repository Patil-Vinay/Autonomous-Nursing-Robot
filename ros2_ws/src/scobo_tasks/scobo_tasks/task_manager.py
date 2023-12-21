"""SCOBO task manager.

Keeps the ward plan (ward/plan) and makes a trip to the beds when tasks are due.
Visits are published on ward/visits and stored in the SQLite file.

ros2 service call /ward/run_now std_srvs/srv/Trigger              checks every occupied bed now
ros2 service call /ward/go_to scobo_interfaces/srv/GoTo "{bed: 3}"  drives to bed 3 and waits there
ros2 service call /ward/stop std_srvs/srv/Trigger                 stops driving, ends the trip
"""
import math
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Thread

import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from geometry_msgs.msg import Pose, PoseArray, PoseStamped
from lifecycle_msgs.srv import GetState
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from scobo_interfaces.msg import (Bed, DisplayPrompt, DisplayResponse, PulseOximeter, Task,
                                  VisitRecord, WardPlan)
from scobo_interfaces.srv import Dispense, GoTo
from sensor_msgs.msg import Image
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener

from scobo_tasks.ward_db import TASK_FIELDS, WardDB

# kept for late subscribers
LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)


@dataclass
class Visit:
    """What to do at one bed during a trip."""
    bed: int
    tasks: list = field(default_factory=list)
    temperature: bool = False
    pulse_oximeter: bool = False
    # (hopper, count)
    pills: list = field(default_factory=list)


def load_poses():
    path = os.path.join(get_package_share_directory('scobo_navigation'), 'config', 'beds.yaml')
    with open(path) as f:
        data = yaml.safe_load(f)
    return {int(bed): pose for bed, pose in data['beds'].items()}, data['home']


def now_text():
    return datetime.now().isoformat(timespec='seconds')


class TaskManager(Node):
    def __init__(self):
        super().__init__('task_manager')
        param = self.declare_parameter
        self.window = timedelta(minutes=param('window_minutes', 15).value)
        self.late_limit = timedelta(minutes=param('late_limit_minutes', 60).value)
        self.pulse_timeout = param('pulse_timeout', 60.0).value
        self.collect_timeout = param('collect_timeout', 120.0).value
        self.thermal_frames = param('thermal_frames', 8).value
        self.hot_pixels = param('hot_pixels', 4).value
        self.skin_offset = param('skin_offset', 1.0).value
        self.min_skin = param('min_skin', 30.0).value
        self.route = list(param('route', [4, 3, 2, 1, 8, 7, 6, 5]).value)
        # metres from the goal that count as arrived
        self.arrive_tolerance = param('arrive_tolerance', 0.25).value
        database = os.path.expanduser(param('database', '~/.ros/scobo/ward.db').value)

        self.db = WardDB(database)
        self.beds, self.tasks = self.db.load_plan()
        self.poses, self.home = load_poses()
        # tasks timed before this are not reported as missed
        self.since = datetime.now()
        self.run_now = False
        self.next_check = 0.0
        # set by the web page: a bed to drive to (0 for home), or stop
        self.go_to = None
        self.stopped = False
        self.busy = False
        self.bridge = CvBridge()
        # readings are only collected while these are lists
        self.pulse = None
        self.thermal = None
        self.responses = {}
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, self)

        self.plan_pub = self.create_publisher(WardPlan, 'ward/current_plan', LATCHED)
        self.visit_pub = self.create_publisher(VisitRecord, 'ward/visits', 50)
        self.display_pub = self.create_publisher(DisplayPrompt, 'display/prompt', LATCHED)
        self.status_pub = self.create_publisher(String, 'ward/status', LATCHED)
        self.stops_pub = self.create_publisher(PoseArray, 'ward/bed_stops', LATCHED)
        self.dispense = self.create_client(Dispense, 'dispense')
        self.create_subscription(WardPlan, 'ward/plan', self.on_plan, 10)
        self.create_subscription(PulseOximeter, 'pulse_oximeter', self.on_pulse, 10)
        self.create_subscription(Image, 'thermal/image', self.on_thermal, qos_profile_sensor_data)
        self.create_subscription(DisplayResponse, 'display/response', self.on_response, 10)
        self.create_service(Trigger, 'ward/run_now', self.on_run_now)
        self.create_service(GoTo, 'ward/go_to', self.on_go_to)
        self.create_service(Trigger, 'ward/stop', self.on_stop)

        self.publish_plan()
        self.publish_stops()
        self.status('Ready')
        self.show('')
        self.get_logger().info(f'Database {database}, {len(self.beds)} beds, {len(self.tasks)} tasks')

        self.nav = BasicNavigator()
        self.wait_for_nav2()

    def wait_for_nav2(self):
        """Waits until bt_navigator is active, with a timeout on each get_state call."""
        self.nav.nav_to_pose_client.wait_for_server()
        client = self.create_client(GetState, 'bt_navigator/get_state')
        for _ in range(30):
            future = client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)
            if future.done() and future.result().current_state.label == 'active':
                self.get_logger().info('Nav2 is active')
                break
            time.sleep(1.0)
        else:
            self.get_logger().warn('No answer from bt_navigator/get_state, going on')
        self.destroy_client(client)

    # plan and inputs

    def on_plan(self, msg):
        tasks = []
        for t in msg.tasks:
            try:
                datetime.strptime(t.time, '%H:%M')
            except ValueError:
                self.get_logger().error(f'Task {t.id}: bad time "{t.time}", plan ignored')
                return
            tasks.append({k: getattr(t, k) for k in TASK_FIELDS})
        beds = {b.number: b.occupied for b in msg.beds}
        try:
            self.db.save_plan(beds, tasks)
        except Exception as e:
            self.get_logger().error(f'Plan not saved: {e}')
            return
        self.beds, self.tasks = beds, tasks
        self.since = datetime.now()
        self.publish_plan()
        self.get_logger().info(f'New plan: occupied beds {self.occupied()}, {len(tasks)} tasks')

    def publish_plan(self):
        msg = WardPlan()
        msg.beds = [Bed(number=n, occupied=o) for n, o in sorted(self.beds.items())]
        msg.tasks = [Task(**t) for t in self.tasks]
        self.plan_pub.publish(msg)

    def on_pulse(self, msg):
        if self.pulse is not None:
            self.pulse.append(msg)

    def on_thermal(self, msg):
        if self.thermal is not None:
            self.thermal.append(self.bridge.imgmsg_to_cv2(msg, '32FC1'))

    def on_response(self, msg):
        self.responses[msg.id] = msg.button

    def on_run_now(self, req, res):
        self.run_now = True
        res.success = True
        res.message = 'Checking every occupied bed'
        return res

    def publish_stops(self):
        """Bed stops 1 to 8 then home, for the map on the web page."""
        msg = PoseArray()
        msg.header.frame_id = 'map'
        for pose in [self.poses[n] for n in sorted(self.poses)] + [self.home]:
            p = Pose()
            p.position.x, p.position.y = float(pose['x']), float(pose['y'])
            yaw = math.radians(pose['yaw'])
            p.orientation.z, p.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
            msg.poses.append(p)
        self.stops_pub.publish(msg)

    def on_go_to(self, req, res):
        if self.busy:
            res.success, res.message = False, 'Busy: ' + self.state
        elif req.bed and req.bed not in self.poses:
            res.success, res.message = False, f'No stop for bed {req.bed}'
        else:
            self.go_to = req.bed
            res.success = True
            res.message = f'Going to bed {req.bed}' if req.bed else 'Going home'
        return res

    def on_stop(self, req, res):
        self.go_to = None
        if self.busy:
            self.stopped = True
            res.success, res.message = True, 'Stopping'
        else:
            res.success, res.message = False, 'Not moving'
        return res

    def occupied(self):
        return sorted(n for n, o in self.beds.items() if o)

    # scheduler

    def check(self):
        if self.go_to is not None:
            bed, self.go_to = self.go_to, None
            self.go(bed)
            return
        if not self.run_now and time.monotonic() < self.next_check:
            return
        self.next_check = time.monotonic() + 30.0
        visits = self.due_visits()
        if visits:
            self.trip(visits)

    def due_visits(self):
        now = datetime.now()
        visits = {}
        if self.run_now:
            self.run_now = False
            for bed in self.occupied():
                visits[bed] = Visit(bed, ['run_now'], True, True)

        due = []
        for task in self.tasks:
            day = now.date().isoformat() if task['daily'] else 'once'
            if self.db.is_done(task['id'], day):
                continue
            at = datetime.combine(now.date(), datetime.strptime(task['time'], '%H:%M').time())
            if at > now + self.window:
                continue
            if at < now - self.late_limit:
                # a daily task timed before the plan arrived simply waits for tomorrow
                if at >= self.since or not task['daily']:
                    self.report(task, day, 'missed')
                continue
            due.append((at, task, day))

        # leave early tasks for later unless something is due now
        if not visits and not any(at <= now for at, _, _ in due):
            return []
        for _, task, day in due:
            self.db.mark_done(task['id'], day)
            if task['bed'] and not self.beds.get(task['bed']):
                self.report(task, day, 'bed not occupied')
                continue
            for bed in [task['bed']] if task['bed'] else self.occupied():
                v = visits.setdefault(bed, Visit(bed))
                v.tasks.append(task['id'])
                v.temperature |= task['temperature']
                v.pulse_oximeter |= task['pulse_oximeter']
                if task['count']:
                    v.pills.append((task['hopper'], task['count']))

        order = [b for b in self.route if b in visits] + sorted(set(visits) - set(self.route))
        return [visits[b] for b in order]

    def report(self, task, day, status):
        self.db.mark_done(task['id'], day)
        self.save(VisitRecord(time=now_text(), bed=task['bed'], tasks=[task['id']], status=status))

    def go(self, bed):
        label = f'bed {bed}' if bed else 'home'
        self.busy, self.stopped = True, False
        self.status(f'Going to {label}')
        if self.drive(label, self.poses[bed] if bed else self.home):
            self.status(f'At {label}')
        else:
            self.status('Stopped' if self.stopped else f'Could not reach {label}')
        self.busy = False

    def trip(self, visits):
        trip = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.busy, self.stopped = True, False
        self.get_logger().info(f'Trip {trip} to beds {[v.bed for v in visits]}')
        for v in visits:
            if self.stopped:
                self.save(VisitRecord(time=now_text(), trip=trip, bed=v.bed, tasks=v.tasks,
                                      status='stopped by staff'))
                continue
            self.status(f'Visiting bed {v.bed}')
            self.save(self.visit(trip, v))
        self.show('')
        if self.stopped:
            self.status('Stopped')
        else:
            self.status('Going home')
            self.status('At home' if self.drive('home', self.home) else 'Could not reach home')
        self.busy = False
        self.get_logger().info(f'Trip {trip} done')

    # one bed

    def visit(self, trip, v):
        rec = VisitRecord(trip=trip, bed=v.bed, tasks=v.tasks)
        if v.bed not in self.poses or not self.drive(f'bed {v.bed}', self.poses[v.bed]):
            rec.time = now_text()
            rec.status = 'stopped by staff' if self.stopped else 'could not reach bed'
            return rec

        problems = []
        pid = f'{trip}-{v.bed}'
        reason = 'check-up' if v.temperature or v.pulse_oximeter else 'medicine'
        self.show(pid + '-hello', 'Hello', f'SCOBO is here for your {reason}.')
        self.pause(3.0)

        if v.pulse_oximeter:
            self.show(pid + '-pulse', 'Pulse check',
                      'Please place a finger on the sensor at the front left of the robot and keep still.')
            reading = self.read_pulse()
            if reading:
                rec.heart_rate, rec.spo2 = reading
            else:
                problems.append('no pulse reading')

        if v.temperature:
            self.show(pid + '-temperature', 'Temperature', 'Please look towards the robot for a moment.')
            reading = self.read_temperature()
            if reading:
                rec.temperature = reading
            else:
                problems.append('no temperature reading')

        if v.pills:
            self.show(pid + '-wait', 'Your medicine', 'Please wait, your medicine is coming.')
            rec.pills, error = self.give_pills(v.pills)
            if error:
                problems.append(error)
            if rec.pills:
                self.show(pid + '-collect', 'Your medicine',
                          'Please take the medicine from the bowl, then tap Collected.', ['Collected'])
                rec.collected = self.wait_for(lambda: pid + '-collect' in self.responses,
                                              self.collect_timeout)
                if not rec.collected:
                    problems.append('not collected')

        self.show(pid + '-bye', 'Thank you', 'Get well soon.')
        self.pause(2.0)
        self.show('')
        rec.time = now_text()
        rec.status = ', '.join(problems) or 'done'
        return rec

    def read_pulse(self):
        """Median heart rate and SpO2 of 5 steady readings, None after the timeout."""
        self.pulse = []
        ok = self.wait_for(lambda: sum(m.valid for m in self.pulse) >= 5, self.pulse_timeout)
        valid = [m for m in self.pulse if m.valid][:5]
        self.pulse = None
        if not ok:
            return None
        return (statistics.median(m.heart_rate for m in valid),
                statistics.median(m.spo2 for m in valid))

    def read_temperature(self):
        """Hottest pixels of the averaged frames plus the skin offset, None if no face is seen."""
        self.thermal = []
        self.wait_for(lambda: len(self.thermal) >= self.thermal_frames, 10.0)
        frames, self.thermal = self.thermal, None
        if not frames:
            return None
        image = np.mean(frames, axis=0)
        hottest = float(np.mean(np.sort(image, axis=None)[-self.hot_pixels:]))
        if hottest < self.min_skin:
            return None
        return round(hottest + self.skin_offset, 1)

    def give_pills(self, pills):
        """Returns the number of pills given and an error text, empty if all went well."""
        if not self.dispense.wait_for_service(timeout_sec=5.0):
            return 0, 'dispenser not available'
        given = 0
        for hopper, count in pills:
            future = self.dispense.call_async(Dispense.Request(hopper=hopper, count=count))
            self.wait_for(future.done, 10.0 + 5.0 * count)
            res = future.result() if future.done() else None
            if res is None or not res.success:
                return given, 'dispense failed: ' + (res.message if res else 'no answer')
            given += count
        return given, ''

    # helpers

    def drive(self, label, pose):
        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.nav.get_clock().now().to_msg()
        msg.pose.position.x = float(pose['x'])
        msg.pose.position.y = float(pose['y'])
        yaw = math.radians(pose['yaw'])
        msg.pose.orientation.z = math.sin(yaw / 2)
        msg.pose.orientation.w = math.cos(yaw / 2)

        # Nav2 can report success too early, so check the pose and send the goal again
        for _ in range(3):
            self.get_logger().info(f'Going to {label}')
            self.nav.goToPose(msg)
            while not self.nav.isTaskComplete():
                if self.stopped:
                    self.nav.cancelTask()
                    self.get_logger().info(f'Stopped on the way to {label}')
                    return False
                time.sleep(0.05)
            if self.nav.getResult() != TaskResult.SUCCEEDED:
                break
            off = self.distance_to(pose)
            if off is None or off <= self.arrive_tolerance:
                return True
            self.get_logger().warn(f'Nav2 says {label} is reached but the robot is {off:.2f} m away')
        self.get_logger().error(f'Could not reach {label}')
        return False

    def distance_to(self, pose):
        """Metres from the robot to a map pose, None if the transform is missing."""
        try:
            t = self.tf.lookup_transform('map', 'base_footprint', rclpy.time.Time())
        except TransformException:
            return None
        p = t.transform.translation
        return math.hypot(p.x - pose['x'], p.y - pose['y'])

    def wait_for(self, done, timeout):
        end = time.monotonic() + timeout
        while not done() and time.monotonic() < end:
            time.sleep(0.05)
        return done()

    def pause(self, seconds):
        self.wait_for(lambda: False, seconds)

    def status(self, text):
        self.state = text
        self.status_pub.publish(String(data=text))

    def show(self, prompt_id, title='', text='', buttons=()):
        self.display_pub.publish(DisplayPrompt(id=prompt_id, title=title, text=text, buttons=list(buttons)))

    def save(self, rec):
        self.db.add_visit(rec)
        self.visit_pub.publish(rec)
        self.get_logger().info(
            f'Bed {rec.bed}: {rec.status}; temperature {rec.temperature:.1f}, heart rate '
            f'{rec.heart_rate:.0f}, SpO2 {rec.spo2:.0f}, pills {rec.pills}, collected {rec.collected}')


def main():
    rclpy.init()
    manager = TaskManager()
    # callbacks on their own thread, so readings keep coming during a visit
    executor = SingleThreadedExecutor()
    executor.add_node(manager)
    Thread(target=executor.spin, daemon=True).start()
    try:
        while rclpy.ok():
            manager.check()
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
