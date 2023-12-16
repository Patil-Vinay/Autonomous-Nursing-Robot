#!/usr/bin/env python3
"""Sends SCOBO to a bed from config/beds.yaml.

ros2 run scobo_navigation go_to_bed 3      one bed
ros2 run scobo_navigation go_to_bed all    beds 1 to 8, then home
ros2 run scobo_navigation go_to_bed home
In the sim add --ros-args -p use_sim_time:=true
"""
import math
import os
import sys
import time

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.srv import GetState
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.utilities import remove_ros_args


def load_poses():
    path = os.path.join(get_package_share_directory('scobo_navigation'), 'config', 'beds.yaml')
    with open(path) as f:
        data = yaml.safe_load(f)
    poses = {str(bed): pose for bed, pose in data['beds'].items()}
    poses['home'] = data['home']
    return poses, sorted(str(bed) for bed in data['beds'])


def to_pose_stamped(nav, pose):
    msg = PoseStamped()
    msg.header.frame_id = 'map'
    msg.header.stamp = nav.get_clock().now().to_msg()
    msg.pose.position.x = float(pose['x'])
    msg.pose.position.y = float(pose['y'])
    yaw = math.radians(pose['yaw'])
    msg.pose.orientation.z = math.sin(yaw / 2)
    msg.pose.orientation.w = math.cos(yaw / 2)
    return msg


def wait_for_nav2(nav):
    """Waits until bt_navigator is active, with a timeout on each get_state call."""
    nav.nav_to_pose_client.wait_for_server()
    client = nav.create_client(GetState, 'bt_navigator/get_state')
    for _ in range(30):
        future = client.call_async(GetState.Request())
        rclpy.spin_until_future_complete(nav, future, timeout_sec=2.0)
        if future.done() and future.result().current_state.label == 'active':
            break
        time.sleep(1.0)
    else:
        nav.warn('No answer from bt_navigator/get_state, going on')
    nav.destroy_client(client)


def drive(nav, name, pose):
    """Drives to one pose and returns True when Nav2 reports it reached."""
    label = 'home' if name == 'home' else f'bed {name}'
    nav.info(f'Going to {label}')
    nav.goToPose(to_pose_stamped(nav, pose))
    while not nav.isTaskComplete():
        rclpy.spin_once(nav, timeout_sec=0.5)
    result = nav.getResult()
    if result == TaskResult.SUCCEEDED:
        nav.info(f'Reached {label}')
        return True
    nav.error(f'Could not reach {label} ({result})')
    return False


def main():
    rclpy.init(args=sys.argv)
    args = remove_ros_args(sys.argv)[1:]
    poses, beds = load_poses()
    if len(args) != 1 or (args[0] != 'all' and args[0] not in poses):
        print(f'usage: go_to_bed <{"|".join(beds)}|home|all>')
        rclpy.shutdown()
        return 1
    targets = beds + ['home'] if args[0] == 'all' else [args[0]]

    nav = BasicNavigator()
    wait_for_nav2(nav)

    failed = [name for name in targets if not drive(nav, name, poses[name])]
    if len(targets) > 1:
        nav.info(f'Round done, {len(targets) - len(failed)} of {len(targets)} reached')
    nav.destroy_node()
    rclpy.shutdown()
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
