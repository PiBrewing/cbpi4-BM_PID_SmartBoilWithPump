import asyncio
from asyncio import tasks
import logging
from cbpi.api import *
import time
import datetime

@parameters([Property.Number(label = "P", configurable = True, default_value = 117.0795, description="P Value of PID"),
             Property.Number(label = "I", configurable = True, default_value = 0.2747, description="I Value of PID"),
             Property.Number(label = "D", configurable = True, default_value = 41.58, description="D Value of PID"),
             Property.Number(label = "Max_Output", configurable = True, default_value = 100, description="Max power for PID and Ramp up."),
             Property.Number(label = "Max_Boil_Output", configurable = True, default_value = 85, description="Power when Max Boil Temperature is reached."),
             Property.Number(label = "Max_Boil_Temp", configurable = True, default_value = 98,description="When Temperature reaches this, power will be reduced to Max Boil Output."),
             Property.Number(label = "Internal_loop", configurable = True, default_value = 0.2, description="In seconds, how quickly the internal loop will run, dictates maximum PID resolution."),
             Property.Number(label = "Rest_Interval", configurable = True, default_value = 600, description="Rest the pump after this many seconds during the mash."),
             Property.Number(label = "Rest_Time", configurable = True, default_value = 60, description="Rest the pump for this many seconds every rest interval.")])

class BM_PID_SmartBoilWithPump(CBPiKettleLogic):


    async def on_stop(self):
        await self.actor_off(self.agitator)
    
    async def run(self):
        self._logger = logging.getLogger(type(self).__name__)
        try:
            wait_time = sampleTime = 5
            p = float(self.props.get("P", 117.0795))
            i = float(self.props.get("I", 0.2747))
            d = float(self.props.get("D", 41.58))
            maxoutput = float(self.props.get("Max_Output", 100))
            Max_PID_Temp = 88
            maxoutputboil = float(self.props.get("Max_Boil_Output", 85))
            maxtempboil = float(self.props.get("Max_Boil_Temp", 98))
            internal_loop_time = float(self.props.get("Internal_loop", 0.2))
            mash_pump_rest_interval = float(self.props.get("Rest_Interval", 600))
            mash_pump_rest_time = float(self.props.get("Rest_Time", 60))
            Pump_Max_Temp = 88
            self.TEMP_UNIT = self.get_config_value("TEMP_UNIT", "C")

            self.kettle = self.get_kettle(self.id)
            self.heater = self.kettle.heater
            self.agitator = self.kettle.agitator

            if self.TEMP_UNIT != "C":        
                maxtemppid = round(9.0 / 5.0 * Max_PID_Temp + 32, 2)
                pump_max_temp = round(9.0 / 5.0 * Pump_Max_Temp + 32, 2)
            else:
                maxtemppid = float(Max_PID_Temp)
                pump_max_temp = float(Pump_Max_Temp)

            pid = BM_PIDArduino(sampleTime, p, i, d, 0, maxoutput)

            self.start_time = time.time()
            self._logger.debug(self.props.get("Internal_Loop", 0.2))
            self._logger.debug(internal_loop_time)

            next_pump_start = 0
            next_pump_rest = None
            pump_boil_auto_off_control_enabled = True

            if (self.get_sensor_value(self.kettle.sensor).get("value") < pump_max_temp):
                await self.actor_on(self.agitator)
                print("Switching Pump on")

            logging.info("CustomLogic P:{} I:{} D:{} {} {}".format(p, i, d, self.kettle, self.heater))
            while self.running == True:
                sensor_value = current_temp = self.get_sensor_value(self.kettle.sensor).get("value")
                target_temp = self.get_kettle_target_temp(self.id)
                self._logger.debug("calculation cycle")
                inner_loop_now = calculation_loop_start = time.time()
                next_calculation_time = calculation_loop_start + sampleTime

                boil_mode = current_temp > maxtemppid # changed from target_temp according to descriptio above maxtempPID should be smaller than pump_max_temp

                if not boil_mode: #PID
                    heat_percent = pid.calc(current_temp, target_temp)
                elif current_temp < maxtempboil: #Boil Ramp
                    heat_percent = maxoutput
                else: #Boil Sustain
                    heat_percent = maxoutputboil
    
                heating_time = sampleTime * heat_percent / 100
                heat_to = calculation_loop_start + heating_time

                wait_time = sampleTime - heating_time

                while inner_loop_now < next_calculation_time:
                    self._logger.debug("inner loop cycle")

                    if inner_loop_now == calculation_loop_start and heating_time > 0:
                        self._logger.debug("inner loop heat on")
                        await self.actor_on(self.heater)

                    if inner_loop_now > calculation_loop_start and \
                            inner_loop_now >= heat_to and \
                            wait_time > 0:
                        self._logger.debug("inner loop heat off")
                        await self.actor_off(self.heater)
                        wait_time = -1  # to stop off being called continuously

                    if boil_mode:
                        if current_temp > pump_max_temp and pump_boil_auto_off_control_enabled:
                            self._logger.debug("pump off and auto off disabled")
                            pump_boil_auto_off_control_enabled = False
                            self._logger.debug("further mash pump logic is disabled") 
                            next_pump_start = None
                            next_pump_rest = None
                            await self.actor_off(self.agitator)
                        else:
                            self._logger.debug("pump restarted and auto off enabled")
                            pump_boil_auto_off_control_enabled = True
                            await self.actor_off(self.agitator)
                    else:
                        if current_temp < pump_max_temp:
                            if next_pump_start is not None and inner_loop_now >= next_pump_start:
                                self._logger.debug("starting pump")
                                next_pump_start = None
                                next_pump_rest = inner_loop_now + mash_pump_rest_interval
                                await self.actor_on(self.agitator)
                            elif next_pump_rest is not None and inner_loop_now >= next_pump_rest:
                                self._logger.debug("resting pump")
                                next_pump_rest = None
                                next_pump_start = inner_loop_now + mash_pump_rest_time
                                await self.actor_off(self.agitator)
                        else:
                            if self.get_actor_state(self.agitator) == True:
                                await self.actor_off(self.agitator)


                    await asyncio.sleep(internal_loop_time)
                    inner_loop_now = time.time()

        except asyncio.CancelledError as e:
            pass
        except Exception as e:
            logging.error("BM_PIDSmartBoilWithPump Error {}".format(e))
        finally:
            self.running = False
            await self.actor_off(self.heater)

# Based on Arduino PID Library
# See https://github.com/br3ttb/Arduino-PID-Library
class BM_PIDArduino(object):

    def __init__(self, sampleTimeSec, kp, ki, kd, outputMin=float('-inf'),
                 outputMax=float('inf'), getTimeMs=None):
        if kp is None:
            raise ValueError('kp must be specified')
        if ki is None:
            raise ValueError('ki must be specified')
        if kd is None:
            raise ValueError('kd must be specified')
        if float(sampleTimeSec) <= float(0):
            raise ValueError('sampleTimeSec must be greater than 0')
        if outputMin >= outputMax:
            raise ValueError('outputMin must be less than outputMax')

        self._logger = logging.getLogger(type(self).__name__)
        self._Kp = kp
        self._Ki = ki * sampleTimeSec
        self._Kd = kd / sampleTimeSec
        self._sampleTime = sampleTimeSec * 1000
        self._outputMin = outputMin
        self._outputMax = outputMax
        self._iTerm = 0
        self._lastInput = 0
        self._lastOutput = 0
        self._lastCalc = 0

        if getTimeMs is None:
            self._getTimeMs = self._currentTimeMs
        else:
            self._getTimeMs = getTimeMs

    def calc(self, inputValue, setpoint):
        now = self._getTimeMs()

        if (now - self._lastCalc) < self._sampleTime:
            return self._lastOutput

        # Compute all the working error variables
        error = setpoint - inputValue
        dInput = inputValue - self._lastInput

        # In order to prevent windup, only integrate if the process is not saturated
        if self._lastOutput < self._outputMax and self._lastOutput > self._outputMin:
            self._iTerm += self._Ki * error
            self._iTerm = min(self._iTerm, self._outputMax)
            self._iTerm = max(self._iTerm, self._outputMin)

        p = self._Kp * error
        i = self._iTerm
        d = -(self._Kd * dInput)

        # Compute PID Output
        self._lastOutput = p + i + d
        self._lastOutput = min(self._lastOutput, self._outputMax)
        self._lastOutput = max(self._lastOutput, self._outputMin)

        # Log some debug info
        self._logger.debug('P: {0}'.format(p))
        self._logger.debug('I: {0}'.format(i))
        self._logger.debug('D: {0}'.format(d))
        self._logger.debug('output: {0}'.format(self._lastOutput))

        # Remember some variables for next time
        self._lastInput = inputValue
        self._lastCalc = now
        return self._lastOutput

    def _currentTimeMs(self):
        return time.time() * 1000

def setup(cbpi):

    '''
    This method is called by the server during startup 
    Here you need to register your plugins at the server
    
    :param cbpi: the cbpi core 
    :return: 
    '''

    cbpi.plugin.register("BM_PID_SmartBoilWithPump", BM_PID_SmartBoilWithPump)
