import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

# effective track, as in the sim. The wheels slip in turns, so it is wider than 0.2838 m
DRIVE = {'wheel_radius': 0.0482, 'wheel_separation': 0.3179}


def generate_launch_description():
    description = get_package_share_directory('scobo_description')
    hardware = os.path.join(get_package_share_directory('scobo_hardware'), 'config',
                            'hardware.yaml')
    nav = get_package_share_directory('scobo_navigation')
    xacro_file = os.path.join(description, 'urdf', 'scobo.urdf.xacro')
    robot_description = ParameterValue(Command(['xacro ', xacro_file]), value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description}],
    )

    # RPLidar A1, settings from rplidar_ros' rplidar_a1_launch.py
    lidar = Node(
        package='rplidar_ros',
        executable='rplidar_node',
        parameters=[{'serial_port': LaunchConfiguration('lidar_port'), 'serial_baudrate': 115200,
                     'frame_id': 'laser', 'angle_compensate': True,
                     'scan_mode': 'Sensitivity'}],
        remappings=[('scan', 'scan_raw')],
        output='screen',
    )

    scan_crop = Node(package='scobo_hardware', executable='scan_crop')

    # wheels, pan-tilt, hoppers, BNO055, sonars and MAX30102
    mega_bridge = Node(
        package='scobo_hardware',
        executable='mega_bridge',
        parameters=[hardware, DRIVE, {'port': LaunchConfiguration('mega_port')}],
        output='screen',
    )

    thermal = Node(
        package='scobo_hardware',
        executable='mlx90640',
        parameters=[hardware],
        output='screen',
    )

    wheel_odometry = Node(
        package='scobo_navigation',
        executable='wheel_odometry',
        parameters=[DRIVE],
    )

    gyro_bias = Node(package='scobo_navigation', executable='gyro_bias')

    ekf = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        parameters=[os.path.join(nav, 'config', 'ekf.yaml')],
    )

    return LaunchDescription([
        DeclareLaunchArgument('mega_port', default_value='/dev/ttyACM0'),
        DeclareLaunchArgument('lidar_port', default_value='/dev/ttyUSB0'),

        robot_state_publisher,
        lidar,
        scan_crop,
        mega_bridge,
        thermal,
        wheel_odometry,
        gyro_bias,
        ekf,
    ])
