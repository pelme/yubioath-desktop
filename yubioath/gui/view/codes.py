# Copyright (c) 2014 Yubico AB
# All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Additional permission under GNU GPL version 3 section 7
#
# If you modify this program, or any covered work, by linking or
# combining it with the OpenSSL project's OpenSSL library (or a
# modified version of that library), containing parts covered by the
# terms of the OpenSSL or SSLeay licenses, We grant you additional
# permission to convey the resulting work. Corresponding Source for a
# non-source form of such a combination shall include the source code
# for the parts of OpenSSL used as well as that of the covered work.

from PySide import QtGui, QtCore
from .. import messages as m
from ..controller import CredentialType
from yubioath.yubicommon.qt.utils import connect_once
from time import time


TIMELEFT_STYLE = """
QProgressBar {
  padding: 1px;
}
QProgressBar::chunk {
  background-color: #2196f3;
  margin: 0px;
  width: 1px;
}
"""


class TimeleftBar(QtGui.QProgressBar):
    expired = QtCore.Signal()

    def __init__(self):
        super(TimeleftBar, self).__init__()

        self.setStyleSheet(TIMELEFT_STYLE)
        self.setMaximumHeight(8)
        self.setInvertedAppearance(True)
        self.setRange(0, 30000)
        self.setValue(0)
        self.setTextVisible(False)

        self._timer = 0
        self._timeleft = 0

    def set_timeleft(self, millis):
        self._timeleft = max(0, millis)
        self.setValue(min(millis, self.maximum()))
        if self._timer == 0 and millis > 0:
            self._timer = self.startTimer(250)
        elif self._timer != 0 and millis <= 0:
            self.killTimer(self._timer)
            self._timer = 0

    def timerEvent(self, event):
        self.set_timeleft(max(0, self._timeleft - 250))
        if self._timeleft == 0:
            self.expired.emit()


class CodeMenu(QtGui.QMenu):

    def __init__(self, parent):
        super(CodeMenu, self).__init__(parent)
        self.cred = parent.cred

        self.addAction(m.action_delete).triggered.connect(self._delete)

    def _delete(self):
        res = QtGui.QMessageBox.warning(self, m.delete_title,
                                        m.delete_desc_1 % self.cred.name,
                                        QtGui.QMessageBox.Ok,
                                        QtGui.QMessageBox.Cancel)
        if res == QtGui.QMessageBox.Ok:
            self.cred.delete()


class Code(QtGui.QWidget):

    def __init__(self, cred, timer, on_change):
        super(Code, self).__init__()
        self.cred = cred
        self._on_change = on_change
        self.cred.changed.connect(self._draw)
        self.timer = timer
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

        self._build_ui()

    def _build_ui(self):
        layout = QtGui.QHBoxLayout(self)

        labels = QtGui.QVBoxLayout()
        self._name_lbl = QtGui.QLabel(self.cred.name)
        self._name_lbl.setMinimumWidth(10)
        labels.addWidget(self._name_lbl)
        self._code_lbl = QtGui.QLabel()
        labels.addWidget(self._code_lbl)
        layout.addLayout(labels)
        layout.addStretch()

        self._calc_btn = QtGui.QPushButton(QtGui.QIcon(':/calc.png'), None)
        self._calc_btn.clicked.connect(self._calc)
        layout.addWidget(self._calc_btn)
        if self.cred.cred_type not in [CredentialType.TOUCH,
                                       CredentialType.HOTP]:
            self._calc_btn.setVisible(False)

        self._copy_btn = QtGui.QPushButton(QtGui.QIcon(':/copy.png'), None)
        self._copy_btn.clicked.connect(self._copy)
        layout.addWidget(self._copy_btn)

        self.timer.time_changed.connect(self._draw)

        self._draw()

    @property
    def expired(self):
        return self.cred.code.timestamp < self.timer.time

    def _draw(self):
        if self.expired:
            name_fmt = '<b style="color: gray;">%s</b>'
        else:
            name_fmt = '<b>%s</b>'
        if self.cred.cred_type is CredentialType.TOUCH:
            self._calc_btn.setEnabled(self.expired)
        self._code_lbl.setText(name_fmt % (self.cred.code.code))
        self._copy_btn.setEnabled(bool(self.cred.code.code))
        self._on_change()

    def _copy(self):
        QtCore.QCoreApplication.instance().clipboard().setText(
            self.cred.code.code)

    def _calc(self):
        if self.cred.cred_type is CredentialType.HOTP:
            self._calc_btn.setDisabled(True)
            QtCore.QTimer.singleShot(5000,
                                     lambda: self._calc_btn.setEnabled(True))
        self.cred.calculate()

    def _menu(self, pos):
        CodeMenu(self).popup(self.mapToGlobal(pos))

    def mouseDoubleClickEvent(self, event):
        if event.button() is QtCore.Qt.LeftButton:
            if (not self.cred.code.code or self.expired) and \
                    self.cred.cred_type in [CredentialType.HOTP,
                                            CredentialType.TOUCH]:
                connect_once(self.cred.changed, self._copy)
                self.cred.calculate()
                self.window().close()
            else:
                self._copy()  # TODO: Type code out with keyboard?
                self.window().close()
        event.accept()


class CodesList(QtGui.QWidget):

    def __init__(self, timer, credentials=[], on_change=None):
        super(CodesList, self).__init__()

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for cred in credentials:
            layout.addWidget(Code(cred, timer, on_change))
            line = QtGui.QFrame()
            line.setFrameShape(QtGui.QFrame.HLine)
            line.setFrameShadow(QtGui.QFrame.Sunken)
            layout.addWidget(line)

        if not credentials:
            no_creds = QtGui.QLabel(m.no_creds)
            no_creds.setAlignment(QtCore.Qt.AlignCenter)
            layout.addStretch()
            layout.addWidget(no_creds)
            layout.addStretch()

        layout.addStretch()


class CodesWidget(QtGui.QWidget):

    def __init__(self, controller):
        super(CodesWidget, self).__init__()

        self._controller = controller
        controller.refreshed.connect(self.refresh)
        controller.timer.time_changed.connect(self.refresh_timer)

        self._build_ui()
        self.refresh()
        self.refresh_timer()

    def _build_ui(self):
        layout = QtGui.QVBoxLayout(self)
        self._timeleft = TimeleftBar()
        layout.addWidget(self._timeleft)

        self._scroll_area = QtGui.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOn)
        self._scroll_area.setWidget(QtGui.QWidget())
        layout.addWidget(self._scroll_area)

    def refresh_timer(self, timestamp=None):
        if timestamp is None:
            timestamp = self._controller.timer.time
        if self._controller.has_expiring(timestamp):
            self._timeleft.set_timeleft(1000 * (timestamp + 30 - time()))
        else:
            self._timeleft.set_timeleft(0)

    def refresh(self):
        self._scroll_area.takeWidget().deleteLater()
        creds = self._controller.credentials
        self._scroll_area.setWidget(
            CodesList(self._controller.timer, creds or [], self.refresh_timer))
        w = self._scroll_area.widget().minimumSizeHint().width()
        w += self._scroll_area.verticalScrollBar().width()
        self._scroll_area.setMinimumWidth(w)
