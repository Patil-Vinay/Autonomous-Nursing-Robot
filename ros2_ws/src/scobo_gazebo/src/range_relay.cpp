// Republishes the simulated sonar with "no echo" as +inf (REP 117)
#include <limits>
#include <memory>
#include <utility>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/range.hpp"

class RangeRelay : public rclcpp::Node
{
public:
  RangeRelay()
  : Node("range_relay")
  {
    pub_ = create_publisher<sensor_msgs::msg::Range>("range", rclcpp::SensorDataQoS());
    sub_ = create_subscription<sensor_msgs::msg::Range>(
      "range_sim", rclcpp::SensorDataQoS(),
      [this](sensor_msgs::msg::Range::UniquePtr msg) {
        if (msg->range > msg->max_range) {
          msg->range = std::numeric_limits<float>::infinity();
        }
        pub_->publish(std::move(msg));
      });
  }

private:
  rclcpp::Publisher<sensor_msgs::msg::Range>::SharedPtr pub_;
  rclcpp::Subscription<sensor_msgs::msg::Range>::SharedPtr sub_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<RangeRelay>());
  rclcpp::shutdown();
  return 0;
}
