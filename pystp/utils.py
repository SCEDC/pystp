from obspy.core.event import Event
from obspy.core.event.base import ResourceIdentifier
from obspy.core.event.origin import Origin
from obspy.core.event.origin import Pick
from obspy.core.event.base import WaveformStreamID
from obspy.core.event.magnitude import Magnitude
from obspy.core.utcdatetime import UTCDateTime
from obspy.core.event.base import QuantityError
from datetime import datetime


# Mapping of STP magnitude types to obspy.core.event.magnitude.Magnitude.magnitude_type values.
# magnitude_type is a free-text field, so this mapping uses the strings specifically mentioned
# in https://docs.obspy.org/packages/autogen/obspy.core.event.magnitude.Magnitude.html#obspy.core.event.magnitude.Magnitude
# or that seem reasonable.
MAGTYPE_MAPPING = { 'b': 'Mb', \
                    'e': 'Me', \
                    'l': 'ML', \
                    's': 'MS', \
                    'c': 'Mc',
                    'n': '', \
                    'w': 'Mw', \
                    'h': 'Mh', \
                    'd': 'Md', \
                    'un': 'M', \
                    'lr': 'Mlr'
                  }

# Mapping of STP event types to values allowed in obspy.core.event.header.EventType. 
ETYPE_MAPPING = { 'eq': 'earthquake', \
                  'qb': 'quarry blast', \
                  'sn': 'sonic boom', \
                  'nt': 'nuclear blast', \
                  'uk': 'not reported'}

# Mapping of STP first motion values to polarity for obspy.core.event.origin.Pick.
POLARITY_MAPPING = { 'c': 'positive', \
                     'u': 'positive', \
                     'd': 'negative', \
                     'r': 'dilation', \
                     '.': '' \
                   }

def make_event(catalog_entry):
    """ Creates an ObsPy Event object from 
    a line of STP event output.
    """
    #print(catalog_entry)
    fields = catalog_entry.split()
    
    evid = fields[0]
    etype = fields[1]
    origin_time = UTCDateTime(datetime.strptime(fields[3], "%Y/%m/%d,%H:%M:%S.%f"))

    lat = float(fields[4])
    lon = float(fields[5])
    depth = float(fields[6])
    mag = float(fields[7])
    magtype = fields[8]
    
    res_id = ResourceIdentifier(id=evid)
    origin = Origin(latitude=lat, longitude=lon, depth=depth, time=origin_time)
                                
    magnitude = Magnitude(mag=mag, magnitude_type=MAGTYPE_MAPPING[magtype])
    event = Event(resource_id=res_id, event_type=ETYPE_MAPPING[etype], origins=[origin], magnitudes=[magnitude])
    return event


def make_pick(pick_str, origin_time):
    """ Creates an ObsPy Pick object from a line of STP
    phase output.

    Sample pick_str:
    CI    CLC HHZ --   35.8157  -117.5975   775.0 P c. i  1.0    6.46   1.543
    """
    
    fields = pick_str.split()
    if len(fields) != 13:
        raise Exception('Invalid STP phase output')

    new_pick = Pick()
    (net, sta, chan, loc) = fields[:4]
    new_pick.waveform_id = WaveformStreamID(network_code=net, station_code=sta, channel_code=chan, location_code=loc)
    
    # Determine polarity from first motion.
    polarity = POLARITY_MAPPING[fields[8][0]]
    if polarity == '':
        polarity = POLARITY_MAPPING[fields[8][1]]
    if polarity != '':
        new_pick.polarity = polarity

    # Determine signal onset.
    if fields[9] == 'i':
        new_pick.onset = 'impulsive'
    elif fields[9] == 'e':
        new_pick.onset = 'emergent'
    else:
        new_pick.onset = 'questionable'

    # Determine time error from STP quality.
    # Use Jiggle standard and assume sample rate of 100 sps.
    quality = float(fields[10])
    if quality == 0.0:
        new_pick.time_errors = QuantityError(lower_uncertainty=0.03)
    elif quality <= 0.3:
        new_pick.time_errors = QuantityError(upper_uncertainty=0.03)
    elif quality <= 0.5:
        new_pick.time_errors = QuantityError(upper_uncertainty=0.02)
    elif quality <= 0.8:
        new_pick.time_errors = QuantityError(upper_uncertainty=0.01)
    elif quality == 1.0:
        new_pick.time_errors = QuantityError(upper_uncertainty=0.0)

    # Determine pick time.
    offset = float(fields[12])
    new_pick.time = origin_time + offset

    return new_pick