import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('scobo_navigation')
    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('params_file')

    map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        parameters=[params_file,
                    {'yaml_filename': LaunchConfiguration('map'), 'use_sim_time': use_sim_time}],
        output='screen',
    )

    amcl = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        parameters=[params_file, {'use_sim_time': use_sim_time}],
        output='screen',
    )

    # configures and activates the two lifecycle nodes above, in this order
    lifecycle = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        parameters=[{'node_names': ['map_server', 'amcl'], 'autostart': True,
                     'use_sim_time': use_sim_time}],
        output='screen',
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', os.path.join(pkg, 'rviz', 'navigation.rviz')],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              description='true when running against Gazebo'),
        DeclareLaunchArgument('map', default_value=os.path.join(pkg, 'maps', 'ward.yaml')),
        DeclareLaunchArgument('params_file',
                              default_value=os.path.join(pkg, 'config', 'nav2_params.yaml')),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='false on the robot, run RViz on the PC instead'),
        map_server,
        amcl,
        lifecycle,
        rviz,
    ])
