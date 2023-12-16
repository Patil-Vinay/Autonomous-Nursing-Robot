import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg = get_package_share_directory('scobo_display')
    web = os.path.join(pkg, 'web')
    rosbridge = os.path.join(get_package_share_directory('rosbridge_server'), 'launch',
                             'rosbridge_websocket_launch.xml')

    return LaunchDescription([
        DeclareLaunchArgument('http_port', default_value='8080',
                              description='Port of the display page'),

        # websocket link between the page and ROS, port 9090
        IncludeLaunchDescription(AnyLaunchDescriptionSource(rosbridge)),

        # the tablet opens http://<robot>:8080
        ExecuteProcess(
            cmd=['python3', os.path.join(pkg, 'scripts', 'display_server.py'),
                 LaunchConfiguration('http_port'), web],
            output='screen',
        ),
    ])
