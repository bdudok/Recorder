import nidaqmx
import numpy
from nidaqmx.constants import LineGrouping
# import nidaqmx.system
# system = nidaqmx.system.System.local()

'''
Trigger:
   P2.0: PFI0: start the task (stim train)
   P1.1: PFI1: 2P frame start 
Output:
    AO0: LED power
    P0.0: DO0: Shutter
    P0.1: DO1: Gating
'''

device_name = 'Dev1'
fs = 1000
ms = fs / 1000

lightDur = int(10 * ms)
shutterOpenDelay = int(22 * ms)
shutterCloseDelay = int(6 * ms)

pulseProtocolDur = shutterOpenDelay + lightDur

# generate digital output
dig_out = numpy.zeros((2, pulseProtocolDur), dtype='bool')
dig_out[0, :shutterOpenDelay+lightDur-shutterCloseDelay] = 1 #shutter
dig_out[0, shutterOpenDelay:shutterOpenDelay+lightDur] = 1 #shutter



'''
plan: start a task to wait for the train trigger. read options and set vars such as pulse number, intensity.
then make a task that does the pulse on trigger. Start it on trig, and when it returns, start it again in a for loop 
'''

# with nidaqmx.Task() as task:
# with nidaqmx.Task() as train_task, nidaqmx.Task() as pulse_task:
with nidaqmx.Task('Pulse') as pulse_task:
    # task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
    # data = task.read(number_of_samples_per_channel=1)
    # train_task.triggers.start_trigger.cfg_dig_edge_start_trig("Dev1/port2/line0")

    # pulse_task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
    pulse_task.do_channels.add_do_chan("Dev1/port0/line0", name_to_assign_to_lines="Shutter")
    pulse_task.do_channels.add_do_chan("Dev1/port0/line1", name_to_assign_to_lines="Gating")
    # pulse_task.timing.cfg_samp_clk_timing(fs)



    # train_task.triggers.sync_type.MASTER = True
    # pulse_task.triggers.sync_type.SLAVE = True

    # pulse_task.triggers.start_trigger.cfg_dig_edge_start_trig("Dev1/port1/line1")


    pulse_task.write(dig_out, auto_start=True)
    # pulse_task.write([True,True,], auto_start=True)

    # train_task.start()
    pulse_task.start()

    #GRRR, this is 3.6V


# device = system.devices['Dev1']