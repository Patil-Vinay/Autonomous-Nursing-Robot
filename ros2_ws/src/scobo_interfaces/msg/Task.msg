# One job from the ward plan
string id
# bed 1 to 8, 0 for every occupied bed (a round)
uint8 bed
# local time of day, HH:MM
string time
# true repeats every day, false runs once today
bool daily
bool temperature
bool pulse_oximeter
# pills from one hopper (1 to 3), count 0 for none
uint8 hopper
uint8 count
