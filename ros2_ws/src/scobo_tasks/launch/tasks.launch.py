import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('scobo_tasks')
    display = os.path.join(get_package_share_directory('scobo_display'), 'launch', 'display.launch.py')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),

        # display page and rosbridge
        IncludeLaunchDescription(PythonLaunchDescriptionSource(display)),

        Node(
            package='scobo_tasks',
            executable='task_manager',
            parameters=[os.path.join(pkg, 'config', 'task_manager.yaml'),
                        {'use_sim_time': use_sim_time}],
            output='screen',
        ),
    ])
