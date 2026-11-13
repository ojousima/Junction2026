// Smoke test: Modulino Thermo + Movement readout over Bridge.
#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>

ModulinoThermo thermo;
ModulinoMovement imu;

void setup() {
  Bridge.begin();
  Modulino.begin();
  thermo.begin();
  imu.begin();
}

void loop() {
  imu.update();
  float t = thermo.getTemperature();
  float h = thermo.getHumidity();
  Bridge.notify("env", t, h, imu.getX(), imu.getY(), imu.getZ());
  delay(1000);
}
