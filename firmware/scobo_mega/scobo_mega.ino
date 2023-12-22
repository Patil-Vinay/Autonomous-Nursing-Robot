// SCOBO Mega 2560: wheels, pan-tilt, pill hoppers and the sensors wired to the Mega.
// Talks to the Jetson over USB in lines like $V 800 800 800 800*1C
#include <AccelStepper.h>
#include <MAX30105.h>
#include <Servo.h>
#include <Wire.h>
#include <spo2_algorithm.h>
#include <stdarg.h>

// wheels in the order FL, RL, FR, RR
const uint8_t MOTOR_PWM[4] = {5, 6, 7, 8};
const uint8_t MOTOR_DIR[4] = {22, 23, 24, 25};
const uint8_t ENC_A[4] = {2, 3, 18, 19};
const uint8_t ENC_B[4] = {26, 27, 28, 29};
// the right side motors face the other way
const bool MOTOR_INVERT[4] = {false, false, true, true};
const bool ENC_INVERT[4] = {false, false, true, true};

const uint8_t TILT_PIN[2] = {9, 10};  // left, right
const uint8_t HOPPER_PIN[3] = {11, 12, 44};
const uint8_t PAN_STEP = 30, PAN_DIR = 31, PAN_EN = 32, PAN_HOME = 33;
const uint8_t SONAR_TRIG[2] = {34, 36};  // rear, front, echoes on A8 and A9
const uint8_t BNO_ADDR = 0x28;

// wheel speed loop, speeds in encoder counts per second
const float FULL_SPEED = 3000.0;  // counts/s at full PWM, measure on the robot
const float KP = 0.05, KI = 0.5;
const unsigned long CMD_TIMEOUT = 500;  // ms without a V line stops the wheels

// pan stepper: 200 steps, 1/16 microstepping, direct drive
const float PAN_STEPS_PER_RAD = 200 * 16 / (2 * PI);
const float PAN_SPEED = 1.0, PAN_ACCEL = 2.0, PAN_HOME_SPEED = 0.3;  // rad/s, rad/s^2
const long PAN_HOME_MRAD = -1650;  // pan angle where the home switch closes
const long PAN_LIMIT = 1571, TILT_LIMIT = 785;  // mrad, same as the URDF

// MG995 tilt servos, they face each other
const int TILT_CENTER_US[2] = {1500, 1500};
const int TILT_SIGN[2] = {1, -1};
const float TILT_US_PER_RAD = 573.0;  // about 10 us per degree
const float TILT_SPEED = 1.0;  // rad/s

const int HOPPER_REST_US = 1000, HOPPER_DROP_US = 2000;
const unsigned long HOPPER_MOVE_MS = 700;

const uint32_t FINGER_IR = 50000;  // IR level with a finger on the sensor

volatile long encCount[4];
long lastCount[4];
float measured[4], integral[4];
long target[4];
unsigned long lastCmd;

AccelStepper pan(AccelStepper::DRIVER, PAN_STEP, PAN_DIR);
bool panHomed = false;
Servo tilt[2];
float tiltNow = 0;
long tiltTarget = 0;

Servo hoppers[3];
int8_t hopper = -1;
uint8_t pillsTotal, pillsDone;
bool dropping;
unsigned long hopperTime;

volatile unsigned long echoStart[2], echoTime[2];
volatile bool echoDone[2];
volatile uint8_t lastPinK;
uint8_t sonar = 0;
unsigned long lastPing;

bool imuOk = false;

MAX30105 oximeter;
bool oxOk = false, finger = false, oxValid = false;
uint32_t irBuffer[100], redBuffer[100];
uint8_t samples = 0;
int32_t heartRate, spo2;
unsigned long lastOxCheck;

char rx[64];
uint8_t rxLen = 0;
bool rxOn = false;

unsigned long lastTick, lastStatus;

uint8_t checksum(const char *s)
{
  uint8_t cs = 0;
  while (*s) cs ^= *s++;
  return cs;
}

void send(const char *fmt, ...)
{
  char body[72];
  va_list args;
  va_start(args, fmt);
  vsnprintf(body, sizeof(body), fmt, args);
  va_end(args);
  uint8_t cs = checksum(body);
  Serial.print('$');
  Serial.print(body);
  Serial.print('*');
  if (cs < 0x10) Serial.print('0');
  Serial.println(cs, HEX);
}

// x2 quadrature, counts on both edges of A
void encoderStep(uint8_t i)
{
  encCount[i] += (digitalRead(ENC_A[i]) == digitalRead(ENC_B[i])) ? 1 : -1;
}
void enc0() { encoderStep(0); }
void enc1() { encoderStep(1); }
void enc2() { encoderStep(2); }
void enc3() { encoderStep(3); }

// HC-SR04 echo pulses on A8 (PK0) and A9 (PK1)
ISR(PCINT2_vect)
{
  uint8_t pins = PINK;
  uint8_t changed = pins ^ lastPinK;
  lastPinK = pins;
  unsigned long t = micros();
  for (uint8_t i = 0; i < 2; i++) {
    uint8_t bit = 1 << i;
    if (!(changed & bit)) continue;
    if (pins & bit) {
      echoStart[i] = t;
    } else {
      echoTime[i] = t - echoStart[i];
      echoDone[i] = true;
    }
  }
}

void setMotor(uint8_t i, float out)
{
  digitalWrite(MOTOR_DIR[i], (out < 0) != MOTOR_INVERT[i]);
  analogWrite(MOTOR_PWM[i], constrain((int)fabs(out), 0, 255));
}

void motorTick(unsigned long dtMs)
{
  long counts[4];
  noInterrupts();
  for (uint8_t i = 0; i < 4; i++) counts[i] = encCount[i];
  interrupts();

  if (millis() - lastCmd > CMD_TIMEOUT) {
    for (uint8_t i = 0; i < 4; i++) target[i] = 0;
  }

  for (uint8_t i = 0; i < 4; i++) {
    if (ENC_INVERT[i]) counts[i] = -counts[i];
    float speed = (counts[i] - lastCount[i]) * 1000.0 / dtMs;
    lastCount[i] = counts[i];
    measured[i] = 0.5 * measured[i] + 0.5 * speed;

    float out = 0;
    if (target[i] == 0) {
      integral[i] = 0;
    } else {
      float err = target[i] - measured[i];
      integral[i] = constrain(integral[i] + err * dtMs / 1000.0, -255 / KI, 255 / KI);
      out = target[i] / FULL_SPEED * 255 + KP * err + KI * integral[i];
    }
    setMotor(i, out);
  }

  send("E %lu %ld %ld %ld %ld %ld %ld", millis(), counts[0], counts[1], counts[2], counts[3],
       panHomed ? lround(pan.currentPosition() * 1000.0 / PAN_STEPS_PER_RAD) : 0L,
       lround(tiltNow));
}

void tiltTick(unsigned long dtMs)
{
  float step = TILT_SPEED * dtMs;  // mrad
  tiltNow += constrain(tiltTarget - tiltNow, -step, step);
  for (uint8_t i = 0; i < 2; i++) {
    tilt[i].writeMicroseconds(TILT_CENTER_US[i] + TILT_SIGN[i] * tiltNow / 1000.0 * TILT_US_PER_RAD);
  }
}

uint8_t readReg(uint8_t reg)
{
  Wire.beginTransmission(BNO_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission() != 0 || Wire.requestFrom(BNO_ADDR, (uint8_t)1) != 1) return 0;
  return Wire.read();
}

void writeReg(uint8_t reg, uint8_t value)
{
  Wire.beginTransmission(BNO_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

bool imuBegin()
{
  // the BNO055 needs about 650 ms after power-on
  for (uint8_t i = 0; i < 10 && readReg(0x00) != 0xA0; i++) delay(100);
  if (readReg(0x00) != 0xA0) return false;
  writeReg(0x3D, 0x00);  // config mode
  delay(25);
  writeReg(0x07, 0x00);  // register page 0
  writeReg(0x3E, 0x00);  // normal power
  writeReg(0x3D, 0x08);  // IMU fusion, accel and gyro without the magnetometer
  delay(20);
  return true;
}

// raw BNO055 values: accel 1 m/s^2 = 100, gyro 1 dps = 16, quaternion 1 = 16384
void imuTick()
{
  if (!imuOk) return;
  Wire.beginTransmission(BNO_ADDR);
  Wire.write(0x08);
  if (Wire.endTransmission() != 0 || Wire.requestFrom(BNO_ADDR, (uint8_t)32) != 32) return;
  int16_t d[16];  // accel, mag, gyro, euler xyz, then quaternion wxyz
  for (uint8_t i = 0; i < 16; i++) {
    uint8_t lo = Wire.read();
    d[i] = (int16_t)(lo | (Wire.read() << 8));
  }
  send("I %d %d %d %d %d %d %d %d %d %d", d[0], d[1], d[2], d[6], d[7], d[8],
       d[12], d[13], d[14], d[15]);
}

// one sonar every 50 ms, so each runs at 10 Hz without hearing the other
void sonarTick(unsigned long now)
{
  if (now - lastPing < 50) return;
  lastPing = now;
  noInterrupts();
  bool done = echoDone[sonar];
  unsigned long us = echoTime[sonar];
  interrupts();
  // mm, 0 for no echo
  send("R %c %lu", sonar == 0 ? 'r' : 'f', done ? us * 343 / 2000 : 0UL);

  sonar = 1 - sonar;
  echoDone[sonar] = false;
  digitalWrite(SONAR_TRIG[sonar], HIGH);
  delayMicroseconds(10);
  digitalWrite(SONAR_TRIG[sonar], LOW);
}

bool homePan()
{
  digitalWrite(PAN_EN, LOW);
  pan.setCurrentPosition(0);
  pan.setMaxSpeed(PAN_HOME_SPEED * PAN_STEPS_PER_RAD);
  pan.setSpeed(PAN_HOME_SPEED * PAN_STEPS_PER_RAD * (PAN_HOME_MRAD < 0 ? -1 : 1));
  // a little more than the whole pan range
  long travel = 3.5 * PAN_STEPS_PER_RAD;
  while (digitalRead(PAN_HOME) == HIGH) {
    if (labs(pan.currentPosition()) > travel) {
      digitalWrite(PAN_EN, HIGH);
      return false;
    }
    pan.runSpeed();
  }
  pan.setCurrentPosition(lround(PAN_HOME_MRAD / 1000.0 * PAN_STEPS_PER_RAD));
  pan.setMaxSpeed(PAN_SPEED * PAN_STEPS_PER_RAD);
  pan.setAcceleration(PAN_ACCEL * PAN_STEPS_PER_RAD);
  pan.moveTo(0);
  return true;
}

void setPan(long mrad)
{
  if (panHomed) pan.moveTo(lround(constrain(mrad, -PAN_LIMIT, PAN_LIMIT) / 1000.0 * PAN_STEPS_PER_RAD));
}

void startDispense(long h, long count)
{
  if (hopper >= 0 || h < 1 || h > 3 || count < 1 || count > 255) {
    send("D %ld 0", h);
    return;
  }
  hopper = h - 1;
  pillsTotal = count;
  pillsDone = 0;
  dropping = true;
  hoppers[hopper].writeMicroseconds(HOPPER_DROP_US);
  hopperTime = millis();
}

// one pill per swing to the drop position and back
void hopperTick(unsigned long now)
{
  if (hopper < 0 || now - hopperTime < HOPPER_MOVE_MS) return;
  hopperTime = now;
  if (dropping) {
    hoppers[hopper].writeMicroseconds(HOPPER_REST_US);
    dropping = false;
    pillsDone++;
  } else if (pillsDone < pillsTotal) {
    hoppers[hopper].writeMicroseconds(HOPPER_DROP_US);
    dropping = true;
  } else {
    send("D %d %d", hopper + 1, pillsDone);
    hopper = -1;
  }
}

// 25 samples/s, a result from the last 4 s each time 1 s of new samples is in
void oximeterTick(unsigned long now)
{
  if (!oxOk || now - lastOxCheck < 10) return;
  lastOxCheck = now;
  oximeter.check();
  while (oximeter.available()) {
    uint32_t red = oximeter.getFIFORed();
    uint32_t ir = oximeter.getFIFOIR();
    oximeter.nextSample();
    if (ir < FINGER_IR) {
      finger = oxValid = false;
      samples = 0;
      continue;
    }
    finger = true;
    if (samples == 100) {
      memmove(irBuffer, irBuffer + 25, 75 * sizeof(uint32_t));
      memmove(redBuffer, redBuffer + 25, 75 * sizeof(uint32_t));
      samples = 75;
    }
    irBuffer[samples] = ir;
    redBuffer[samples] = red;
    if (++samples == 100) {
      int8_t spo2Ok, heartRateOk;
      maxim_heart_rate_and_oxygen_saturation(irBuffer, 100, redBuffer, &spo2, &spo2Ok,
                                             &heartRate, &heartRateOk);
      oxValid = spo2Ok && heartRateOk;
    }
  }
}

bool readArgs(long *v, uint8_t n)
{
  for (uint8_t i = 0; i < n; i++) {
    char *t = strtok(NULL, " ");
    if (!t) return false;
    v[i] = atol(t);
  }
  return true;
}

void handleLine(char *line)
{
  char *star = strrchr(line, '*');
  if (!star) return;
  *star = '\0';
  if (checksum(line) != strtol(star + 1, NULL, 16)) return;

  char *cmd = strtok(line, " ");
  long v[4];
  if (!cmd) return;
  if (!strcmp(cmd, "V") && readArgs(v, 4)) {
    for (uint8_t i = 0; i < 4; i++) target[i] = v[i];
    lastCmd = millis();
  } else if (!strcmp(cmd, "P") && readArgs(v, 2)) {
    setPan(v[0]);
    tiltTarget = constrain(v[1], -TILT_LIMIT, TILT_LIMIT);
  } else if (!strcmp(cmd, "D") && readArgs(v, 2)) {
    startDispense(v[0], v[1]);
  }
}

void readSerial()
{
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '$') {
      rxLen = 0;
      rxOn = true;
    } else if (!rxOn) {
      continue;
    } else if (c == '\n' || c == '\r') {
      rx[rxLen] = '\0';
      rxOn = false;
      handleLine(rx);
    } else if (rxLen < sizeof(rx) - 1) {
      rx[rxLen++] = c;
    } else {
      rxOn = false;
    }
  }
}

void setup()
{
  Serial.begin(250000);

  for (uint8_t i = 0; i < 4; i++) {
    pinMode(MOTOR_DIR[i], OUTPUT);
    pinMode(MOTOR_PWM[i], OUTPUT);
    pinMode(ENC_A[i], INPUT_PULLUP);
    pinMode(ENC_B[i], INPUT_PULLUP);
  }
  // timers 3 and 4 to 7.8 kHz fast PWM, the MDD10A takes up to 20 kHz
  TCCR3A = _BV(WGM30);
  TCCR3B = _BV(WGM32) | _BV(CS31);
  TCCR4A = _BV(WGM40);
  TCCR4B = _BV(WGM42) | _BV(CS41);
  for (uint8_t i = 0; i < 4; i++) setMotor(i, 0);
  attachInterrupt(digitalPinToInterrupt(ENC_A[0]), enc0, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_A[1]), enc1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_A[2]), enc2, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_A[3]), enc3, CHANGE);

  for (uint8_t i = 0; i < 2; i++) {
    tilt[i].attach(TILT_PIN[i]);
    tilt[i].writeMicroseconds(TILT_CENTER_US[i]);
  }
  for (uint8_t i = 0; i < 3; i++) {
    hoppers[i].attach(HOPPER_PIN[i]);
    hoppers[i].writeMicroseconds(HOPPER_REST_US);
  }

  for (uint8_t i = 0; i < 2; i++) {
    pinMode(SONAR_TRIG[i], OUTPUT);
    digitalWrite(SONAR_TRIG[i], LOW);
  }
  pinMode(A8, INPUT);
  pinMode(A9, INPUT);
  lastPinK = PINK;
  PCMSK2 |= _BV(PCINT16) | _BV(PCINT17);
  PCICR |= _BV(PCIE2);

  Wire.begin();
  Wire.setClock(400000);
  imuOk = imuBegin();
  oxOk = oximeter.begin(Wire, I2C_SPEED_FAST);
  if (oxOk) oximeter.setup(60, 4, 2, 100, 411, 4096);
  // a stuck bus must not freeze the wheel loop
  Wire.setWireTimeout(3000, true);

  pinMode(PAN_EN, OUTPUT);
  pinMode(PAN_HOME, INPUT_PULLUP);
  panHomed = homePan();

  lastTick = lastStatus = lastCmd = millis();
}

void loop()
{
  readSerial();
  pan.run();

  unsigned long now = millis();
  if (now - lastTick >= 20) {
    unsigned long dt = now - lastTick;
    lastTick = now;
    motorTick(dt);
    tiltTick(dt);
    imuTick();
  }
  sonarTick(now);
  hopperTick(now);
  oximeterTick(now);

  if (now - lastStatus >= 1000) {
    lastStatus = now;
    send("S %d %d %d %d", panHomed, imuOk, oxOk, imuOk ? readReg(0x35) : 0);
    send("X %d %d %ld %ld", finger, finger && oxValid, oxValid ? heartRate : 0L,
         oxValid ? spo2 : 0L);
  }
}
