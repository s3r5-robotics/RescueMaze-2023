void engageMotors(DriveDirection direction, DriveSpeed speed = SLOW)
{
  int motorDirection[4];
  if(direction == FORWARD || direction == RIGHT)
  {
    motorDirection[0] = 1;
    motorDirection[3] = 1;
  }
  else
  {
    motorDirection[0] = -1;
    motorDirection[3] = -1;
  }

  if(direction == BACKWARD || direction == RIGHT)
  {
    motorDirection[2] = 1;
    motorDirection[1] = 1;
  }
  else
  {
    motorDirection[2] = -1;
    motorDirection[1] = -1;
  }
  if(direction == STOP)
  {
    for(int i = 0; i < 4; i++) motorDirection[i] = 0;
  }

  int motorSpeed = (speed == FAST) ? motorSpeedFast : motorSpeedSlow;
  const int ID[4] = motorIDs;
  for(int i = 0; i < 4; i++) motors.SetMotormode(ID[i], motorDirection[i]*motorSpeed);
}

void correctHeading(DriveDirection direction)
{
  if(previousCorrectingDirection != direction)
  {
    engageMotors(FORWARD, FAST);
    if(direction == LEFT)
    {
      motors.SetMotormode(motorFLid, motorSpeedSlow);
    }
    else if(direction == RIGHT)
    {
      motors.SetMotormode(motorFRid, motorSpeedSlow*-1);
    }
    previousCorrectingDirection = direction;
  }
}

void setPreferedDirection(DriveDirection direction)
{
  if(direction == RIGHT)
  {
    preferedDirection = RIGHT;
    oppositeDirection = LEFT;
  }
  else
  {
    preferedDirection = LEFT;
    oppositeDirection = RIGHT;
  }
}

void dropMedKits(DriveDirection direction, int num)
{
  if(kitsDropped >= 12) return;
  kitsDropped += num;
  for(int i = 0; i < num; i++)
  {
    if(direction == LEFT)
    {
      servo.write(180);
      delay(500);
      servo.write(70);
      delay(500);
    }
    else if(direction == RIGHT)
    {
      servo.write(0);
      delay(500);
      servo.write(110);
      delay(500);
    }
  }
}

void rescueVictim(int victimType)
{
  Serial.println(victimType);
  if(victimType == 0 || victimType > 6) return;
  engageMotors(STOP);
  const int medKits[7] = medKitsNum;
  const bool moveForward = checkClearance(FORWARD);
  const DriveDirection dropDirection = (victimType < 0) ? LEFT : RIGHT;
  const int kitsToDrop = medKits[abs(victimType)];
  signalVictim(abs(victimType));
  if(measureDistance(TOF_FL) > tileSize)
  {
    engageMotors(FORWARD, FAST);
    delay(500);
    engageMotors(STOP);
  }
  dropMedKits(dropDirection, kitsToDrop);
  engageMotors(FORWARD, FAST);
}

void turn90(DriveDirection direction)
{
  const int targetDirection = (currentDirection + ((direction == LEFT) ? 3 : 1)) % 4;
  const int previousAngle = currentDirection * 90; 
  const int targetAngle = targetDirection * 90;
  const int previousAngleCorrected = (previousAngle + 359) % 360;
  const int targetAngleCorrected = (targetAngle + 359) % 360;
  int currentAngle = measureHeading();
  unsigned long startingTime = millis();
  if(direction == LEFT)
  {
    engageMotors(LEFT, FAST);
    while(!(currentAngle > targetAngle && currentAngle < previousAngleCorrected) && startingTime + moveTimeout > millis()) currentAngle = measureHeading();
    while(!(currentAngle < targetAngle + turnSlowDownAngle) && startingTime + moveTimeout > millis()) currentAngle = measureHeading();
    engageMotors(LEFT, SLOW);
    while(!(currentAngle < targetAngle + turnStopAngle || currentAngle > previousAngleCorrected) && startingTime + moveTimeout > millis()) currentAngle = measureHeading();
  }
  else if(direction == RIGHT) 
  {
    engageMotors(RIGHT, FAST);
    while(!(currentAngle > previousAngle && currentAngle < targetAngleCorrected) && startingTime + moveTimeout > millis()) currentAngle = measureHeading();
    while(!(currentAngle > targetAngleCorrected - turnSlowDownAngle) && startingTime + moveTimeout > millis()) currentAngle = measureHeading();
    engageMotors(RIGHT, SLOW);
    while(!(currentAngle > targetAngleCorrected - turnStopAngle) && startingTime + moveTimeout > millis()) currentAngle = measureHeading();
  }
  engageMotors(STOP);
  currentDirection = targetDirection;
}

/*void turn90(DriveDirection direction = LEFT)
{
  if(direction == LEFT)
  {
    const int targetDirection = (currentDirection + 3) % 4;
    const int previousAngle = currentDirection * 90;
    const int targetAngle = targetDirection * 90;
    const int previousAngleCorrected = (previousAngle + 359) % 360;
    int currentAngle = measureHeading();
    engageMotors(LEFT, FAST);
    Serial.println(targetAngle);
    Serial.println("turn");
    while(!(currentAngle > targetAngle && currentAngle < previousAngleCorrected)) {currentAngle = measureHeading(); Serial.println(currentAngle);}
    while(!(currentAngle < targetAngle + turnSlowDownAngle)){ currentAngle = measureHeading(); Serial.println(currentAngle);}
    engageMotors(LEFT, SLOW);
    Serial.println("Slow");
    while(!(currentAngle < targetAngle + turnStopAngle || currentAngle > previousAngleCorrected)){ currentAngle = measureHeading(); Serial.println(currentAngle);}
    engageMotors(STOP);
    Serial.println("Stop");
    currentDirection = targetDirection;
  }
  else if(direction == RIGHT) 
  {
    const int targetDirection = (currentDirection + 1) % 4;
    const int previousAngle = currentDirection * 90;
    const int targetAngle = targetDirection * 90;
    const int targetAngleCorrected = (targetAngle + 359) % 360;
    int currentAngle = measureHeading();
    engageMotors(RIGHT, FAST);
    Serial.println(targetAngle);
    Serial.println("turn");
    while(!(currentAngle > previousAngle && currentAngle < targetAngleCorrected)) {currentAngle = measureHeading(); Serial.println(currentAngle);}
    while(!(currentAngle > targetAngleCorrected - turnSlowDownAngle)){ currentAngle = measureHeading(); Serial.println(currentAngle);}
    engageMotors(RIGHT, SLOW);
    Serial.println("Slow");
    while(!(currentAngle > targetAngleCorrected - turnStopAngle)){ currentAngle = measureHeading(); Serial.println(currentAngle);}
    engageMotors(STOP);
    Serial.println("Stop");
    currentDirection = targetDirection;
  }
}*/

void chooseNextDirection()
{
  if(!sideClear() || frontBlocked)
  {
    turn90(oppositeDirection);
    if(frontBlocked)
    {
      lastTurnTime = millis();
      frontBlocked = false;
    }
  }
  else
  {
    turn90(preferedDirection);
    lastTurnTime = millis();
  }
}

void goForward()
{
  unsigned long startingTime = millis();
  if(!checkClearance(FORWARD)) return;
  engageMotors(FORWARD, FAST);
  while(true)
  {
    if(!checkClearance(FORWARD))
    {
      Serial.println("exit 1");
      checkGyroCalibration();
      break;
    }
    if(sideClear())
    {
      delay(500);
      Serial.println("exit 2");
      break;
    }
    if(onBlackTile())
    {
      engageMotors(BACKWARD, FAST);
      frontBlocked = true;
      delay(400);
      Serial.println("exit 3");
      break;
    }
    if(onBlueTile())
    {
      delay(250);
      Serial.println("exit 4");
      engageMotors(STOP);
      controlLed(BLUE);
      delay(5000);
      controlLed(OFF);
      lastBlueTileTime = millis();
      engageMotors(FORWARD, FAST);
    }
    if(notMoving())
    {
      engageMotors(BACKWARD, FAST);
      delay(500);
      Serial.println("exit 6");
      break;
    }
    correctHeading(checkSpacing());
    rescueVictim(checkVictims());
    checkLopButton();
  }
  engageMotors(STOP);
  previousCorrectingDirection = BACKWARD;
}
