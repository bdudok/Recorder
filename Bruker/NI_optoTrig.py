import nidaqmx
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

# with nidaqmx.Task() as task:
with nidaqmx.Task() as train_task, nidaqmx.Task() as pulse_task:
    # task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
    # data = task.read(number_of_samples_per_channel=1)


    train_task.triggers.sync_type.MASTER = True
    pulse_task.triggers.sync_type.SLAVE = True

    pulse_task.triggers.start_trigger.cfg_dig_edge_start_trig("/PXI1Slot3/ai/StartTrigger")

    pulse_task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
    pulse_task.write([1.1, 2.2, 3.3, 4.4, 5.5], auto_start=True)

    train_task.start()
    pulse_task.start()


# device = system.devices['Dev1']