cmake_minimum_required(VERSION 3.8)
project(scobo_gazebo)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

add_executable(range_relay src/range_relay.cpp)
ament_target_dependencies(range_relay rclcpp sensor_msgs)

install(TARGETS range_relay DESTINATION lib/${PROJECT_NAME})

# fake sensors and dispenser for the sim
install(PROGRAMS scripts/fake_thermal.py DESTINATION lib/${PROJECT_NAME} RENAME fake_thermal)
install(PROGRAMS scripts/fake_pulse_oximeter.py DESTINATION lib/${PROJECT_NAME} RENAME fake_pulse_oximeter)
install(PROGRAMS scripts/fake_dispenser.py DESTINATION lib/${PROJECT_NAME} RENAME fake_dispenser)
install(FILES scripts/sim_patients.py DESTINATION lib/${PROJECT_NAME})

install(
  DIRECTORY config launch models rviz urdf worlds
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
