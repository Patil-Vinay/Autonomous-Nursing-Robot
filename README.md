# Autonomous-Nursing-Robot

The project entails the development of an autonomous healthcare robot designed to revolutionize hospital patient care. This robot leverages advanced technologies, including Robotics Operating System (ROS), Lidar, and SLAM algorithms, to autonomously navigate medical facilities, monitor vital signs, dispense medication, and enable remote interaction between healthcare providers and patients. The robot's features include real-time patient parameter monitoring, precise localization, non-contact temperature assessment, and UV floor sanitization. The project aims to enhance the efficiency of healthcare processes, improve patient care, and promote the use of cutting-edge robotics in healthcare, ultimately benefiting both patients and healthcare providers.

## Features

The **autonomous hospital robot** is equipped with a range of capabilities to serve various tasks within the healthcare environment:

- **Autonomous Pill Dispensing:** The robot autonomously navigates to deliver pills to patients. When positioned in front of the patient's bed or the goal location, the pill dispenser's light will illuminate to indicate that a pill is ready for dispensing.

- **Health Parameter Monitoring:** The robot monitors patients' health parameters, which include:
  - Body Temperature: A thermal camera with a region of interest set to the forehead detects the patient's body temperature while they are in bed.
  - Heart Rate and Oxygen Levels: Patients can place their finger on a heart rate and pulse oximeter sensor, which detects their heart/pulse rate and oxygen levels in the body.

- **Sanitization:** The robot has a UV light sanitizer installed beneath it, which sanitizes the hospital floor as the robot moves around the hospital ward.

- **Navigation and Mapping:** The robot's motors activate during movement or directional changes. The hospital ward is mapped using a LIDAR sensor, and coordinates are stored for all the beds in the ward.

- **Communication Facilitation:** The robot features a display that can be adjusted in the pan-tilt direction to ensure optimal visibility during communication between doctors and patients.

These capabilities make the autonomous hospital robot a valuable asset in healthcare settings, enhancing patient care and the overall hospital environment.

## Images:

![](https://github.com/Patil-Vinay/Autonomous-Nursing-Robot/blob/main/3D%20Model/Robot.jpg) 

![](https://github.com/Patil-Vinay/Autonomous-Nursing-Robot/blob/main/3D%20Model/3D%20%20Model%20Image%202.png)


ROS Navigation: 

![](https://github.com/Patil-Vinay/Autonomous-Nursing-Robot/blob/main/Output/ROS%20Navigation.png)


Body Temperature Monitoring:

![](https://github.com/Patil-Vinay/Autonomous-Nursing-Robot/blob/main/Output/Body%20Temp.png)
