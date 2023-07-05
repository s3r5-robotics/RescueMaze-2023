#include <SPI.h>
#include <ServoCds55.h>
#include <Servo.h>
#include <Wire.h>
#include <VL53L1X.h>
#include "DFRobot_I2C_Multiplexer.h"
#include "Adafruit_TCS34725.h"
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <BH1745.h>


#include "startup.h"
#include "signaling.h"
#include "detection.h"
#include "movement.h"

void setup()
{
  Serial.begin(115200);
  initMotors();
  initSignaling();
  initSensors();
  initCameras();
  initServo();
  calibrateGyro();
  Serial.println("Setup succesful");
  generateRandomSeed();
  for(int i = 0; i < 8; i++)
  {
    engageMotors(FORWARD,SLOW);
    engageMotors(BACKWARD,SLOW); 
    engageMotors(STOP); 
    delay(50);
  }
  controlSignaling(1, 50);
  controlSignaling(0, 50);
}

void loop()
{
  checkVictims();
  chooseNextDirection();
  checkVictims();
  moveToNextTile();
}
