# One bed visit, or a task that could not be done
# local date and time, ISO 8601
string time
string trip
uint8 bed
# ids of the tasks handled in this visit
string[] tasks
# readings are 0 when not measured. deg C, beats per minute, percent
float32 temperature
float32 heart_rate
float32 spo2
uint8 pills
bool collected
# "done", or what went wrong, comma separated
string status
