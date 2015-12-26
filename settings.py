#!python3

from configparser import ConfigParser

class MainSettings(object):
    """docstring for MainSettings"""
    def __init__(self):
        # instantiate
        self.config = ConfigParser()
        self.load()
        #
        self.serial()
        self.console()

    def load(self):
        """ """
        self.config.read('settings.ini')

    def save(self):
        with open('settings.ini', 'w') as f:
            self.config.write(f)

    def serial(self):
        config = self.config
        try:
            port = config.get('serial', 'port')
            baud = config.getint('serial', 'baud')
            linedelay = config.getint('serial', 'line_delay')
            return (port, baud, linedelay)
        except Exception as e:
            config.add_section('serial')
            config.set('serial', 'port', 'COM5')
            config.set('serial', 'baud', '9600')
            config.set('serial', 'line_delay', '200')
            return ('COM5', 9600, 200)

    def set_serial(self, port, baud, linedelay):
        try:
            self.config.get('serial', 'port')
        except Exception as e:
            self.config.add_section('serial')
        self.config.set('serial', 'port', port)
        self.config.set('serial', 'baud', str(baud))
        self.config.set('serial', 'line_delay', str(linedelay))

    def console(self):
        config = self.config
        try:
            family = config.get('console', 'font_family')
            size = config.getint('console', 'font_size')
            return (family, size)
        except Exception as e:
            config.add_section('console')
            config.set('console', 'font_family', 'MS Shell Dlg 2')
            config.set('console', 'font_size', '8')
            return ('MS Shell Dlg 2', 8)

    def set_console(self, family, size):
        try:
            self.config.get('console', 'font_family')
        except Exception as e:
            self.config.add_section('console')
        self.config.set('console', 'font_family', family)
        self.config.set('console', 'font_size', str(size))
