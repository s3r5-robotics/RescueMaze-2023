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


int measureHeading()
{
  SwitchMultiplexerPort(portGyro);
  sensors_event_t orientationData;
  gyroSensor.getEvent(&orientationData, Adafruit_BNO055::VECTOR_EULER);
  return (int(orientationData.orientation.x) - gyroOffset + 360) % 360;
}


bool checkClearance(DriveDirection direction)
{
  if(direction == FORWARD)
  {
    int distanceLimit = frontClearanceTolerance + frontSensorOffset;
    if(measureDistance(TOF_FL) < distanceLimit && measureDistance(TOF_FR) < distanceLimit)
    {
      return false;
    }
  }
  else if(direction == LEFT)
  {
    int distanceLimit = sideClearanceTolerance + sideSensorOffset;
    if(measureDistance(TOF_LB) < distanceLimit /*&& measureDistance(TOF_LF) < distanceLimit*/)
    {
      return false;
    }
  }
  else if(direction == RIGHT)
  {
    int distanceLimit = sideClearanceTolerance + sideSensorOffset;
    if(measureDistance(TOF_RB) < distanceLimit /*&& measureDistance(TOF_RF) < distanceLimit*/)
    {
      return false;
    }
  }
  return true;
}

void calibrateGyro()
{
  currentDirection = 0;
  gyroOffset = 0;
  gyroOffset = measureHeading();
}

void checkGyroCalibration()
{
  if(lastGyroCalibrationTime + gyroCalibrationPeriod < millis() && !checkClearance(FORWARD))
  {
    engageMotors(FORWARD, SLOW);
    delay(1000);
    engageMotors(STOP, SLOW);
    delay(500);
    calibrateGyro();
    blinkLed(WHITE, 2, 100);
    engageMotors(BACKWARD, SLOW);
    delay(500);
    engageMotors(STOP, SLOW);
    lastGyroCalibrationTime = millis();
  }
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
  if(colorSensor.clear > 20) return 0;
  else if(int(float(colorSensor.blue)/1.5) > colorSensor.green) return 1;
  else return 2;
}

bool onBlackTile()
{
  if(measureColor() == 2)
  {
    blackSamples++;
    if(blackSamples > 2)
    {
      blackSamples = 0;
      return true;
    }
  }
  else
  {
    blackSamples = 0;
  }
  return false;
}

bool onBlueTile()
{
  if(measureColor() == 1 && lastBlueTileTime + blueTileTimeout < millis())
  {
    return true;
  }
  return false;
}

bool sideClear()
{
  if(checkClearance(preferedDirection) && lastTurnTime + moveOneTileTime < millis())
  {
    return true;
  }
  return false;
}

bool notMoving()
{
  return false;
}

DriveDirection checkSpacing()
{
  TOFdirection preferedSensor = (preferedDirection == LEFT) ? TOF_LF : TOF_RF;
  const int targetDistance = wallSpacingDistance + sideSensorOffset;
  const int currentDistance = measureDistance(preferedSensor);
  if(currentDistance > targetDistance + wallSpacingTolerance && currentDistance < tileSize)
  {
    return preferedDirection;
  }
  else if(currentDistance < targetDistance - wallSpacingTolerance)
  {
    return oppositeDirection;
  }
  else
  {
    return FORWARD;
  }
}

int checkVictims()
{
  int victimType = 0;
  if(lastVictimTime + victimTimeout < millis())
  {
    const int leftPins[cameraPinsNum] = leftCameraPins;
    const int rightPins[cameraPinsNum] = rightCameraPins;
    int leftVal = 0, rightVal = 0;
    for(int i = cameraPinsNum-1; i >= 0; i--)
    { 
      leftVal <<= 1;
      leftVal += digitalRead(leftPins[i]);
      rightVal <<= 1;
      rightVal += digitalRead(rightPins[i]);
    }
    if(leftVal != 0 && !checkClearance(LEFT))
    {
      victimType = leftVal * -1;
      lastVictimTime = millis();
    }
    else if(rightVal != 0 && !checkClearance(RIGHT))
    {
      victimType = rightVal;
      lastVictimTime = millis();
    } 
  }
  return victimType;
}

void reset();
void checkLopButton()
{
  if(!digitalRead(buttonPin)) reset();
}
