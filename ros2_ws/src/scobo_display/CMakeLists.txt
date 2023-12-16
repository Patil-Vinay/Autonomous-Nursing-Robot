cmake_minimum_required(VERSION 3.8)
project(scobo_display)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch scripts web
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
