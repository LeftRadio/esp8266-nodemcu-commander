#!python3

import sys
import os
from PyQt5.QtCore import QDir
from PyQt5.QtWidgets import QFileSystemModel

class CommanderFileManager(object):
    """docstring for FileManager"""
    def __init__(self):

        self.files_tree_model = QFileSystemModel()
        self.set_filter()
        self.files_tree_model.setRootPath(os.path.abspath(__file__))
        self._file = None

    def set_filter(self, filter_list=['*.lua']):
        self.files_tree_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.AllEntries)
        self.files_tree_model.setNameFilters(filter_list)
        self.files_tree_model.setNameFilterDisables(0)

    def get_path(self, index):
        return self.files_tree_model.filePath(index)

    def open(self, path):
        try:
            with open(path, 'rt') as f:
                text = f.read()
                self._file = path
                return text
        except Exception as e:
            print(e)
        return None

    def save(self, fp, text):
        """ save file document """
        try:
            with open(fp, 'wt') as f:
                f.write(text)
        except Exception as e:
            return False

        return True

    @property
    def file(self):
        return self._file
    @file.setter
    def file(self, f):
        self._file = f


# debug
if __name__ == '__main__':

    from PyQt5.QtWidgets import QMainWindow, QApplication, QTreeView

    class MainForm(QMainWindow):
        def __init__(self, parent=None):
            super(MainForm, self).__init__(parent)
            self.filemanager = CommanderFileManager()
            self.view = QTreeView()
            self.view.setModel(self.filemanager.files_tree_model)
            self.setCentralWidget(self.view)

    app = QApplication(sys.argv)
    form = MainForm()
    form.show()
    form.filemanager.set_filter(['*.txt'])
    form.filemanager.set_filter(['*.png'])
    app.exec_()