void controlSignaling(bool enabled, int delayTime)
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
}