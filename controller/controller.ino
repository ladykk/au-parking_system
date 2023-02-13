// Pins Configurations
#define K_SENSOR_T 2
#define K_SENSOR_E 3
#define K_BUTTON 4
#define C_MODE 5
#define C_OPEN 6
#define C_CLOSE 7
#define C_BARRICADE_LED 8
#define C_MODE_LED 9
#define P_SENSOR_T 10
#define P_SENSOR_E 11
#define P_BARRICADE 12

// Initial States
int mode = 0;
int b_open = 0;
int b_close = 0;
int k_sensor = 0;
int k_button = 0;
int p_sensor = 0;
int barricade = 0;

// Serial Variables
String command;
bool is_send = false;

// Reading Functions
int readUltrasonicDistance(int triggerPin, int echoPin)
{
  // Clear the trigger
  pinMode(triggerPin, OUTPUT);
  digitalWrite(triggerPin, LOW);
  delayMicroseconds(2);
  // Set the trigger pin to HIGH state for 10 microseconds.
  digitalWrite(triggerPin, HIGH);
  delayMicroseconds(5);
  digitalWrite(triggerPin, LOW);
  // Read the echo pin, and returns the sound wave travel time in microseconds.
  pinMode(echoPin, INPUT);
  return pulseIn(echoPin, HIGH) / 29 / 2;
}

// Barricade Functions
void openBarricade()
{
  barricade = 1;
  digitalWrite(P_BARRICADE, LOW);
  digitalWrite(C_BARRICADE_LED, HIGH);
}

void closeBarricade()
{
  barricade = 0;
  digitalWrite(P_BARRICADE, HIGH);
  digitalWrite(C_BARRICADE_LED, LOW);
}

// Setup Function
void setup()
{
  Serial.begin(9600);
  pinMode(K_SENSOR_T, OUTPUT);
  pinMode(K_SENSOR_E, INPUT);
  pinMode(K_BUTTON, INPUT);
  pinMode(C_MODE, INPUT);
  pinMode(C_OPEN, INPUT);
  pinMode(C_CLOSE, INPUT);
  pinMode(C_BARRICADE_LED, OUTPUT);
  pinMode(C_MODE_LED, OUTPUT);
  pinMode(P_SENSOR_T, OUTPUT);
  pinMode(P_SENSOR_T, INPUT);
  pinMode(P_BARRICADE, OUTPUT);
  digitalWrite(P_BARRICADE, HIGH);
}

// Loop Function
void loop()
{
  // Reading values.
  mode = digitalRead(C_MODE);
  b_open = digitalRead(C_OPEN);
  b_close = digitalRead(C_CLOSE);
  k_sensor = readUltrasonicDistance(K_SENSOR_T, K_SENSOR_E);
  k_button = digitalRead(K_BUTTON);
  p_sensor = readUltrasonicDistance(P_SENSOR_T, P_SENSOR_E);

  // Write values.
  digitalWrite(C_MODE_LED, mode);

  // Read received command
  command = "";
  if (Serial.available())
  {
    command = Serial.readStringUntil('\n');
    command.trim();
  }

  // Mannual Mode
  if (mode)
  {
    // Open Barricade Pressed
    if (b_open)
      openBarricade();
    if (b_close)
      closeBarricade();
  }
  // Command Mode
  else
  {
    // Check commands.
    if (command.equals("open barricade."))
      openBarricade();
    else if (command.equals("close barricade."))
      closeBarricade();
  }

  /*
    Serial Communication Print
    Format:
      1. mode
      2. b_open
      3. b_close
      4. k_button
      5. barricade
      6. k_sensor
      7. p_sensor
  */

  Serial.print("Values:");
  Serial.print(mode);
  Serial.print(",");
  Serial.print(b_open);
  Serial.print(",");
  Serial.print(b_close);
  Serial.print(",");
  Serial.print(k_button);
  Serial.print(",");
  Serial.print(barricade);
  Serial.print(",");
  Serial.print(k_sensor);
  Serial.print(",");
  Serial.println(p_sensor);
}
