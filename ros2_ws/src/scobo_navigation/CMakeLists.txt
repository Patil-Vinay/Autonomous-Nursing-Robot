cmake_minimum_required(VERSION 3.8)
project(scobo_navigation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

add_executable(gyro_bias src/gyro_bias.cpp)
ament_target_dependencies(gyro_bias geometry_msgs nav_msgs rclcpp sensor_msgs)

add_executable(wheel_odometry src/wheel_odometry.cpp)
ament_target_dependencies(wheel_odometry nav_msgs rclcpp sensor_msgs)

install(TARGETS gyro_bias wheel_odometry DESTINATION lib/${PROJECT_NAME})
install(PROGRAMS scripts/go_to_bed.py DESTINATION lib/${PROJECT_NAME} RENAME go_to_bed)

install(
  DIRECTORY config launch maps rviz
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
