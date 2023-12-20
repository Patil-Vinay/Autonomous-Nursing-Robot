"""Link between the robot and the ward website, over HTTP.

Pulls the ward plan from the site into ward/plan and sends the site the new visit
rows of the task manager's SQLite file.
"""
import json
import os
import sqlite3
import urllib.error
import urllib.request

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from scobo_interfaces.msg import Bed, Task, WardPlan

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)

TASK_FIELDS = ['id', 'bed', 'time', 'daily', 'temperature', 'pulse_oximeter', 'hopper', 'count']
VISIT_FIELDS = ['id', 'time', 'trip', 'bed', 'tasks', 'temperature', 'heart_rate', 'spo2',
                'pills', 'collected', 'status']


def plan_msg(data):
    """WardPlan from the site's JSON. Bad data raises an error."""
    msg = WardPlan()
    msg.beds = [Bed(number=b['number'], occupied=b['occupied']) for b in data['beds']]
    msg.tasks = [Task(**{k: t[k] for k in TASK_FIELDS}) for t in data['tasks']]
    return msg


def plan_key(msg):
    """The plan as sorted tuples, so two plans compare equal whatever their order."""
    beds = sorted((b.number, b.occupied) for b in msg.beds)
    tasks = sorted(tuple(getattr(t, k) for k in TASK_FIELDS) for t in msg.tasks)
    return beds, tasks


class WebLink(Node):
    def __init__(self):
        super().__init__('web_link')
        param = self.declare_parameter
        self.site = param('site_url', 'http://localhost:8000').value.rstrip('/')
        self.token = param('token', 'dev-robot-token').value
        self.database = os.path.expanduser(param('database', '~/.ros/scobo/ward.db').value)
        self.timeout = param('timeout', 5.0).value
        self.batch = param('batch', 100).value

        # plan the task manager holds, and the last one sent to it
        self.current = None
        self.sent = None
        self.online = None

        self.plan_pub = self.create_publisher(WardPlan, 'ward/plan', 10)
        self.create_subscription(WardPlan, 'ward/current_plan', self.on_current, LATCHED)
        self.create_timer(param('plan_period', 5.0).value, self.pull_plan)
        self.create_timer(param('visit_period', 10.0).value, self.push_visits)
        self.get_logger().info(f'Site {self.site}, database {self.database}')

    def on_current(self, msg):
        self.current = plan_key(msg)
        # a different plan here means the task manager restarted, send the plan again
        if self.current != self.sent:
            self.sent = None

    def pull_plan(self):
        # without a task manager there is nobody to send the plan to
        if self.current is None:
            return
        data = self.request('GET', '/api/plan/')
        if data is None:
            return
        try:
            msg = plan_msg(data)
        except (KeyError, TypeError, ValueError, AssertionError) as e:
            self.get_logger().error(f'Bad plan from the site: {e!r}')
            return
        key = plan_key(msg)
        # a plan the task manager turned down is not sent again until the site changes it
        if key != self.current and key != self.sent:
            self.plan_pub.publish(msg)
            self.sent = key
            occupied = [b.number for b in msg.beds if b.occupied]
            self.get_logger().info(f'Plan sent: occupied beds {occupied}, {len(msg.tasks)} tasks')

    def push_visits(self):
        answer = self.request('GET', '/api/visits/')
        if answer is None:
            return
        try:
            rows = self.new_rows(int(answer['last']))
        except (KeyError, TypeError, ValueError, sqlite3.Error) as e:
            self.get_logger().warn(f'Could not read the visits: {e!r}')
            return
        if not rows:
            return
        answer = self.request('POST', '/api/visits/', {'visits': rows})
        if answer is not None:
            self.get_logger().info(f'Sent visits {rows[0]["id"]} to {rows[-1]["id"]}, '
                                   f'{answer.get("stored")} new on the site')

    def new_rows(self, last):
        # read only, the task manager is the one that writes
        db = sqlite3.connect(f'file:{self.database}?mode=ro', uri=True, timeout=2.0)
        try:
            cur = db.execute(f'SELECT {", ".join(VISIT_FIELDS)} FROM visits WHERE id > ?'
                             ' ORDER BY id LIMIT ?', (last, self.batch))
            rows = [dict(zip(VISIT_FIELDS, r)) for r in cur]
        finally:
            db.close()
        for r in rows:
            r['tasks'] = r['tasks'].split(',') if r['tasks'] else []
            r['collected'] = bool(r['collected'])
        return rows

    def request(self, method, path, data=None):
        """The JSON answer, None if the site could not be reached or said no."""
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.site + path, data=body, method=method, headers={
            'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                answer = json.load(res)
        except urllib.error.HTTPError as e:
            self.set_online(False, f'{method} {path}: HTTP {e.code}')
            return None
        except (OSError, ValueError) as e:
            self.set_online(False, f'{method} {path}: {e}')
            return None
        self.set_online(True)
        return answer

    def set_online(self, online, reason=''):
        # logged only when it changes, the site is asked every few seconds
        if online != self.online:
            if online:
                self.get_logger().info('Site reachable')
            else:
                self.get_logger().warn(f'Site not reachable: {reason}')
        self.online = online


def main():
    rclpy.init()
    node = WebLink()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
