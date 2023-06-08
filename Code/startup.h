#pragma once

//______________________________________________________Random:
void generateRandomSeed()
{
  unsigned long number = millis();
  for(int i = 0; i < 25; i++)
  {
    number += analogRead(A0);
    number *= analogRead(A1);
    number /= analogRead(A2);
    delay(1);
  }
  randomSeed(number);
}


//______________________________________________________Signaling:
#define signalLedPin 47
#define signalBuzzerPin 11

void initSignaling()
{
  pinMode(signalLedPin, OUTPUT);
  pinMode(signalBuzzerPin, OUTPUT);
  digitalWrite(signalLedPin, LOW);
  digitalWrite(signalBuzzerPin, LOW);
}

//______________________________________________________Servo:
#define servoPin 7

int kitsDropped = 0;

Servo servo;

void initServo()
{
  servo.attach(servoPin);
  servo.write(90);
}

//______________________________________________________Motors:
#define motorBLid 2
#define motorFLid 3
#define motorFRid 5
#define motorBRid 9
#define motorIDs {motorBLid, motorBRid, motorFRid, motorFLid}

#define motorSpeedFast 300
#define motorSpeedSlow 100
#define motorTurnSpeedFast 200
#define motorTurnSpeedSlow 50

enum DriveDirection {LEFT, FORWARD, RIGHT, BACKWARD, STOP};
enum DriveSpeed {FAST, SLOW};

ServoCds55 motors;

void initMotors()
{
  motors.begin();
  const int IDs[4] = motorIDs;
  for(int i = 0; i < 4; i++)
  {
    motors.SetServoLimit(IDs[i],0);
  }
}

//______________________________________________________Cameras:
#define cameraPin0L 22
#define cameraPin1L 24
#define cameraPin2L 26
#define cameraPin0R 52
#define cameraPin1R 50
#define cameraPin2R 48
#define leftCameraPins {cameraPin0L, cameraPin1L, cameraPin2L}
#define rightCameraPins {cameraPin0R, cameraPin1R, cameraPin2R}
#define cameraPinsNum 3

#define victimTimeBuffer 10000
#define medKitsNum {0, 0, 1, 1, 2, 3, 0} //None, Green, Red, Yellow, S, H, U

unsigned long lastVictimTime = 0;

void initCameras()
{
  const int leftPins[cameraPinsNum] = leftCameraPins;
  const int rightPins[cameraPinsNum] = rightCameraPins;
  for(int i = 0; i < cameraPinsNum; i++)
  {
    pinMode(leftPins[i], INPUT);
    pinMode(rightPins[i], INPUT);
  }
}

//______________________________________________________Sensors:
#define portTofLB 5
#define portTofLF 7
#define portTofFL 6
#define portTofFR 1
#define portTofRF 0
#define portTofRB 2
#define numTOF 6
#define portsTOF {portTofLB, portTofLF, portTofFL, portTofFR, portTofRF, portTofRB}
#define portGyro 3
#define portColor 4
#define portSwitchDelay 5

#define tileSize 300
#define clearTolerance 200
#define clearToleranceStrict 20
#define headingFixTolerance 5
#define tiltTolerance 10
#define turnSlowDownAngle 15
#define turnStopAngle 2
#define moveSlowDownDistance 40
#define moveStopDistance 10
#define moveTimeout 2000
#define gyroCalibrationPeriod 60000

unsigned long lastGyroCalibrationTime = 0;
int gyroOffset = 0, gyroTiltOffset = 0;
int currentMultiplexerPort = 10;
int currentDirection = 0; //0 forward, 1 right, 2 back, 3 left relative to calibrated direction
int fixingHeading = 0; //0 no, 1 right, 2 left
bool frontBlocked = false, movingForward = false;


void i2cInitializationFailure()
{
  while (true)
  {
    digitalWrite(signalLedPin, HIGH);
    digitalWrite(signalBuzzerPin, HIGH);
    delay(200);
    digitalWrite(signalLedPin, LOW);
    digitalWrite(signalBuzzerPin, LOW);
    delay(200);
  }
}

//______________________________________TOF:
enum TOFdirection {TOF_LB, TOF_LF, TOF_FL, TOF_FR, TOF_RF, TOF_RB};

VL53L1X tofSensor[numTOF];

void initTof(int i)
{
  tofSensor[i].setTimeout(500);
  if (!tofSensor[i].init())
  {
    Serial.print("Tof ");
    Serial.print(i);
    Serial.println(" initialization error!");
    i2cInitializationFailure();
  }
  tofSensor[i].setDistanceMode(VL53L1X::Long);
  tofSensor[i].setMeasurementTimingBudget(50000);
  tofSensor[i].startContinuous(50);
}

//______________________________________Gyro:
Adafruit_BNO055 gyroSensor = Adafruit_BNO055(55, 0x28);

void initGyro()
{ 
  if (!gyroSensor.begin())
  {
    Serial.println("Gyro initialization error!");
    i2cInitializationFailure();
  }
  gyroSensor.setExtCrystalUse(true);
}

//______________________________________Color:
BH1745 colorSensor = BH1745();

void initColor()
{
  if (!colorSensor.begin())
  {
    Serial.println("Color initialization error!");
    i2cInitializationFailure();
  }
  colorSensor.setGain(colorSensor.GAIN_1X);
  colorSensor.setRgbcMode(colorSensor.RGBC_16_BIT);
}


//______________________________________Multiplexer:
DFRobot_I2C_Multiplexer I2CMulti(&Wire, 0x70);

void initMultiplexer()
{
  I2CMulti.begin();
  Wire.begin();
  Wire.setClock(100000); // use 400 kHz I2C
  delay(portSwitchDelay);
}


void initSensors()
{
  delay(100);
  initMultiplexer();
  const int tofPort[numTOF] = portsTOF;
  for(int i = 0; i < numTOF; i++)
  {
    I2CMulti.selectPort(tofPort[i]);
    delay(portSwitchDelay);
    initTof(i);
  }
  
  I2CMulti.selectPort(portGyro);
  delay(portSwitchDelay);
  initGyro();

  I2CMulti.selectPort(portColor);
  delay(portSwitchDelay);
  initColor();
}