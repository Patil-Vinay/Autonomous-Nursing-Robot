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
        Node(package='scobo_web', executable='web_link', output='screen',
             parameters=[params, {'use_sim_time': use_sim_time}]),
        Node(package='scobo_web', executable='robot_pose', output='screen',
             parameters=[params, {'use_sim_time': use_sim_time}]),
    ])
