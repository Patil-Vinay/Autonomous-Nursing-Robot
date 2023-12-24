import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    bringup = os.path.join(get_package_share_directory('scobo_bringup'), 'launch')
    nav = os.path.join(get_package_share_directory('scobo_navigation'), 'launch')

    # drive the robot round the ward, then save the map into /maps
    return LaunchDescription([
        IncludeLaunchDescription(PythonLaunchDescriptionSource(
            os.path.join(bringup, 'robot.launch.py'))),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(nav, 'mapping.launch.py')),
            launch_arguments={'rviz': 'false'}.items()),
    ])
