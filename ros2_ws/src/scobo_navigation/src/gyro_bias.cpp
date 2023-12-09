// Learns the gyro bias while the wheels say the robot is standing still
// and removes it before the IMU reaches the EKF
#include <algorithm>
#include <cmath>
#include <memory>
#include <utility>

#include "geometry_msgs/msg/vector3_stamped.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"

class GyroBias : public rclcpp::Node
{
public:
  GyroBias()
  : Node("gyro_bias")
  {
    // below these the wheels count as stopped
    max_linear_ = declare_parameter("max_linear", 0.001);
    max_angular_ = declare_parameter("max_angular", 0.0001);
    // wait this long after stopping, so the robot has stopped rocking
    settle_time_ = declare_parameter("settle_time", 1.0);
    // averaging window in seconds
    time_constant_ = declare_parameter("time_constant", 10.0);

    imu_pub_ = create_publisher<sensor_msgs::msg::Imu>(
      "imu/data_corrected", rclcpp::SensorDataQoS());
    bias_pub_ = create_publisher<geometry_msgs::msg::Vector3Stamped>("~/bias", 10);

    odom_sub_ = create_subscription<nav_msgs::msg::Odometry>(
      "odom", 10,
      [this](nav_msgs::msg::Odometry::ConstSharedPtr msg) {on_odom(*msg);});
    imu_sub_ = create_subscription<sensor_msgs::msg::Imu>(
      "imu/data", rclcpp::SensorDataQoS(),
      [this](sensor_msgs::msg::Imu::UniquePtr msg) {on_imu(std::move(msg));});
  }

private:
  void on_odom(const nav_msgs::msg::Odometry & msg)
  {
    const auto & v = msg.twist.twist;
    const bool still = std::abs(v.linear.x) < max_linear_ && std::abs(v.angular.z) < max_angular_;
    last_odom_ = now();
    if (still && !still_) {
      still_since_ = last_odom_;
    }
    still_ = still;
  }

  void on_imu(sensor_msgs::msg::Imu::UniquePtr msg)
  {
    const rclcpp::Time stamp(msg->header.stamp, RCL_ROS_TIME);
    const rclcpp::Time t = now();
    const bool odom_fresh = (t - last_odom_).seconds() < 0.5;

    if (still_ && odom_fresh && (t - still_since_).seconds() > settle_time_) {
      double dt = (stamp - last_imu_).seconds();
      if (dt <= 0.0 || dt > 0.5) {
        dt = 0.01;
      }
      // plain mean over the first samples, then a moving average that follows slow drift
      ++samples_;
      const double a = std::max(1.0 / samples_, dt / time_constant_);
      bias_x_ += a * (msg->angular_velocity.x - bias_x_);
      bias_y_ += a * (msg->angular_velocity.y - bias_y_);
      bias_z_ += a * (msg->angular_velocity.z - bias_z_);

      geometry_msgs::msg::Vector3Stamped bias;
      bias.header = msg->header;
      bias.vector.x = bias_x_;
      bias.vector.y = bias_y_;
      bias.vector.z = bias_z_;
      bias_pub_->publish(bias);
    }
    last_imu_ = stamp;

    msg->angular_velocity.x -= bias_x_;
    msg->angular_velocity.y -= bias_y_;
    msg->angular_velocity.z -= bias_z_;
    imu_pub_->publish(std::move(msg));
  }

  double max_linear_, max_angular_, settle_time_, time_constant_;
  bool still_ = false;
  rclcpp::Time still_since_{0, 0, RCL_ROS_TIME};
  rclcpp::Time last_odom_{0, 0, RCL_ROS_TIME};
  rclcpp::Time last_imu_{0, 0, RCL_ROS_TIME};
  long samples_ = 0;
  double bias_x_ = 0.0, bias_y_ = 0.0, bias_z_ = 0.0;

  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_pub_;
  rclcpp::Publisher<geometry_msgs::msg::Vector3Stamped>::SharedPtr bias_pub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<GyroBias>());
  rclcpp::shutdown();
  return 0;
}
