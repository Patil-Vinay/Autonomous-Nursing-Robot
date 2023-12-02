// Wheel odometry from the encoder angles in joint_states, two wheels per side.
// No TF, the EKF publishes odom -> base_footprint
#include <cmath>
#include <string>
#include <vector>

#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/joint_state.hpp"

class WheelOdometry : public rclcpp::Node
{
public:
  WheelOdometry()
  : Node("wheel_odometry")
  {
    left_joints_ = declare_parameter(
      "left_joints", std::vector<std::string>{"front_left_wheel_joint", "rear_left_wheel_joint"});
    right_joints_ = declare_parameter(
      "right_joints", std::vector<std::string>{"front_right_wheel_joint", "rear_right_wheel_joint"});
    wheel_radius_ = declare_parameter("wheel_radius", 0.0482);
    // effective track, larger than the real one because skid steer wheels slip in turns
    wheel_separation_ = declare_parameter("wheel_separation", 0.2838);
    odom_frame_ = declare_parameter("odom_frame", "odom");
    base_frame_ = declare_parameter("base_frame", "base_footprint");
    pose_covariance_ = declare_parameter(
      "pose_covariance_diagonal", std::vector<double>{0.001, 0.001, 1e6, 1e6, 1e6, 0.03});
    twist_covariance_ = declare_parameter(
      "twist_covariance_diagonal", std::vector<double>{0.001, 0.001, 1e6, 1e6, 1e6, 0.03});

    odom_pub_ = create_publisher<nav_msgs::msg::Odometry>("odom", 10);
    joint_sub_ = create_subscription<sensor_msgs::msg::JointState>(
      "joint_states", 10,
      [this](sensor_msgs::msg::JointState::ConstSharedPtr msg) {on_joints(*msg);});
  }

private:
  // mean angle of the named joints, false if one is missing
  static bool mean_angle(
    const sensor_msgs::msg::JointState & msg, const std::vector<std::string> & names,
    double & angle)
  {
    double sum = 0.0;
    for (const auto & name : names) {
      bool found = false;
      for (size_t i = 0; i < msg.name.size() && i < msg.position.size(); ++i) {
        if (msg.name[i] == name) {
          sum += msg.position[i];
          found = true;
          break;
        }
      }
      if (!found) {
        return false;
      }
    }
    angle = sum / names.size();
    return true;
  }

  void on_joints(const sensor_msgs::msg::JointState & msg)
  {
    // the pan-tilt states come on the same topic without the wheels
    double left, right;
    if (!mean_angle(msg, left_joints_, left) || !mean_angle(msg, right_joints_, right)) {
      return;
    }
    const rclcpp::Time stamp(msg.header.stamp, RCL_ROS_TIME);
    if (!started_) {
      last_left_ = left;
      last_right_ = right;
      last_stamp_ = stamp;
      started_ = true;
      return;
    }
    const double dt = (stamp - last_stamp_).seconds();
    if (dt <= 0.0) {
      return;
    }

    const double dl = (left - last_left_) * wheel_radius_;
    const double dr = (right - last_right_) * wheel_radius_;
    last_left_ = left;
    last_right_ = right;
    last_stamp_ = stamp;

    // second order Runge-Kutta, heading taken halfway through the step
    const double ds = (dl + dr) / 2.0;
    const double dyaw = (dr - dl) / wheel_separation_;
    const double mid = yaw_ + dyaw / 2.0;
    x_ += ds * std::cos(mid);
    y_ += ds * std::sin(mid);
    yaw_ += dyaw;

    nav_msgs::msg::Odometry odom;
    odom.header.stamp = msg.header.stamp;
    odom.header.frame_id = odom_frame_;
    odom.child_frame_id = base_frame_;
    odom.pose.pose.position.x = x_;
    odom.pose.pose.position.y = y_;
    odom.pose.pose.orientation.z = std::sin(yaw_ / 2.0);
    odom.pose.pose.orientation.w = std::cos(yaw_ / 2.0);
    odom.twist.twist.linear.x = ds / dt;
    odom.twist.twist.angular.z = dyaw / dt;
    for (size_t i = 0; i < 6; ++i) {
      odom.pose.covariance[i * 7] = pose_covariance_.at(i);
      odom.twist.covariance[i * 7] = twist_covariance_.at(i);
    }
    odom_pub_->publish(odom);
  }

  std::vector<std::string> left_joints_, right_joints_;
  double wheel_radius_, wheel_separation_;
  std::string odom_frame_, base_frame_;
  std::vector<double> pose_covariance_, twist_covariance_;

  bool started_{false};
  double last_left_{0.0}, last_right_{0.0};
  rclcpp::Time last_stamp_{0, 0, RCL_ROS_TIME};
  double x_{0.0}, y_{0.0}, yaw_{0.0};

  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_;
  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr joint_sub_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<WheelOdometry>());
  rclcpp::shutdown();
  return 0;
}
