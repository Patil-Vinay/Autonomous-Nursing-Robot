"""Sends a ward plan from a YAML file.

ros2 run scobo_tasks send_plan               config/ward_plan.yaml
ros2 run scobo_tasks send_plan my_plan.yaml
"""
import os
import sys
import time
from datetime import datetime

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.utilities import remove_ros_args
from scobo_interfaces.msg import Bed, Task, WardPlan


def read_plan(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    msg = WardPlan()
    for number, status in sorted(data['beds'].items()):
        if status not in ('occupied', 'discharged'):
            raise ValueError(f'bed {number}: status must be occupied or discharged')
        msg.beds.append(Bed(number=int(number), occupied=status == 'occupied'))

    ids = set()
    for t in data.get('tasks') or []:
        if t['id'] in ids:
            raise ValueError(f'task id {t["id"]} is used twice')
        ids.add(t['id'])
        # quoted in the yaml, unquoted 08:00 is read as a number
        datetime.strptime(str(t['time']), '%H:%M')
        msg.tasks.append(Task(
            id=t['id'], bed=int(t.get('bed', 0)), time=t['time'], daily=bool(t.get('daily', False)),
            temperature=bool(t.get('temperature', False)),
            pulse_oximeter=bool(t.get('pulse_oximeter', False)),
            hopper=int(t.get('hopper', 0)), count=int(t.get('count', 0))))
    return msg


def main():
    rclpy.init(args=sys.argv)
    args = remove_ros_args(sys.argv)[1:]
    path = args[0] if args else os.path.join(
        get_package_share_directory('scobo_tasks'), 'config', 'ward_plan.yaml')
    try:
        msg = read_plan(path)
    except (OSError, KeyError, ValueError) as e:
        print(f'{path}: {e}')
        return 1

    node = rclpy.create_node('send_plan')
    pub = node.create_publisher(WardPlan, 'ward/plan', 10)
    end = time.time() + 10.0
    while pub.get_subscription_count() == 0 and time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.2)
    if pub.get_subscription_count() == 0:
        print('No task manager is listening on ward/plan')
        return 1

    pub.publish(msg)
    rclpy.spin_once(node, timeout_sec=0.5)
    print(f'Sent {len(msg.beds)} beds and {len(msg.tasks)} tasks from {path}')
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
