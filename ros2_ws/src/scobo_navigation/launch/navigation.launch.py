import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('scobo_navigation')
    # replan only when the path is blocked, so the robot does not turn back and forth at goals
    bt_xml = os.path.join(get_package_share_directory('nav2_bt_navigator'), 'behavior_trees',
                          'navigate_w_recovery_and_replanning_only_if_path_becomes_invalid.xml')
    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('params_file')
    params = [params_file, {'use_sim_time': use_sim_time}]

    # map_server, amcl and RViz
    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg, 'launch', 'localization.launch.py')),
        launch_arguments={'use_sim_time': use_sim_time, 'map': LaunchConfiguration('map'),
                          'params_file': params_file, 'rviz': LaunchConfiguration('rviz')}.items(),
    )

    # controller -> cmd_vel_nav -> velocity smoother -> cmd_vel_smoothed
    # -> collision monitor -> cmd_vel -> wheels
    nav_nodes = [
        Node(package='nav2_controller', executable='controller_server', name='controller_server',
             output='screen', parameters=params, remappings=[('cmd_vel', 'cmd_vel_nav')]),
        Node(package='nav2_planner', executable='planner_server', name='planner_server',
             output='screen', parameters=params),
        # spin and back up go through the smoother and the collision monitor too
        Node(package='nav2_behaviors', executable='behavior_server', name='behavior_server',
             output='screen', parameters=params, remappings=[('cmd_vel', 'cmd_vel_nav')]),
        Node(package='nav2_bt_navigator', executable='bt_navigator', name='bt_navigator',
             output='screen', parameters=params + [{'default_nav_to_pose_bt_xml': bt_xml}]),
        Node(package='nav2_velocity_smoother', executable='velocity_smoother',
             name='velocity_smoother', output='screen', parameters=params,
             remappings=[('cmd_vel', 'cmd_vel_nav')]),
        Node(package='nav2_collision_monitor', executable='collision_monitor',
             name='collision_monitor', output='screen', parameters=params),
    ]

    lifecycle = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        parameters=[{'node_names': ['controller_server', 'planner_server', 'behavior_server',
                                    'bt_navigator', 'velocity_smoother', 'collision_monitor'],
                     'autostart': True, 'use_sim_time': use_sim_time}],
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              description='true when running against Gazebo'),
        DeclareLaunchArgument('map', default_value=os.path.join(pkg, 'maps', 'ward.yaml')),
        DeclareLaunchArgument('params_file',
                              default_value=os.path.join(pkg, 'config', 'nav2_params.yaml')),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='false on the robot, run RViz on the PC instead'),
        localization,
        *nav_nodes,
        lifecycle,
    ])
