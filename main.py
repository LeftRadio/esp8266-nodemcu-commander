#!python3

import os
import sys
import threading
import subprocess
from queue import Queue
from PyQt5 import QtCore, uic
from PyQt5.QtCore import Qt, QModelIndex, pyqtSlot, QPoint
from PyQt5.QtGui import QColor, QIcon, QFont
from PyQt5.QtWidgets import ( QMainWindow, QApplication, QStyleFactory,
                              QGraphicsScene, QDesktopWidget, QFileDialog,
                              QMessageBox, QSplitter, QTableWidgetItem,
                              QMenu, QAction, QLabel )
import ui_rc
from time import time, sleep
from datetime import datetime
from qsci_editor import QsciEditor
from comm_filemanager import CommanderFileManager
from nodeserial import NodeSerialCommander
from io import StringIO as std_str_io
from settings import MainSettings


__version__ = 1.057

# ------------------------------------------------------------------------------
# ESP_Files_ContextMenu
# ------------------------------------------------------------------------------
class ESP_Files_ContextMenu(QMenu):

    def __init__(self, parent = None):
        super(ESP_Files_ContextMenu, self).__init__(parent)
        pass
    #
    def fonts_context(self, lst_item, id_name):
        """
        Context menu for NGL font list_view
        """
        if lst_item:

            listItem_name = lst_item.text()

            self.copyname_act = QAction ( 'Copy Name', self )
            self.read_act = QAction ( 'Read %s \'%s\'' % (id_name, listItem_name), self )
            self.save_act = QAction ( 'Save to...', self )
            self.del_act = QAction ( 'Delete \'%s\'' % listItem_name, self )
            self.del_all_act = QAction ( 'Delete all', self )

            self.addAction(self.copyname_act)
            self.addAction(self.read_act)
            self.addAction(self.save_act)
            self.addAction(self.del_act)
            self.addAction(self.del_all_act)

        return self


# main window class
class MainWindow(QMainWindow):

    log_signal = QtCore.pyqtSignal(str, str)
    wrline_signal = QtCore.pyqtSignal(str)

    def __init__(self, parent = None):
        super(MainWindow, self).__init__(parent)

        # --- load main ui window
        self.uic = uic.loadUi('main.ui', self)

        self.settings = MainSettings()

        # --- create qsci lua/python editor widgets
        self.codeEdit = QsciEditor()
        self.codeEdit.set_lexer('Lua')
        self.codeEdit.setMinimumSize(420, 300)
        self.codeEditPython = QsciEditor()
        self.codeEditPython.set_lexer('Python')
        self.codeEditPython.setMinimumSize(420, 80)
        self.codeEditPython.setText( '\n'.join(["print('hello ESP!')",
                                        "import telnetlib",
                                        "telnet = telnetlib.Telnet()",
                                        "print('telnet: ', telnet)"]) )
        # add editors widgets to layout
        self.vLayoutLua.addWidget(QSplitter())
        self.vLayoutLua.addWidget(self.codeEdit)
        self.vLayoutPython.addWidget(self.codeEditPython)
        # editors signals/slots
        self.btnESP_RunAll.clicked.connect(self.serial_send)
        self.btnESP_WriteAll.clicked.connect(self.serial_send)
        self.btnPythonRun.clicked.connect(self.python_run)
        self.btnLineToEditor.clicked.connect(self.line_to_editor)

        # --- filemanager
        self.filemanager = CommanderFileManager()
        self.treeFiles.setModel(self.filemanager.files_tree_model)
        self.btnEdit_fileSave.clicked.connect(self.fileSave)
        self.btnEdit_fileSaveAs.clicked.connect(self.fileSaveAs)
        # filemanager signals/slots
        self.treeFiles.doubleClicked.connect(self.fileSelect)

        # ---
        self.btnFilesWriteESP.clicked.connect( self.serial_send )
        self.listFilesESP.cellDoubleClicked.connect( self.select_ESPfile )
        self.listFilesESP.customContextMenuRequested.connect( self.esp_files_contextMenu )
        self.btnFilesESPUpdate.clicked.connect( self.serial_send )

        # --- node serial port
        port, baud, lndelay = self.settings.serial()
        self.nodecommander = NodeSerialCommander(port, baud, lndelay, self.log_signal.emit)
        # update avables ports
        self.serial_updateports()
        # fill serial params
        self.serial_fillsettings()
        # serial signals/slots
        self.btnSerialUpdate.clicked.connect( self.serial_updateports )
        self.btnSerialSet.clicked.connect( self.serial_set )
        self.btnSerialSendLine.clicked.connect( self.serial_send )
        self.btnSerialSendReset.clicked.connect( self.serial_send )
        self.btnSerialSendChipID.clicked.connect( self.serial_send )

        # --- node/python console
        family, size_pt = self.settings.console()
        self.fontComboBox_Console.setCurrentFont(QFont(family))
        self.spinBox_ConsoleFontSize.setValue(size_pt)
        self.textBrowserNodeConsole.setFont(QFont(family, size_pt))
        self.fontComboBox_Console.currentFontChanged.connect(self.nodecondole_font)
        self.spinBox_ConsoleFontSize.valueChanged.connect(self.nodeconsole_font_size)

        # --- self signals/slots
        self.log_signal.connect(self.qlog_message)
        self.btnAPIAddCustom.clicked.connect(self.esp_api_add)
        self.btnAPIRemoveCustom.clicked.connect(self.esp_api_add)

        # --- queue, threads, worker
        # Create the queue for threads, threads
        self.nqueue = Queue()
        t = threading.Thread(target=self.worker)
        t.daemon = True  # thread dies when main thread exits.
        t.start()

        # set window to center and show
        window = self.frameGeometry()
        center = QDesktopWidget().availableGeometry().center()
        window.moveCenter(center)
        self.move(window.topLeft())
        self.show()


        # hello message
        self.start_msg = [
            'ESP8266 NodeMCU utility, ver: %.3f' % __version__,
            'Full free open source project',
            'PyQt5 based',
            '---',
            'Author:',
            'Vladislav Kamenev :: LeftRadio',
            'vladislav@inorbit.com',
            'https://github.com/LeftRadio',
            '---',
            'wait commands ...' ]
        self.nqueue.put('start')

    def _clipboard(self, data):
        cmd='echo '+data.strip()+'|clip'
        return subprocess.check_call(cmd, shell=True)

    @pyqtSlot(str, str)
    def qlog_message(self, msg, lvl=''):
        """ """
        lvl_colors = {
            'err':  '#ff6464',
            'warn': '#dcdc8c',
            'ginf': '#ffffff',
            'end':  '#aaff00',
            'inf':  '#77f8be',
            '':     '#d4e0d4'
        }
        txbr = self.textBrowserNodeConsole
        txbr.setTextColor( QColor(lvl_colors[lvl]) )
        txbr.insertPlainText(str(msg) + '\n')
        sb = txbr.verticalScrollBar()
        sb.setValue(sb.maximum())
        # txbr.repaint()
        txbr.update()
        self.statusBar.showMessage('serial operation msg: [ %s ]' % str(msg), 5000)

    @pyqtSlot()
    def serial_updateports(self):
        self.qlog_message('Update avables serial ports...', 'warn')
        ports = self.nodecommander.nodesettings.avablesPorts()
        self.cmBoxSerialName.clear()
        self.cmBoxSerialName.addItems(ports)
        self.qlog_message(ports, 'warn')

    def serial_fillsettings(self):
        # line delay
        self.spinBoxSerialLineDelay.setValue(
            self.nodecommander.nodesettings.linedelay)
        # baudRate lineedit
        self.lnEditSerialBaudRate.setText(
                str(self.nodecommander.nodesettings.baudRate))
        #
        self.esp_api_read()

    @pyqtSlot()
    def serial_set(self):
        # close port
        self.nodecommander.nodeserial.close_port()
        # get current serial settings
        st = self.nodecommander.nodesettings
        # set new values
        st.name = self.cmBoxSerialName.currentText()
        st.baudRate = int(self.lnEditSerialBaudRate.text())
        st.linedelay = self.spinBoxSerialLineDelay.value()
        #
        self.settings.set_serial(st.name, st.baudRate, st.linedelay)
        self.nodecommander.nodeserial.apply_settings(st)
        #
        msg = 'set serial settings: %s, %d' % (st.name, st.baudRate)
        self.qlog_message(msg, 'warn')

    @pyqtSlot()
    def serial_send(self, **kwargv):
        sender = self.sender().objectName()

        if sender == 'btnSerialSendLine':
            self.nodecommander.line( self.lineEditSerialLine.text() )

        elif sender == 'btnSerialSendReset':
            self.nodecommander.line('node.restart()')

        elif 'btnSerialSendChipID' in sender:
            self.nodecommander.line('print(node.chipid())')

        elif sender == 'btnFilesESPUpdate':
            self.listFilesESP.setRowCount(0)
            self.nodecommander.listfiles(callback=self.esp_files_fill)

        elif sender == 'btnESP_RunAll':
            self.nodecommander.runfile( data=self.codeEdit.text() )

        elif sender == 'btnESP_WriteAll':
            nm = self.lineEditLUAFileName.text()
            dt = self.codeEdit.text()
            self.nodecommander.writefile( name=nm, data=dt)

        elif sender == 'btnFilesWriteESP':
            indexes = self.treeFiles.selectedIndexes()
            for i in range(0, len(indexes), 4):
                indx = indexes[i]
                path = self.filemanager.get_path(indx)
                if not os.path.isdir(path):
                    name = os.path.basename(path)
                    data = self.filemanager.open(path)
                    self.nodecommander.writefile(name=name, data=data)

    def esp_files_fill(self, row_data):
        """ """
        col = self.listFilesESP.columnCount()
        row = self.listFilesESP.rowCount()
        self.listFilesESP.setRowCount(row+1)
        name, size = row_data
        self.listFilesESP.setItem(row, 0, QTableWidgetItem(name))
        self.listFilesESP.setItem(row, 1, QTableWidgetItem(size))
        self.listFilesESP.update()

    @pyqtSlot(int, int)
    def select_ESPfile(self, row, col):
        if col > 0:
            return
        name = self.listFilesESP.item(row, col).text()
        self.esp_file_read(name)

    def esp_file_read(self, name):
        self.codeEdit.setText('')
        self.nodecommander.readfile( name=name, callback=self.esp_file_read_callback)
        self.dockWidget_LuaEditor.setWindowTitle(
                'CODE EDITOR  -  %s' % name.lower() )
        self.lineEditLUAFileName.setText(name)
        self.lineEditLUAFileName.update()

    def esp_file_read_callback(self, data):
        """ callback for reading file from esp """
        self.codeEdit.append(data + '\n')

    def esp_file_delete(self, name):
        self.nodecommander.line(
            'file.remove("%s")' % name,
            callback=self.esp_file_delete_callback)

    def esp_file_delete_callback(self,data):
        self.btnFilesESPUpdate.clicked.emit()

    def esp_api_read(self):
        self.cmBoxNodeAPI.clear()
        for item in self.nodecommander.node_api_get():
            if item.startswith('#'):
                self.cmBoxNodeAPI.insertSeparator(
                    self.cmBoxNodeAPI.count() )
                self.cmBoxNodeAPI.insertSeparator(
                    self.cmBoxNodeAPI.count() )
            else:
                self.cmBoxNodeAPI.addItem(item)
        self.cmBoxNodeAPI.setCurrentIndex(0)
        self.cmBoxNodeAPI.update()

    @pyqtSlot()
    def esp_api_add(self):
        cmd = self.lineEditSerialLine.text()

        nm =self.sender().objectName()

        if nm == 'btnAPIAddCustom':
            state = self.nodecommander.node_api_add(cmd)
        elif nm == 'btnAPIRemoveCustom':
            state = self.nodecommander.node_api_remove(cmd)
        else:
            self.statusBar.showMessage('err - %s' % nm, 2000)
            return

        if state == 'ok':
            self.esp_api_read()
            msg = 'add/remove custom - \'%s\' command' % cmd
        elif state == 'exist':
            msg = 'not added, command already in list'
        elif state == 'not exist':
            msg = 'nothing remove, command item not in list'
        else:
            msg = 'Error!'

        self.statusBar.showMessage(msg, 2000)

    @QtCore.pyqtSlot(QPoint)
    def esp_files_contextMenu(self, qpoint):
        """
        NGL font listview context menu
        """
        lst_widget = self.listFilesESP
        lst_item = lst_widget.currentItem()

        # create and exec context menu
        menu_cntx = ESP_Files_ContextMenu().fonts_context(lst_item, '')
        action = menu_cntx.exec_( lst_widget.viewport().mapToGlobal(qpoint) )

        if action:

            if 'Copy Name' in action.text():
                self._clipboard(lst_item.text())

            if 'Read' in action.text():
                self.esp_file_read(lst_item.text())

            elif 'Save to' in action.text():
                pass

            elif 'Delete all' in action.text():
                pass

            elif 'Delete' in action.text():
                self.esp_file_delete(lst_item.text())

    def worker(self):
        while True:
            item = self.nqueue.get()
            with threading.Lock():
                if item == 'start':
                    import random
                    for m in self.start_msg:
                        self.log_signal.emit(m, '')
                        sleep(random.uniform(0.05, 0.20))
            self.nqueue.task_done()

    @pyqtSlot()
    def line_to_editor(self):
        self.codeEdit.append(self.lineEditSerialLine.text())

    @pyqtSlot()
    def python_run(self):
        expression = self.codeEditPython.text()

        try:
            old_stdout = sys.stdout
            sys.stdout = sio = std_str_io()

            exec(str(expression))

            sys.stdout = old_stdout
            result = sio.getvalue()
            lv = ''
        except Exception as e:
            result = str(e)
            lv = 'err'
        finally:
            self.log_signal.emit(result, lv)

    @pyqtSlot(QFont)
    def nodecondole_font(self, font):
        font = QFont(font.family(), self.spinBox_ConsoleFontSize.value())
        self.nodeconsole_set_font(font)

    @pyqtSlot(int)
    def nodeconsole_font_size(self, size):
        font = self.fontComboBox_Console.currentFont()
        font.setPointSize(size)
        self.nodeconsole_set_font(font)

    def nodeconsole_set_font(self, font):
        self.textBrowserNodeConsole.setFont(font)
        self.textBrowserNodeConsole.update()
        self.settings.set_console(font.family(), font.pointSize())

    @pyqtSlot(QModelIndex)
    def fileSelect(self, indx):
        """ Select item from files tree view """
        # get selected path
        p = self.filemanager.get_path(indx)
        # if selected is file
        if not os.path.isdir(p):
            # self.dockWidget_LuaEditor._ofilename = p.lower()
            self.dockWidget_LuaEditor.setWindowTitle(
                'CODE EDITOR  -  %s' % p.lower() )
            self.lineEditLUAFileName.setText(os.path.basename(p))
            self.lineEditLUAFileName.update()
            ev = 'file'
            # set file to code editor
            txt = self.filemanager.open(p)
            self.codeEdit.setText(txt)
            self.codeEdit.setModified(False)
        else:
            ev = 'dir'
        # put op message
        self.statusBar.showMessage('files operation: [ open %s \' %s \' ]' % (ev, p), 2000)

    @pyqtSlot()
    def fileSave(self, **kwargv):
        """ save file document """
        # if save as...
        try:
            def_path = os.path.dirname(self.filemanager.file)
        except Exception as e:
            def_path = os.path.dirname(__file__) + '/'
        def_path += self.lineEditLUAFileName.text()

        fp = kwargv.get('filepath', def_path)
        # get text from code editor and save
        state = self.filemanager.save(fp, self.codeEdit.text())
        # state of save operation
        if state:
            if fp == def_path:
                self.codeEdit.setModified(False)
            self.statusBar.showMessage('SUCCESSFUL saved to - \' %s \'' % fp, 5000)
        else:
            self.statusBar.showMessage('ERROR! while save to - \' %s \'' % fp, 5000)
        return state

    def fileSaveAs(self):
        """ save as file document """
        fp, _ = QFileDialog.getSaveFileName(
                            self, "Save as...", None,
                            "LUA files (*.lua);;All Files (*)" )
        if not fp:
            return False

        return self.fileSave(filepath=fp)

    def maybeSave(self):
        """ check modified for working file """
        if self.filemanager.file is None or \
                            not self.codeEdit.isModified() or \
                            self.filemanager.file.startswith(':/'):
            return True

        ret = QMessageBox.warning(self, "Application",
                "The document has been modified.\n"
                "Do you want to save your changes?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)

        if ret == QMessageBox.Save:
            return self.fileSave()
        elif ret == QMessageBox.Cancel:
            return False

        return True

    @pyqtSlot()
    def CloseButtonClicked(self):
        """ """
        self.close()

    def closeEvent(self, e):
        if self.maybeSave():
            self.settings.save()
            e.accept()
        else:
            e.ignore()


# program start here
if __name__ == '__main__':

    app = QApplication(sys.argv)
    QApplication.setStyle(QStyleFactory.create('Fusion'))
    ex = MainWindow()
    sys.exit(app.exec_())
