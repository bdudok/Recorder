import win32com

import win32com.client
pl = win32com.client.Dispatch("PrairieLink64.Application")

pl.Connect()

# pl.SendScriptCommands('-ts') #start movie
pl.SendScriptCommands('-stop') #stop movie

'''
{-TSeries|-ts}
Performs a T-series using the current settings.

{-Abort|-stop}
Aborts any scans or script commands in progress.  Any script commands sent along with this command will not be run,
 even commands appearing before the abort; just run them in a separate request if needed.  This command will also abor
  any acquisitions in progress, even those not started with a script.  Additionally any voltage output, voltage
   recording or mark point experiments in progress will also be aborted.  This command will have no effect when run
    from within Prairie View; it is only for use from the command line, through PrairieLink or direct TCP/IP
     communication.
     
{-SetSavePath|-p} <Path> [addDateTime]
Changes the directory where scan data is saved.

{-SetFileName|-fn} {acquisition type AtlasVolume|BrightnessOverTime|LineScan|MarkPoints|PointScan|SingleImage|TSeries|VoltageRecording|WSeries|XZYZ|ZSeries} <Filename no path> [addDateTime]
Sets the filename for the specified acquisition type.  If the optional parameter addDateTime is included, then the current date and time will be appended to the specified filename.
'''

# pl.Disconnect()