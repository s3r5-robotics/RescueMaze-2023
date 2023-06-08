#pragma once

void SwitchMultiplexerPort(int port)
{
  if(currentMultiplexerPort != port)
  {
    I2CMulti.selectPort(port);
    delay(portSwitchDelay);
  }
}

int measureDistance(TOFdirection direction)
{
  const int port[numTOF] = portsTOF;
  SwitchMultiplexerPort(port[direction]);
  return tofSensor[direction].read();
}

bool checkClearance(DriveDirection direction, bool strict = false)
{
  if(direction == FORWARD)
    if((measureDistance(TOF_FL) < clearTolerance || measureDistance(TOF_FR) < clearTolerance) && !strict) return false;
    if((measureDistance(TOF_FL) < clearToleranceStrict || measureDistance(TOF_FR) < clearToleranceStrict) && strict) return false;
  if(direction == LEFT)
    if((measureDistance(TOF_LB) < clearTolerance || measureDistance(TOF_LF) < clearTolerance) && !strict) return false;
    if((measureDistance(TOF_LB) < clearToleranceStrict || measureDistance(TOF_LF) < clearToleranceStrict) && strict) return false;
  if(direction == RIGHT)
    if((measureDistance(TOF_RB) < clearTolerance || measureDistance(TOF_RF) < clearTolerance) && !strict) return false;
    if((measureDistance(TOF_RB) < clearToleranceStrict || measureDistance(TOF_RF) < clearToleranceStrict) && strict) return false;
  return true;
}

int measureTilt()
{
  SwitchMultiplexerPort(portGyro);
  sensors_event_t orientationData;
  gyroSensor.getEvent(&orientationData, Adafruit_BNO055::VECTOR_EULER);
  return abs(int(orientationData.orientation.y) - gyroTiltOffset + 90);
}

int measureHeading()
{
  SwitchMultiplexerPort(portGyro);
  sensors_event_t orientationData;
  gyroSensor.getEvent(&orientationData, Adafruit_BNO055::VECTOR_EULER);
  return (int(orientationData.orientation.x) - gyroOffset + 360) % 360;
}

void calibrateGyro()
{
  currentDirection = 0;
  gyroOffset = 0;
  gyroTiltOffset = 0;
  delay(500);
  gyroOffset = measureHeading();
  gyroTiltOffset = measureTilt();
}




int measureColor()
{
  SwitchMultiplexerPort(portColor);
  colorSensor.read();
  /*Serial.print(colorSensor.clear);
  Serial.print(", ");
  Serial.print(colorSensor.blue);
  Serial.print(", ");
  Serial.println(colorSensor.green);*/
  if(colorSensor.clear > 50) return 0;
  if(int(float(colorSensor.blue)/1.2) > colorSensor.green) return 1;
  return 2;
}

void dropMedKits(bool direction, int num);
void checkVictims()
{
  if(lastVictimTime + victimTimeBuffer < millis())
  {
    const int medKits[7] = medKitsNum;
    const int leftPins[cameraPinsNum] = leftCameraPins;
    const int rightPins[cameraPinsNum] = rightCameraPins;
    int leftVal = 0, rightVal = 0;
    delay(200);
    for(int i = cameraPinsNum-1; i >= 0; i--)
    { 
      leftVal <<= 1;
      leftVal += digitalRead(leftPins[i]);
      rightVal <<= 1;
      rightVal += digitalRead(rightPins[i]);
    }
    if(leftVal != 0 && !checkClearance(LEFT))
    {
      signalVictim();
      dropMedKits(false, medKits[leftVal]);
      lastVictimTime = millis();
    }
    else if(rightVal != 0 && !checkClearance(RIGHT))
    {
      signalVictim();
      dropMedKits(true, medKits[rightVal]);
      lastVictimTime = millis();
    }
  }
}