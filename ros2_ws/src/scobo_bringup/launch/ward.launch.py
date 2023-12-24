import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def launch_file(package, name):
    return PythonLaunchDescriptionSource(
        os.path.join(get_package_share_directory(package), 'launch', name))


def generate_launch_description():
    # the robot on its rounds: drivers, Nav2 on the saved map, tasks, display and website link
    return LaunchDescription([
        DeclareLaunchArgument('map', default_value='/maps/ward.yaml'),
        DeclareLaunchArgument('site_url', default_value='http://localhost:8000',
                              description='The ward website'),
        DeclareLaunchArgument('token', default_value='dev-robot-token',
                              description='Must match SCOBO_ROBOT_TOKEN on the site'),

        IncludeLaunchDescription(launch_file('scobo_bringup', 'robot.launch.py')),
        IncludeLaunchDescription(
            launch_file('scobo_navigation', 'navigation.launch.py'),
            launch_arguments={'map': LaunchConfiguration('map'), 'rviz': 'false'}.items()),
        IncludeLaunchDescription(launch_file('scobo_tasks', 'tasks.launch.py')),
        IncludeLaunchDescription(
            launch_file('scobo_web', 'web.launch.py'),
            launch_arguments={'site_url': LaunchConfiguration('site_url'),
                              'token': LaunchConfiguration('token')}.items()),
    ])
