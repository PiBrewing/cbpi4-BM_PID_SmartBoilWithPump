# CBPi4 Braumeister Smart Boil with Pump KettleLogic

### This Kettle Logic can be used to run a Speidel Braumeister with CraftbeerPi4. It is based on this cbpi3 Plugin (https://github.com/cgspeck/cbpi-pidsmartboil-withpump)

## Mash & Boil in single Kettle (e.g. Speidel Braumeister)
- The Kettle logic is intended to be used in a single Kettle. It is a PID logic. PID parameters can be for instance derived from the PID AutoTune plugin (https://github.com/avollkopf/cbpi4-PIDAutoTune)
- It runs on PID control until it reaches a specified temperature. Above that temperature it heates w/o PID logic until a specified boil temp is reached.
- Power to run boil can be specified in the plugin
- Pump Intervals cen be set to have a pump rest on specified intervals for a specified time (e.g. 60 seconds every 600 seconds which is a default for the Braumeister controller)
- Pump (Kettle Agitator) is siwtched off above 88°C / 190F for pump protection (hard coded)

## Parameters:
- Configurable:
	- P: Proportional - Takes current value into account
	- I: Integral - Takes past values into account
	- D: Derivative - Takes future values into account
	- Max Output: Maximum Power (%) to be used for PID during Ramp up
	- Max Boil Output: Maximum Power during when Boil Temp is reached
	- Max Boil Temp: When Temp is reached,  power is set to Max Boil Output
	- Internal Loop: Seconds of the internal loop -> Determines maximum PID resolution
	- Rest Interval: Time interval in seconds after which Pump is switched off
	- Rest Time: Pump is switched off for specified time in seconds
- Fixed in Code:
	- Max PID Temp: PID is switched off above this temperature -> 88°C / 190F
	- Max Pump Temp: Pump is switched of above this temperatre and cannot be switched back on -> 88°C 190F


Changelog:

15.03.21: Support for cbpi >= 4.0.0.32
