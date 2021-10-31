import asyncio
from asyncio import tasks
import logging
from cbpi.api import *
import time
import datetime


@parameters([Property.Number(label="P", configurable=True, default_value=117.0795, description="P Value of PID"),
             Property.Number(label="I", configurable=True, default_value=0.2747, description="I Value of PID"),
             Property.Number(label="D", configurable=True, default_value=41.58, description="D Value of PID"),
             Property.Number(label="Max_Pump_Temp", configurable=True, default_value=110,
                             description="Max temp the pump can work in."),
             Property.Number(label="Max_Boil_Output", configurable=True, default_value=85,
                             description="Power when Max Boil Temperature is reached."),
             Property.Number(label="Max_Boil_Temp", configurable=True, default_value=98,
                             description="When Temperature reaches this, power will be reduced to Max Boil Output."),
             Property.Number(label="Max_PID_Temp", configurable=True,
                             description="When this temperature is reached, PID will be turned off"),
             Property.Number(label="Rest_Interval", configurable=True, default_value=600,
                             description="Rest the pump after this many seconds during the mash."),
             Property.Number(label="Rest_Time", configurable=True, default_value=60,
                             description="Rest the pump for this many seconds every rest interval.")])
class BM_PID_SmartBoilWithPump(CBPiKettleLogic):

    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self._logger = logging.getLogger(type(self).__name__)
        self.sample_time, self.max_output, self.pid = None, None, None
        self.work_time, self.rest_time, self.max_output_boil, self.max_boil_temp, self.max_pid_temp, self.max_pump_temp\
            = None, None, None, None, None, None
        self.kettle, self.heater, self.agitator = None, None, None

    async def on_stop(self):
        await self.actor_off(self.agitator)

    async def pump_control(self):
        while self.running:
            if self.get_sensor_value(self.kettle.sensor).get("value") < self.pump_max_temp:
                self._logger.debug("starting pump")
                await self.actor_on(self.agitator)
                off_time = time.time() + self.work_time
                while time.time() < off_time:
                    await asyncio.sleep(2)
                    if self.get_sensor_value(self.kettle.sensor).get("value") >= self.pump_max_temp:
                        await self.actor_off(self.agitator)
                self._logger.debug("resting pump")
                # await self.actor_off(self.agitator)
                await asyncio.sleep(self.rest_time)
            else:
                if self.get_actor_state(self.agitator):
                    await self.actor_off(self.agitator)

    async def temp_control(self):
        while self.running:
            sensor_value = current_temp = self.get_sensor_value(self.kettle.sensor).get("value")
            target_temp = self.get_kettle_target_temp(self.id)
            if current_temp >= self.max_boil_temp:
                heat_percent = self.max_output_boil
            elif current_temp >= self.max_pid_temp:
                heat_percent = self.max_output
            else:
                heat_percent = self.pid.calc(sensor_value, target_temp)

            heating_time = self.sample_time * heat_percent / 100
            wait_time = self.sample_time - heating_time
            if heating_time > 0:
                await self.actor_on(self.heater)
                await asyncio.sleep(heating_time)
            if wait_time > 0:
                await self.actor_off(self.heater)
                await asyncio.sleep(wait_time)

    async def run(self):
        try:
            self.sample_time = 5
            self.max_output = 100
            p = float(self.props.get("P", 117.0795))
            i = float(self.props.get("I", 0.2747))
            d = float(self.props.get("D", 41.58))
            self.pid = PIDArduino(self.sample_time, p, i, d, 0, self.max_output)

            self.work_time = float(self.props.get("Rest_Interval", 600))
            self.rest_time = float(self.props.get("Rest_Time", 60))
            self.max_output_boil = float(self.props.get("Max_Boil_Output", 85))
            self.max_boil_temp = float(self.props.get("Max_Boil_Temp", 98))

            mpidt = float(self.props.get("Max_PID_Temp", 88))
            mpt = float(self.props.get("Max_Pump_Temp", 110))
            temp_unit = self.get_config_value("TEMP_UNIT", "C")

            self.kettle = self.get_kettle(self.id)
            self.heater = self.kettle.heater
            self.agitator = self.kettle.agitator

            if temp_unit != "C":
                self.max_pid_temp = round(9.0 / 5.0 * mpidt + 32, 2)
                self.max_pump_temp = round(9.0 / 5.0 * mpt + 32, 2)
            else:
                self.max_pid_temp = float(mpidt)
                self.max_pump_temp = float(mpt)

            logging.info("CustomLogic P:{} I:{} D:{} {} {}".format(p, i, d, self.kettle, self.heater))

            pump_controller = asyncio.create_task(self.pump_control())
            temp_controller = asyncio.create_task(self.temp_control())

            await pump_controller
            await temp_controller

        except asyncio.CancelledError as e:
            pass
        except Exception as e:
            logging.error("BM_PIDSmartBoilWithPump Error {}".format(e))
        finally:
            self.running = False
            await self.actor_off(self.heater)


# Based on Arduino PID Library
# See https://github.com/br3ttb/Arduino-PID-Library
class PIDArduino(object):

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
        if self._outputMax > self._lastOutput > self._outputMin:
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


# class Mock:
#
#     def __init__(self):
#         self.kettle = "a"
#
#     def get(self, a, b):
#         return 1
#
#
# if __name__ == '__main__':
#     bm = BM_PID_SmartBoilWithPump(Mock(), 1, Mock())
#     loop = asyncio.get_event_loop()
#     coroutine = bm.run()
#     loop.run_until_complete(coroutine)