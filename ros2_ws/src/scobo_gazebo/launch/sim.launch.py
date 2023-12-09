import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription, RegisterEventHandler,
                            SetEnvironmentVariable)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('scobo_gazebo')
    gazebo_ros = get_package_share_directory('gazebo_ros')
    nav = get_package_share_directory('scobo_navigation')
    xacro_file = os.path.join(pkg, 'urdf', 'scobo_sim.urdf.xacro')

    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')
    rviz = LaunchConfiguration('rviz')
    robot_description = ParameterValue(Command(['xacro ', xacro_file]), value_type=str)

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(gazebo_ros, 'launch', 'gazebo.launch.py')),
        launch_arguments={'world': world, 'gui': gui,
                          'params_file': os.path.join(pkg, 'config', 'gazebo.yaml')}.items(),
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description, 'use_sim_time': True}],
    )

    # start at home
    spawn = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=['-topic', 'robot_description', '-entity', 'scobo',
                   '-x', LaunchConfiguration('x'), '-y', LaunchConfiguration('y'),
                   '-z', '0.01', '-Y', LaunchConfiguration('yaw')],
        output='screen',
    )

    controllers = [
        Node(
            package='controller_manager',
            executable='spawner',
            arguments=[name, '--controller-manager', '/controller_manager'],
        )
        for name in ['joint_state_broadcaster', 'pan_tilt_controller']
    ]

    ekf = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        parameters=[os.path.join(nav, 'config', 'ekf.yaml'), {'use_sim_time': True}],
    )

    # same values as the diff drive plugin
    wheel_odometry = Node(
        package='scobo_navigation',
        executable='wheel_odometry',
        parameters=[{'wheel_radius': 0.0482, 'wheel_separation': 0.3179, 'use_sim_time': True}],
    )

    gyro_bias = Node(
        package='scobo_navigation',
        executable='gyro_bias',
        parameters=[{'use_sim_time': True}],
    )

    range_relays = [
        Node(
            package='scobo_gazebo',
            executable='range_relay',
            name=f'range_relay_{side}',
            parameters=[{'use_sim_time': True}],
            remappings=[('range_sim', f'range/{side}_sim'), ('range', f'range/{side}')],
        )
        for side in ['rear', 'front']
    ]

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', os.path.join(pkg, 'rviz', 'sim.rviz')],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(rviz),
    )

    return LaunchDescription([
        SetEnvironmentVariable('GAZEBO_MODEL_DATABASE_URI', ''),

        DeclareLaunchArgument('world', default_value=os.path.join(pkg, 'worlds', 'ward.world')),
        DeclareLaunchArgument('gui', default_value='true', description='Open the Gazebo client'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('x', default_value='8.4'),
        DeclareLaunchArgument('y', default_value='-0.5'),
        DeclareLaunchArgument('yaw', default_value='3.1416'),

        gazebo,
        robot_state_publisher,
        spawn,
        RegisterEventHandler(OnProcessExit(target_action=spawn, on_exit=controllers)),
        wheel_odometry,
        gyro_bias,
        ekf,
        *range_relays,
        rviz_node,
    ])
