import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    params = os.path.join(get_package_share_directory('scobo_web'), 'config', 'web_link.yaml')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('site_url', default_value='http://localhost:8000',
                              description='The ward website'),
        DeclareLaunchArgument('token', default_value='dev-robot-token',
                              description='Must match SCOBO_ROBOT_TOKEN on the site'),
        Node(package='scobo_web', executable='web_link', output='screen',
             parameters=[params, {'site_url': LaunchConfiguration('site_url'),
                                  'token': LaunchConfiguration('token'),
                                  'use_sim_time': use_sim_time}]),
        Node(package='scobo_web', executable='robot_pose', output='screen',
             parameters=[params, {'use_sim_time': use_sim_time}]),
    ])
