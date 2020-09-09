from __future__ import print_function

import socket
import struct
import re
import os
import obspy.core
from obspy.core import Stream
from obspy.core.event import Catalog
from . import utils

VALID_FORMATS = ['sac', 'mseed', 'seed', 'ascii', 'v0', 'v1']

class STPClient:
    
    def __init__(self, host='stp.gps.caltech.edu', port=9999, output_dir='.', verbose=False):
        """ Set up a new STPClient object.
        """
        
        self.host = host
        self.port = port
        self.socket = None
        self.fdr = None      # File handle to the socket
        self.fdout = None    # Output file handle
        self.output_dir = '.'
        self.message = ''  # Most recent message from the server
        self.motd = ''     # Message of the Day
        self.recent_files = []   # List of most recently written files
        self.verbose = verbose
        self.connected = False
        

    def _send_sample(self):
        """ Send the integer 2 to the server
        to verify endianness.
        """

        two = struct.Struct('I').pack(2)
        nbytes = self.socket.send(two)
        

    def _read_message(self):
        """ Read and store text sent from the STP server delimited
        by MESS and ENDmess.
        """

        message = ''
        while True:
            line = self.fdr.readline()

            if not line or line == b'OVER\n' or line == b'ENDmess\n':
                break
            
            message += line.decode('ascii')
        return message


    def _process_error(self, fields):
        """ Display STP error messages.
        """

        err_msg = ' '.join(fields[1:])
        print(err_msg)
        

    def _set_motd(self):
        """ Reads the message of the day from the server
        and stores it in self.motd.
        """
        
        line = self.fdr.readline()
        if line == b'MESS\n':
            self.motd = self._read_message()
        else:
            words = line.split()
            if words[0] == b'ERR':
                self._process_error(words)
        self.fdr.readline()   # Read the b'OVER\n'


    def _receive_data(self):
        """ Process results sent by the STP server.
        """

        if self.verbose:
            print("STPClient._receive_data()")
        while True:
            line = self.fdr.readline()
            if self.verbose:
                print('_receive_data: Received line ', line)
                
            if not line:
                self.output_dir = '.'
                break
            
            line_words = line.decode('ascii').split()
            if len(line_words) == 0:
                continue
            if self.verbose:
                print('_receive_data: ', line_words)

            if line_words[0] == 'OVER':
                self.output_dir = '.'
                break
            elif line_words[0] == 'FILE':
                if self.fdout:
                    self.fdout.close()
                outfile = os.path.join(self.output_dir, line_words[1])
                if self.verbose:
                    print('Opening {} for writing'.format(outfile))
                self.fdout = open(outfile, 'wb')
                if not self.fdout:
                    print('Could not open {} for writing'.format(outfile))
                else:
                    self.recent_files.append(outfile)
            elif line_words[0] == 'DIR':
                # Create output directory
                self.output_dir = os.path.join(self.output_dir, line_words[1])
                if not os.path.isdir(self.output_dir):
                    os.mkdir(self.output_dir)
            elif line_words[0] == 'MESS':
                msg = self._read_message()
                self.message += msg
                print(msg, end='')
            
            elif line_words[0] == 'DATA':
                ndata = int(line_words[1])
                # TODO: Read ndata bytes from self.fdr
                data = self.fdr.read(ndata)
                # Write to self.fdout
                if self.fdout:
                    self.fdout.write(data)
            elif line_words[0] == 'ENDdata':
                continue
            elif line_words[0] == 'ERR':
                self._process_error(line_words)
                
    
    def set_verbose(self, verbose):
        self.verbose = verbose


    def set_output_dir(self, output_dir):
        """ Change the base output directory.
        """
        self.output_dir = output_dir


    def connect(self, show_motd=True):
        """ Connect to STP server.
        """

        if self.connected:
            print('Already connected')
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.fdr = self.socket.makefile(mode='rb')

        self.socket.sendall(b'STP stpisgreat 1.6.3 stpc\n')
       
        line = self.fdr.readline()
        if line != b'CONNECTED\n':
            raise Exception('Failed to connect')

        self._send_sample()

        self._set_motd()
        if show_motd:
            print(self.motd, end='')
        self.connected = True


    def _send_data_command(self, cmd, data_format, as_stream=True, keep_files = False):
        """ Send a waveform request command process the results.
        """

        data_format = data_format.lower()
        if data_format not in VALID_FORMATS:
            raise Exception('Invalid data format')
        if self.verbose:
            print("data_format={} cmd={}".format(data_format, cmd))
        self.socket.sendall('{}\n'.format(data_format).encode('utf-8'))
        self._receive_data()
        self.socket.sendall(cmd.encode('utf-8'))
        self._receive_data()        

        waveform_stream = None
        if as_stream:
            waveform_stream = Stream()
            ntraces = 0
            for f in self.recent_files:
                try:
                    if self.verbose:
                        print('Reading {}'.format(f))
                    tr = obspy.core.read(f)
                    waveform_stream += tr
                    ntraces += 1
                except TypeError:
                    if self.verbose:
                        print('{} is in unknown format. Skipping.'.format(f))
                        

                if not keep_files:
                    if self.verbose:
                        print("Removing {} after reading".format(f))
                    if os.path.isfile(f):
                        os.remove(f)
            print('Processed {} waveform traces'.format(ntraces))
            
        return waveform_stream


    def _end_command(self):
        """ Perform cleanup after an STP command is ended.
        """

        if self.fdout:
            self.fdout.close()
        self.recent_files.clear()
        self._clear_message()

    def _clear_message(self):
        self.message = ''

    def get_trig(self, evids, net='%', sta='%', chan='%', loc='%', radius=None,  data_format='sac', as_stream=True, keep_files=False):
        """ Download triggered waveforms from STP using the TRIG command.
        """

        if not self.connected:
            print('STP is not connected')
            return None

        base_cmd = 'trig '
        if net != '%':
            base_cmd += ' -net {}'.format(net)
        if sta != '%':
            base_cmd += ' -sta {}'.format(sta)
        if chan != '%':
            base_cmd += ' -chan {}'.format(chan)
        if loc != '%':
            base_cmd += ' -loc {}'.format(loc)
        if radius is not None:
            base_cmd += ' -radius {}'.format(radius)
        
        result = {}
        for ev in evids:
            cmd = "{} {}\n".format(base_cmd, ev)

            result[ev] = self._send_data_command(cmd, data_format, as_stream)
        self._end_command()
        
        return result


    def get_continuous(self, net='%', sta='%', chan='%', loc='%', data_format='sac', as_stream=True, keep_files=False):
        pass


    def _get_event_phase(self, cmd, evids, times=None, lats=None, lons=None, mags=None, depths=None, types=None, gtypes=None, output_file=None, is_xml=False):
        """ Helper function that handles the event and phase commands, 
        which have similar syntax.
        """

        if output_file is not None:
            cmd += ' -f {} '.format(output_file)
        if evids is not None:
            evids_str = [str(e) for e in evids]
            cmd += ' -e {} '.format(' '.join(evids_str))
        else:
            if times is not None:
                start_time = times[0].strftime("%Y/%m/%d,%H:%M:%S.%f")
                end_time = times[1].strftime("%Y/%m/%d,%H:%M:%S.%f")
                cmd += ' -t0 {} {}'.format(start_time, end_time)
            if lats is not None:
                cmd += ' -lat {} {}'.format(lats[0], lats[1])
            if lons is not None:
                cmd += ' -lon {} {}'.format(lons[0], lons[1])
            if mags is not None:
                cmd += ' -mag {} {}'.format(mags[0], mags[1])
            if depths is not None:
                cmd += ' -depth {} {}'.format(depths[0], depths[1])
            if types is not None:
                cmd += ' -type {} '.format(','.join(types))
            if gtypes is not None:
                cmd += ' -gtype {} '.format(','.join(gtypes))
            
        if self.verbose:
            print(cmd)
        cmd += '\n'
        if self.verbose:
            print('Sending command')
        self.socket.send(cmd.encode('utf-8'))
        self._receive_data()
        
                
    def get_events(self, evids=None, times=None, lats=None, lons=None, mags=None, depths=None, types=None, gtypes=None, output_file=None, is_xml=False):
        """ Download events from STP using the EVENT command.
        """

        if not self.connected:
            print('STP is not connected')
            return None
        self._get_event_phase('event', evids, times, lats, lons, mags, depths, types, gtypes, output_file)
        catalog = Catalog()
        for line in self.message.splitlines():
            if not line.startswith('#'):
                catalog.append(utils.make_event(line))
        self._end_command()
        return catalog

        
    def get_phases(self, evids=None, times=None, lats=None, lons=None, mags=None, depths=None, types=None, gtypes=None, output_file=None, is_xml=False):
        """ Download events and phase picks from STP using the PHASE command.
        """

        if not self.connected:
            print('STP is not connected')
            return None
        self._get_event_phase('phase', evids, times, lats, lons, mags, depths, types, gtypes, output_file)
        evid_pattern = re.compile('^[1-9]+')
        catalog = Catalog()
        event = None
        for line in self.message.splitlines():
            line = line.strip()
            if not line.startswith('#'):
                #print(evid_pattern.match(line))
                if evid_pattern.match(line) is not None:
                    #print('Creating event')
                    event = utils.make_event(line)
                    catalog.append(event)
                else:
                    #print('Creating phase pick')
                    pick = utils.make_pick(line.strip(), event.origins[0].time)
                    if event is None:
                        raise Exception('Error parsing phase output')
                    event.picks.append(pick)
        self._end_command()    
        return catalog


    def disconnect(self):
        """ Disconnect from the STP server.
        """

        if self.fdr:
            self.fdr.close()
        if self.socket:
            self.socket.close()
        self.connected = False

if __name__ == '__main__':
    stp = STPClient('athabasca.gps.caltech.edu', 9999)
    stp.connect(True)
    stp.disconnect()
