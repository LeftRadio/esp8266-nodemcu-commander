import sys
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont, QFontMetrics, QColor
from PyQt5.QtWidgets import QLabel
from PyQt5 import Qsci
from PyQt5.Qsci import QsciScintilla, QsciLexerLua

class QsciEditor(QsciScintilla):
    ARROW_MARKER_NUM = 8

    def __init__(self, parent=None):
        super(QsciEditor, self).__init__(parent)

        # Set the default font
        font = QFont('MS Shell Dlg 2', 9)
        self.setFont(font)
        self.setMarginsFont(font)

        # Margin 0 is used for line numbers
        fontmetrics = QFontMetrics(font)
        self.setMarginsFont(font)
        self.setMarginWidth(0, fontmetrics.width("00") + 4)
        self.setMarginLineNumbers(0, True)
        self.setMarginSensitivity(0, True)
        self.setMarginsBackgroundColor(QColor("#e6e2e2"))

        # Brace matching: enable for a brace immediately before or after
        # the current position
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)

        # Current line visible with special background color
        self.setCaretLineVisible(True)
        self.setCaretLineBackgroundColor(QColor("#c0d4d4"))
        self.setCaretForegroundColor(QColor("#fcfffc"))

        self.SendScintilla(QsciScintilla.SCI_STYLESETFONT, 0)
        self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)
        self.SendScintilla(QsciScintilla.SCI_SETVSCROLLBAR, 0)

        self.setMinimumSize(450, 0)

    def set_lexer(self, lex='Lua'):
        lexer = getattr(Qsci, 'QsciLexer' + lex)()
        lexer.setDefaultFont(self.font())
        lexer.setDefaultPaper(QColor("#efefed"))
        lexer.setDefaultColor(QColor("#191919"))
        self.setLexer(lexer)



# start at app for debug
if __name__ == "__main__":

    import sys
    from PyQt5.QtWidgets import ( QMainWindow, QApplication, QStyleFactory,
                              QGraphicsScene, QDesktopWidget )

    app = QApplication(sys.argv)
    editor = QsciEditor()
    editor.show()
    editor.set_lexer('Python')
    editor.setText(open(sys.argv[0]).read())
    app.exec_()
