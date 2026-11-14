// MCU side: Modulino Thermo readout, sent to Linux over the Bridge once per second,
// and the Modulino Buzzer alarm, switched on/off by the Linux app ("alarm" call).
// Sound/vibration and camera are handled on the Linux side (USB mic + USB camera).
#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>

ModulinoThermo thermo;
ModulinoBuzzer buzzer;
bool thermo_ok = false;
bool buzzer_ok = false;
bool alarm_on = false;

void set_alarm(bool on) {
  alarm_on = on;
  if (buzzer_ok && !on) {
    buzzer.noTone();
  }
}

void setup() {
  Bridge.begin();
  Bridge.provide("alarm", set_alarm);
  Modulino.begin();
  thermo_ok = thermo.begin();
  buzzer_ok = buzzer.begin();
}

void loop() {
  if (thermo_ok) {
    Bridge.notify("env", thermo.getTemperature(), thermo.getHumidity());
  } else {
    Bridge.notify("sensor_error", "thermo");
  }
  if (alarm_on && buzzer_ok) {
    buzzer.tone(2000, 300);  // short beep once per second while the alarm is on
  }
  delay(1000);
}
