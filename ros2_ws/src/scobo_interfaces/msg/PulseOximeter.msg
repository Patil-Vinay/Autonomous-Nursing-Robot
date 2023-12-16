# MAX30102 reading, published about once a second
std_msgs/Header header

bool finger_detected
# true once heart_rate and spo2 come from a steady signal
bool valid
# beats per minute
float32 heart_rate
# percent
float32 spo2
