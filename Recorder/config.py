from Recorder.token import token

user_list = (
    'Recorder',
    'Mate',
    'Barna',
    'Emre',
    'Shanii',
)

stim_config_fields = ('n', 'f', 'l', 'p', 'b', 'g') #to keep button order fix
stim_field_labels = { #this will be displayed in GUI
    'n': 'Stims per train',
    'f': 'Burst frequency (Hz)',
    'l': 'Pulse duration (ms)',
    'p': 'Power (0-1)',
    'b': 'Burst duration (s)',
    'g': 'Gating (True/False)',
}

serial_path = 'COM12' #Windows