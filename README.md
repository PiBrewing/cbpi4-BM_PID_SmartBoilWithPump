# CBPi4 Braumeister Smart Boil with Pump KettleLogic

### This Kettle Logic can be used to run a Speidel Braumeister with CraftbeerPi4. It is based on this cbpi3 Plugin (https://github.com/cgspeck/cbpi-pidsmartboil-withpump)

## Mash & Boil in single Kettle (e.g. Speidel Braumeister)
- The Kettle logic is intended to be used in a single Kettle. It is a PID logic. PID parameters can be for instance derived from the PID AutoTune plugin (https://github.com/avollkopf/cbpi4-PIDAutoTune)
- It runs on PID control until it reaches a specified temperature. Above that temperature it heates w/o PID logic until a specified boil temp is reached.
- Power to run boil can be specified in the plugin
- Pump Intervals cen be set to have a pump rest on specified intervals for a specified time (e.g. 60 seconds every 600 seconds which is a default for the Braumeister controller)

## Parameters:
- Configurable:
	- P: Proportional - Takes current value into account
	- I: Integral - Takes past values into account
	- D: Derivative - Takes future values into account
	- Max Pump Temp: Pump is switched off above this temperature and cannot be switched back on
	- Max Boil Output: Maximum Power during when Boil Temp is reached
	- Max Boil Temp: When Temp is reached, power is set to Max Boil Output
	- Max PID Temp: PID is switched off above this temperature
	- Rest Interval: Time interval in seconds after which Pump is switched off
	- Rest Time: Pump is switched off for specified time in seconds
	
- Fixed in Code:
	- Max Output: Maximum Power (%) to be used for PID during Ramp up -> 100%


Changelog:

- 01.11.21: Merged Pull request from madhatguy ansd fixed some bugs
- 15.03.21: Support for cbpi >= 4.0.0.32
- 31.10.21: Changed logic to coroutines
