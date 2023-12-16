cmake_minimum_required(VERSION 3.8)
project(scobo_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/PulseOximeter.msg"
  "msg/DisplayPrompt.msg"
  "msg/DisplayResponse.msg"
  "msg/Bed.msg"
  "msg/Task.msg"
  "msg/WardPlan.msg"
  "msg/VisitRecord.msg"
  "srv/Dispense.srv"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
