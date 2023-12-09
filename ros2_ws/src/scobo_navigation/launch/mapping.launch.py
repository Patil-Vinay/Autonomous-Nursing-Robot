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

    slam = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        parameters=[LaunchConfiguration('slam_params_file'), {'use_sim_time': use_sim_time}],
        output='screen',
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', os.path.join(pkg, 'rviz', 'mapping.rviz')],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              description='true when running against Gazebo'),
        DeclareLaunchArgument('slam_params_file',
                              default_value=os.path.join(pkg, 'config', 'slam_toolbox.yaml')),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='false on the robot, run RViz on the PC instead'),
        slam,
        rviz,
    ])
