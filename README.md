# PySTP

PySTP is a Python module for connecting to [STP (Seismogram Transfer Program)](https://scedc.caltech.edu/research-tools/stp/) servers and downloading event metadata, phase picks, and waveforms triggered by seismic events.

PySTP requires [ObsPy](https://www.obspy.org).

## Installation

Clone the PySTP repository:

```
git clone https://github.com/SCEDC/pystp.git
```

Navigate to the `pystp` directory and run `pip install .` to install the pystp module in your Python environment's path.

```
cd pystp
pip install .
```

## Basic STPClient Functions

`get_events` - Downloads an ObsPy catalog either by event IDs or by search parameters of time window, magnitude range, and location boundaries.

`get_phases` - Downloads an ObsPy catalog containing phase picks.

`get_trig` - Downloads waveforms for one or events as a Python dictionary with event IDs as keys and ObsPy Stream objects as values.

## Usage Example

```python
from pystp import STPClient

client = STPClient()
client.connect()   # Open a connection.

# Download a catalog.
events = client.get_events(times=[datetime.datetime(2019, 10, 17), datetime.datetime(2019, 10, 17, 23, 59, 59)], mags=[2, 4])
# Get event IDs.
evids = [ev.resource_id.id for ev in events]
# Download all CI.CLC.BH waveforms for the events in the catalog.
waveforms = client.get_trig(evids, net='CI', sta='CLC', chan= 'BH_')

# Disconnect from the STP server.
client.disconnect()
```

## Tutorials

[Downloading waveforms](https://github.com/SCEDC/pystp/blob/master/Example%20Notebook.ipynb)

[Downloading events and picks](https://github.com/SCEDC/pystp/blob/master/Example%20Notebook%202%20-%20Events%20and%20Phases.ipynb)

## Links

[STP](https://scedc.caltech.edu/research-tools/stp/)

[ObsPy](https://github.com/obspy/obspy/wiki)