/*void controlSignaling(bool enabled, int delayTime)
{
  digitalWrite(signalLedPin, enabled);
  digitalWrite(signalBuzzerPin, enabled);
  delay(delayTime);
}

void signalVictim()
{
  for(int i = 0; i < 3; i++)
  {
    controlSignaling(true, 200);
    controlSignaling(false, 200);
  }
  for(int i = 0; i < 3; i++)
  {
    controlSignaling(true, 600);
    controlSignaling(false, 200);
  }
  for(int i = 0; i < 3; i++)
  {
    controlSignaling(true, 200);
    controlSignaling(false, 200);
  }
  delay(200);
}*/

void controlLed(LedColor color)
{
  digitalWrite(redLedPin, (color == RED || color == YELLOW || color == MAGENTA || color == WHITE));
  digitalWrite(greenLedPin, (color == GREEN || color == YELLOW || color == CYAN || color == WHITE));
  digitalWrite(blueLedPin, (color == BLUE || color == CYAN || color == MAGENTA || color == WHITE));
}

void blinkLed(LedColor color, int num, int interval)
{
  for(int i = 0; i < num; i++)
  {
    controlLed(color);
    delay(interval);
    controlLed(OFF);
    delay(interval);
  }
}

void signalVictim(int victimType)
{
  const LedColor colorArray[7] = victimColorCodes;
  LedColor color = colorArray[victimType];
  blinkLed(color, 3, 200);
  blinkLed(color, 3, 400);
  blinkLed(color, 3, 200);
}
