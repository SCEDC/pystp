from obspy.core.event import Event
from obspy.core.event.base import ResourceIdentifier
from obspy.core.event.origin import Origin
from obspy.core.event.magnitude import Magnitude
from obspy.core.utcdatetime import UTCDateTime
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
                    'lr': 'Mlr' # TODO: Verify what 'lr' should represent'. 
                  }

# Mapping of STP event types to values allowed in obspy.core.event.header.EventType. 
ETYPE_MAPPING = { 'eq': 'earthquake', \
                  'qb': 'quarry blast', \
                  'sn': 'sonic boom', \
                  'nt': 'nuclear blast', \
                  'uk': 'not reported'}


def make_event(catalog_entry):
    """ Creates an ObsPy Event object from 
    an STP catalog entry.
    """
    print(catalog_entry)
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


