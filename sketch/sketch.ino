// Smoke test: Modulino Thermo + Movement readout over Bridge.
#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>

ModulinoThermo thermo;
ModulinoMovement imu;
bool thermo_ok = false;
bool imu_ok = false;

void setup() {
  Bridge.begin();
  Modulino.begin();
  thermo_ok = thermo.begin();
  imu_ok = imu.begin();
}

void loop() {
  int fresh = imu_ok ? imu.update() : 0;
  float t = thermo.getTemperature();
  float h = thermo.getHumidity();
  Bridge.notify("env", t, h, imu.getX(), imu.getY(), imu.getZ());
  Bridge.notify("status", (int)thermo_ok, (int)imu_ok, fresh);
  delay(1000);
}
