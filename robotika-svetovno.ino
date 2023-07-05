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

void reset()
{
  engageMotors(STOP);
  controlLed(WHITE);
  delay(1000);
  while(digitalRead(buttonPin));
  calibrateGyro();
  controlLed(OFF);
  delay(500);
}

void setup()
{
  Serial.begin(115200);
  initMotors();
  initSignaling();
  initButton();
  initSensors();
  initCameras();
  initServo();
  calibrateGyro();
  Serial.println("Setup succesful");
  setPreferedDirection(RIGHT);
  generateRandomSeed();
  for(int i = 0; i < 8; i++)
  {
    engageMotors(FORWARD,SLOW);
    engageMotors(STOP);
    delay(500);
    engageMotors(BACKWARD,SLOW);
    engageMotors(STOP);
    delay(500);
  }
  blinkLed(GREEN, 2, 200);
  reset();
}

void loop()
{
  goForward();
  chooseNextDirection();
  //rescueVictim(checkVictims());
  //measureColor();
  //delay(500);
}
