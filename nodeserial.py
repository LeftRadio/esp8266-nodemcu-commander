#!python3

from PyQt5.QtCore import QIODevice, pyqtSignal, pyqtSlot
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
import threading
from queue import Queue
from time import time, sleep


QIODevice_names = {
        'QIODevice::NotOpen':   QIODevice.NotOpen,      # The device is not open.
        'QIODevice::ReadOnly':  QIODevice.ReadOnly,     # The device is open for reading.
        'QIODevice::WriteOnly': QIODevice.WriteOnly,    # The device is open for writing. Note that this mode implies Truncate.
        'QIODevice::ReadWrite': QIODevice.ReadWrite,    # The device is open for reading and writing.
        'QIODevice::Append':    QIODevice.Append,       # The device is opened in append mode so that all data is written to the end of the file.
        'QIODevice::Truncate':  QIODevice.Truncate,     # If possible, the device is truncated before it is opened. All earlier contents of the device are lost.
        'QIODevice::Text':      QIODevice.Text,         # When reading, the end-of-line terminators are translated to '\n'.
                                                        # When writing, the end-of-line terminators are translated to the local encoding,
                                                        # for example '\r\n' for Win32.
        'QIODevice::Unbuffered': QIODevice.Unbuffered   # Any buffer in the device is bypassed.
    }

def serial_log(type, lvl='inf'):
    """ logging decorator maker """
    def logdec(func):
        def wrapper(self, *argv, **kwargv):
            res = func(self, *argv, **kwargv)

            if self.log:

                if res == -1 or res == False:
                    l = 'err'
                else:
                    l = lvl

                if type == 'wr':
                    pref = '<<'
                    l = 'warn'
                elif type == 'rd':
                    pref = '>>'
                else:
                    pref = '%s' % type

                msg = '%s %s' % (pref, ' '.join([str(a) for a in argv]))
                self.log(msg.replace('\r\n', ''), l)

            return res
        return wrapper
    return logdec

class NodeSerialSettings(object):
    """docstring for NodeSerialSettings"""
    def __init__(self, **kwargv):
        """ """
        # serial serial port object
        serial = kwargv.get('serial', QSerialPort())
        # settings
        ports = self.avablesPorts()
        if serial.portName() not in ports and len(ports):
            self.name = ports[0]
        else:
            self.name = kwargv.get('name', serial.portName())
        self.baudRate = kwargv.get('baud', serial.baudRate())
        self.dataBits = kwargv.get('databit', serial.dataBits())
        self.parity = kwargv.get('parity', serial.parity())
        self.stopBits = kwargv.get('stopbit', serial.stopBits())
        self.flowControl = kwargv.get('flow', serial.flowControl())
        # send line delay in ms
        self.linedelay = kwargv.get('linedelay', 200)

    def avablesPorts(self):
        ports = QSerialPortInfo.availablePorts()
        return [info.portName() for info in ports]

class NodeSerial(QSerialPort):
    """docstring for NodeSerial"""

    readline_signal = pyqtSignal(str)
    writeline_signal = pyqtSignal(str)

    def __init__(self, parent=None, **kwargv):
        super(NodeSerial, self).__init__(parent)

        self.writeline_data = ''
        self.readline_ready = False
        self.readline_data = ''
        self.workerbreak = 0

        self.readyRead.connect(self.ready_read)
        self.writeline_signal.connect(self.write_data)
        self.log = kwargv.get('log', None)

        # --- queue, threads, worker
        # Create the queue for threads
        self.nqueue = Queue()
        t = threading.Thread(target=self.worker)
        t.daemon = True  # thread dies when main thread exits.
        t.start()

    def apply_settings(self, settings):
        self.setPortName(settings.name)
        self.setBaudRate(settings.baudRate)
        self.setDataBits(settings.dataBits)
        self.setParity(settings.parity)
        self.setStopBits(settings.stopBits)
        self.setFlowControl(settings.flowControl)
        self.linedelay = settings.linedelay

    def open_port(self, name):
        # close previosly used port set new name
        if name != self.portName():
            self.close_port()
            self.setPortName(name)
        # try open
        if not self.isOpen():
            return self.open('QIODevice::ReadWrite', name)
        return True

    def close_port(self):
        if self.isOpen():
            self.close(self.portName())
        return True

    @serial_log('OPEN', lvl='ginf')
    def open(self, dev, name):
        return super().open(QIODevice_names[dev])

    @serial_log('CLOSE', lvl='ginf')
    def close(self, port):
        super().close()

    @serial_log('wr')
    @pyqtSlot(str)
    def write_data(self, data):
        if self.open_port(self.portName()):
            self.workerbreak = self.write(data)
            return
        self.workerbreak = -1

    @pyqtSlot()
    def ready_read(self):
        try:
            data = self.readAll()
            read = data.data().decode('windows-1251')
        except Exception as e:
            self.log(str(e), 'err')
            self.workerbreak = -1
            return

        self.readline_data += read
        indx = self.readline_data.rfind('\r\n')
        if indx != -1:
            self.ready_readline(self.readline_data[:indx].replace('>', ''))
            self.readline_data = self.readline_data[indx+2:]

    @serial_log('rd')
    def ready_readline(self, data):
        self.readline_ready = True
        self.readline_signal.emit(data)

    def write_line(self, string):
        self.nqueue.join()
        self.readline_data = ''
        self.writeline_data = string
        self.nqueue.put('writelines')

    def handle_error(self, error):
        if error == QSerialPort.ResourceError:
            self.closePort()

    def worker(self):
        while True:
            item = self.nqueue.get()
            with threading.Lock():
                if item == 'writelines':
                    # print('writelines')
                    for s in self.writeline_data.split('\r\n'):
                        if self.workerbreak == -1:
                            break
                        # print('l:', s)
                        # write line signal
                        self.writeline_signal.emit(s + '\r\n')
                        st = time()
                        # wait nodemcu respond
                        while self.readline_ready is not True:
                            if time() - st > 4:
                                self.log('Respond timeout ):', 'err')
                                break
                        # print('l0:', s)
                        sleep(self.linedelay/1000)
                        # print('l1:', s)

                    # reset read state and r/w lines data
                    self.readline_ready = False
                    self.workerbreak = 0
                    self.writeline_data = ''

            self.nqueue.task_done()
            # print('self.nqueue.task_done()')
            self.workerbreak = False

class NodeCMD(object):
    """docstring for NodeCMD_Base"""
    def __init__(self, req, callback):
        self.req = req.replace(r'\r', r'\\r').replace(r'\n', r'\\n')
        self.callback = callback

    def read(self, data):
        if self.callback is not None:
            self.callback(data)

class NodeCMD_FilesList(NodeCMD):
    """docstring for NodeCMD_FileList"""
    def __init__(self, callback):
        self.id_name = '$n_'
        self.id_size = '$s_'
        req = ( 'l = file.list()\r\n'
                'for k,v in pairs(l) do\r\n'
                '    print("%s"..k..",%s"..v)\r\n'
                'end\r\n' ) % (self.id_name, self.id_size)
        super(NodeCMD_FilesList, self).__init__(req, callback)

    def read(self, data):
        """ """
        if '.lua' in data:
            if self.id_name in data and self.id_size in data:
                indx_name = data.find(self.id_name)
                indx_size = data.find(self.id_size)
                retv = ( data[indx_name + len(self.id_name) : indx_size - 1],
                         data[indx_size + len(self.id_size) : ] )
                if self.callback is not None:
                    self.callback(retv)

class NodeCMD_FileRead(NodeCMD):
    """docstring for NodeCMD_FileRead"""
    def __init__(self, name, callback):
        self.startcapt = False

        req = ( 'filename = "%s"\r\n'
                'file.open(filename,"r")\r\n'
                'txt = ""\r\n'
                'repeat\r\n'
                '  line = file.readline()\r\n'
                '  if (line~=nil) then txt = txt .. line end\r\n'
                'until line == nil\r\n'
                'file.close()\r\n'
                'print(txt)\r\n' ) % name
        super(NodeCMD_FileRead, self).__init__(req, callback)

    def read(self, data):
        """ """
        if self.startcapt == True:
            if self.callback is not None:
                self.callback(data)
        elif 'print(txt)' in data:
            self.startcapt = True

class NodeCMD_FileRun(NodeCMD):
    """docstring for NodeCMD_FileRun"""
    def __init__(self, data):
        super(NodeCMD_FileRun, self).__init__(data, None)
        req = ''
        for line in self.req.split('\n'):
            req += line.replace("'", "\"") + '\r\n'
        self.req = req

class NodeCMD_WriteFile(NodeCMD):
    """docstring for NodeCMD_WriteFile"""
    def __init__(self, name, data):
        super(NodeCMD_WriteFile, self).__init__(data, None)

        req = ( 'file.remove("{name}")\r\n'
                'file.open("{name}","w")\r\n' ).format(name=name)
        for line in self.req.split('\n'):
            req += "file.writeline('%s')" % (line.replace("'", r"\'")) + '\r\n'
        req += 'file.close()\r\n'
        self.req = req

    def read(self, data):
        """ """
        pass

class NodeSerialCommander(object):
    """docstring for NodeSerialCommander"""
    def __init__(self, name, baud, linedelay, log=None):

        self.cmd = None
        self.log = log
        self.nodesettings = NodeSerialSettings(
            name=name,
            baud=baud,
            linedelay=linedelay )
        self.nodeserial = NodeSerial(log=self.log)
        self.nodeserial.apply_settings(self.nodesettings)
        self.nodeserial.readline_signal.connect(self.recive)

        self.node_api_file = 'node_api.txt'
        self.node_user_file = 'node_user.txt'

    def open_api(self, name):
        api = []
        with open(name, 'rt') as f:
            for ln in f.read().split('\n'):
                if ln.strip() != '':
                    api.append(ln.strip())
        return api

    def save_api(self, name, data):
        with open(name, 'wt', encoding='utf-8') as f:
            f.write(data)

    def node_api_get(self):
        api = self.open_api(self.node_user_file)
        api += self.open_api(self.node_api_file)
        return api

    def node_api_add(self, cmd):
        data = self.open_api(self.node_user_file)
        if cmd not in data:
            data.append(cmd)
            data = '\r\n'.join(data)
            self.save_api(self.node_user_file, data)
            return 'ok'
        return 'exist'

    def node_api_remove(self, cmd):
        data = self.open_api(self.node_user_file)
        if cmd in data:
            data.remove(cmd)
            data = '\r\n'.join(data)
            self.save_api(self.node_user_file, data)
            return 'ok'
        return 'not exist'

    @pyqtSlot(str)
    def recive(self, data):
        if self.cmd is not None:
            self.cmd.read(data)

    def line(self, data, **kwargv):
        self.cmd = NodeCMD(data, kwargv.get('callback', None))
        self.nodeserial.write_line(self.cmd.req)

    def listfiles(self, **kwargv):
        self.cmd = NodeCMD_FilesList( kwargv.get('callback', None) )
        self.nodeserial.write_line(self.cmd.req)

    def readfile(self, **kwargv):
        self.cmd = NodeCMD_FileRead( kwargv.get('name', ''), kwargv.get('callback', None) )
        self.nodeserial.write_line(self.cmd.req)

    def runfile(self, **kwargv):
        self.cmd = NodeCMD_FileRun( kwargv.get('data', '') )
        self.nodeserial.write_line(self.cmd.req)

    def writefile(self, **kwargv):
        self.cmd = NodeCMD_WriteFile( kwargv.get('name', ''), kwargv.get('data', '') )
        self.nodeserial.write_line(self.cmd.req)
