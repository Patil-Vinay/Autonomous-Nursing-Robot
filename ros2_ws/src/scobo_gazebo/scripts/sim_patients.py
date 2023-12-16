"""Simulated patients for the fake sensors: config/patients.yaml plus their poses from Gazebo."""
import math
import os

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from gazebo_msgs.srv import GetEntityState


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def load_patients(node):
    """Returns the yaml settings and {bed: patient} with the world pose and head centre."""
    path = os.path.join(get_package_share_directory('scobo_gazebo'), 'config', 'patients.yaml')
    with open(path) as f:
        cfg = yaml.safe_load(f)

    client = node.create_client(GetEntityState, '/gazebo/get_entity_state')
    while not client.wait_for_service(timeout_sec=2.0):
        node.get_logger().info('Waiting for /gazebo/get_entity_state')

    patients = {}
    for bed, p in cfg['patients'].items():
        future = client.call_async(GetEntityState.Request(name=f'patient_{bed}', reference_frame='world'))
        rclpy.spin_until_future_complete(node, future)
        res = future.result()
        if not res.success:
            node.get_logger().warn(f'patient_{bed} is not in the world, skipped')
            continue
        pos = res.state.pose.position
        yaw = yaw_of(res.state.pose.orientation)
        hx, hy, hz = cfg['models'][p['model']]['head']
        c, s = math.cos(yaw), math.sin(yaw)
        head = (pos.x + c * hx - s * hy, pos.y + s * hx + c * hy, pos.z + hz)
        patients[bed] = dict(p, x=pos.x, y=pos.y, z=pos.z, yaw=yaw, head=head)
    node.get_logger().info(f'Patients in beds {sorted(patients)}')
    return cfg, patients
