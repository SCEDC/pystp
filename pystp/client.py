import socket
import struct
import os
import obspy.core
from obspy.core import Stream


VALID_FORMATS = ['sac', 'mseed', 'seed', 'ascii', 'v0', 'v1']

class STPClient:
    
    def __init__(self, host, port, output_dir='.', verbose=False):
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
        #self.base_dir = base_dir   # Directory where output will be written

    def _send_sample(self):
        """ Sends the integer 2 to the server
        to verify endianness.
        """

        two = struct.Struct('I').pack(2)
        nbytes = self.socket.send(two)
        

    def _read_message(self):
        """ Reads text sent from the STP server delimited
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
                print(self._read_message(), end='')
            
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
        """ Opens socket connection to STP server.
        """

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.fdr = self.socket.makefile(mode='rb', newline='\n')

        self.socket.sendall(b'STP stpisgreat 1.6.3 stpc\n')
       
        line = self.fdr.readline()
        if line != b'CONNECTED\n':
            raise Exception('Failed to connect')

        self._send_sample()

        self._set_motd()
        if show_motd:
            print(self.motd, end='')


    def _send_data_command(self, cmd, data_format, as_stream=True, keep_files = False):
        data_format = data_format.lower()
        if data_format not in VALID_FORMATS:
            print('Invalid data format')
            return
            # TODO: Raise exception
        if self.verbose:
            print("data_format={} cmd={}".format(data_format, cmd))
        self.socket.sendall('{}\n'.format(data_format).encode('utf-8'))
        self._receive_data()
        self.socket.sendall(cmd.encode('utf-8'))
        self._receive_data()        

        waveform_stream = None
        if as_stream:
            waveform_stream = Stream()
            for f in self.recent_files:
                try:
                    print('Reading {}'.format(f))
                    tr = obspy.core.read(f)
                    waveform_stream += tr
                except TypeError:
                    print('{} is in unknown format. Skipping.'.format(f))
                
                print("keep_files: {}".format(keep_files))
                if not keep_files:
                    print("Removing {} after reading".format(f))
                    os.remove(f)
        
        return waveform_stream

    def _end_command(self):
        """ Perform cleanup after an STP command is ended.
        """
        if self.fdout:
            self.fdout.close()
        self.recent_files.clear()


    def get_trig(self, evid, net='%', sta='%', chan='%', loc='%', data_format='sac', as_stream=True, keep_files=False):
        cmd = 'trig {}'.format(evid)
        if net != '%':
            cmd += ' -net {}'.format(net)
        if sta != '%':
            cmd += ' -sta {}'.format(sta)
        if chan != '%':
            cmd += ' -chan {}'.format(chan)
        if loc != '%':
            cmd += ' -loc {}'.format(loc)
        cmd += '\n'

        result = self._send_data_command(cmd, data_format, as_stream)
        self._end_command()
        
        return result


    def get_continuous(self, net='%', sta='%', chan='%', loc='%', data_format='sac', as_stream=True, keep_files=False):
        pass


    def _get_event_phase(self, cmd, evids, times=None, lat=None, lon=None, depth=None, etype=None, gtype=None, output_file=None, is_xml=False):
        """ Handles the event and phase commands, which have similar syntax.
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
            if lat is not None:
                cmd += ' -lat {} {}'.format(lat[0], lat[1])
            if lon is not None:
                cmd += ' -lon {} {}'.format(lon[0], lon[1])
            if depth is not None:
                cmd += ' -depth {} {}'.format(depth[0], depth[1])
            if etype is not None:
                cmd += ' -type {} '.format(','.join(etype))
            if gtype is not None:
                cmd += ' -gtype {} '.format(','.join(gtype))
            
        if self.verbose:
            print(cmd)
        cmd += '\n'
        if self.verbose:
            print('Sending command')
        self.socket.send(cmd.encode('utf-8'))
        self._receive_data()

        self._end_command()        
    

    def get_events(self, evids=None, times=None, lat=None, lon=None, depth=None, etype=None, gtype=None, output_file=None, is_xml=False):
        self._get_event_phase('event', evids, times, lat, lon, depth, etype, gtype, output_file)


    def get_phases(self, evids=None, times=None, lat=None, lon=None, depth=None, etype=None, gtype=None, output_file=None, is_xml=False):
        self._get_event_phase('phase', evids, times, lat, lon, depth, etype, gtype, output_file)


    def disconnect(self):
        """ Closes file handles and socket connection.
        """
        if self.fdr:
            self.fdr.close()
        if self.socket:
            self.socket.close()


if __name__ == '__main__':
    stp = STPClient('athabasca.gps.caltech.edu', 9999)
    stp.connect(True)
    stp.disconnect()
