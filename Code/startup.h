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


//______________________________________________________Button:
#define buttonPin 12

void initButton()
{
  pinMode(buttonPin, INPUT_PULLUP);
}

//______________________________________________________Signaling:
#define redLedPin 11
#define greenLedPin 13
#define blueLedPin 9

enum LedColor {RED, GREEN, BLUE, CYAN, YELLOW, MAGENTA, WHITE, OFF};

void initSignaling()
{
  pinMode(redLedPin, OUTPUT);
  pinMode(greenLedPin, OUTPUT);
  pinMode(blueLedPin, OUTPUT);
  digitalWrite(redLedPin, LOW);
  digitalWrite(greenLedPin, LOW);
  digitalWrite(blueLedPin, LOW);
}


//______________________________________________________Servo:
#define servoPin 53

Servo servo;

void initServo()
{
  servo.attach(servoPin);
  servo.write(90);
}

//______________________________________________________Motors:
#define motorBLid 1
#define motorFLid 4
#define motorFRid 2
#define motorBRid 3
#define motorIDs {motorBLid, motorBRid, motorFRid, motorFLid}

#define motorSpeedFast 200
#define motorSpeedSlow 100
#define motorTurnSpeedFast 200
#define motorTurnSpeedSlow 50

enum DriveDirection {LEFT, FORWARD, RIGHT, BACKWARD, STOP};
enum DriveSpeed {FAST, SLOW};

ServoCds55 motors;

void engageMotors(DriveDirection direction, DriveSpeed speed);
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
#define cameraPin0L 52
#define cameraPin1L 50
#define cameraPin2L 48
#define cameraPin0R 22
#define cameraPin1R 24
#define cameraPin2R 26
#define leftCameraPins {cameraPin0L, cameraPin1L, cameraPin2L}
#define rightCameraPins {cameraPin0R, cameraPin1R, cameraPin2R}
#define cameraPinsNum 3

#define medKitsNum {0, 0, 1, 1, 2, 3, 0} //None, Green, Red, Yellow, S, H, U
#define victimColorCodes {WHITE, GREEN, RED, YELLOW, MAGENTA, BLUE, CYAN}


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
#define portTofLF 6
#define portTofFL 7
#define portTofFR 0
#define portTofRF 1
#define portTofRB 2
#define numTOF 6
#define portsTOF {portTofLB, portTofLF, portTofFL, portTofFR, portTofRF, portTofRB}
#define portGyro 3
#define portColor 4
#define portSwitchDelay 5
#define sideSensorOffset 40
#define frontSensorOffset 30

#define tileSize 300
#define turnSlowDownAngle 30
#define turnStopAngle 2
#define gyroCalibrationPeriod 60000
#define moveTimeout 5000
#define frontClearanceTolerance 60
#define sideClearanceTolerance 120
#define wallSpacingDistance 30
#define wallSpacingTolerance 20
#define moveOneTileTime 1500
#define blueTileTimeout 4000
#define victimTimeout 5000

unsigned long lastGyroCalibrationTime = 0;
unsigned long lastTurnTime = 0;
unsigned long lastBlueTileTime = 0;
unsigned long lastVictimTime = 0;
int gyroOffset = 0;
int currentMultiplexerPort = 10;
int currentDirection = 0; //0 forward, 1 right, 2 back, 3 left relative to calibrated direction
int fixingHeading = 0; //0 no, 1 right, 2 left
int blackSamples = 0;
int kitsDropped = 0;
bool frontBlocked = false;
DriveDirection preferedDirection = RIGHT;
DriveDirection oppositeDirection = LEFT;
DriveDirection previousCorrectingDirection = BACKWARD;


void i2cInitializationFailure()
{
  while (true)
  {
    digitalWrite(redLedPin, HIGH);
    delay(200);
    digitalWrite(redLedPin, LOW);
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
  tofSensor[i].setDistanceMode(VL53L1X::Medium);
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
