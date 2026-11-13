// MCU side: Modulino Thermo readout, sent to Linux over the Bridge once per second.
// Sound/vibration and camera are handled on the Linux side (USB mic + USB camera).
#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>

ModulinoThermo thermo;
bool thermo_ok = false;

void setup() {
  Bridge.begin();
  Modulino.begin();
  thermo_ok = thermo.begin();
}

void loop() {
  if (thermo_ok) {
    Bridge.notify("env", thermo.getTemperature(), thermo.getHumidity());
  } else {
    Bridge.notify("sensor_error", "thermo");
  }
  delay(1000);
}
