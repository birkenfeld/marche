#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ server control daemon
# Copyright (c) 2015 by the authors, see LICENSE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Georg Brandl <g.brandl@fz-juelich.de>
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

from marche.gui.util import loadUi
from marche.gui.client import Client, PollThread
from marche.jobs import STATE_STR, RUNNING, DEAD, STARTING, STOPPING, INITIALIZING
from marche.version import get_version

from PyQt4.QtCore import pyqtSignature as qtsig, Qt
from PyQt4.QtGui import QMainWindow, QWidget, QInputDialog, QColor, QTreeWidget, \
    QTreeWidgetItem, QBrush, QMessageBox


class JobButtons(QWidget):
    def __init__(self, client, service, instance=None, parent=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'job.ui')

        self._client = client
        self._service = service
        self._instance = instance

    @qtsig('')
    def on_startBtn_clicked(self):
        self._client.startService(self._service, self._instance)

    @qtsig('')
    def on_stopBtn_clicked(self):
        self._client.stopService(self._service, self._instance)

    @qtsig('')
    def on_restartBtn_clicked(self):
        self._client.restartService(self._service, self._instance)


class HostTree(QTreeWidget):
    STATE_COLORS = {
        RUNNING:      ('green', ''),
        DEAD:         ('white', 'red'),
        STARTING:     ('blue', ''),
        STOPPING:     ('blue', ''),
        INITIALIZING: ('blue', ''),
    }

    def __init__(self, parent, client):
        QTreeWidget.__init__(self, parent)
        self._client = client
        self._pollThread = PollThread(client.host, client.port)
        self._pollThread.newData.connect(self.updateStatus)
        self._pollThread.start()

        self.setColumnCount(4)
        self.headerItem().setText(0, 'Service')
        self.headerItem().setText(1, 'Status')
        self.headerItem().setText(2, 'Control')
        self.headerItem().setText(3, '')
        self._items = {}
        self.fill()

        self.expandAll()
        self.resizeColumnToContents(0)
        self.setColumnWidth(0, self.columnWidth(0) * 1.4)
        self.resizeColumnToContents(2)
        width = sum([self.columnWidth(i) for i in range(self.columnCount())])
        self.setMinimumWidth(width+2)
        # self.collapseAll()

    def fill(self):
        services = self._client.getServices()

        for service, instances in services.iteritems():
            serviceItem = QTreeWidgetItem([service])
            serviceItem.setForeground(1, QBrush(QColor('white')))
            serviceItem.setTextAlignment(1, Qt.AlignCenter)
            serviceItem.setFlags(Qt.ItemIsEnabled)
            self.addTopLevelItem(serviceItem)

            if not instances:
                self._items[service] = serviceItem
                btn = JobButtons(self._client, service)
                self.setItemWidget(serviceItem, 2, btn)
            else:
                self._items[service] = {}
                for instance in instances:
                    instanceItem = QTreeWidgetItem([instance])
                    instanceItem.setForeground(1, QBrush(QColor('white')))
                    instanceItem.setTextAlignment(1, Qt.AlignCenter)
                    instanceItem.setFlags(Qt.ItemIsEnabled)
                    serviceItem.addChild(instanceItem)

                    btn = JobButtons(self._client, service, instance)
                    self.setItemWidget(instanceItem, 2, btn)

                    self._items[service][instance] = instanceItem

    def updateStatus(self, service, instance, status):
        item = self._items[service]

        if instance:
            item = self._items[service][instance]

        colors = self.STATE_COLORS.get(status, ('gray', ''))
        item.setForeground(1, QBrush(QColor(colors[0])) if colors[0] else QBrush())
        item.setBackground(1, QBrush(QColor(colors[1])) if colors[1] else QBrush())
        item.setText(1, STATE_STR[status])


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        loadUi(self, 'mainwindow.ui')

        self.resize(800, 500)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 5)
        self.setWindowTitle('Marche')

        self._clients = {}

        self.addHost('localhost:8124')
        self.openHost('localhost:8124')

    @qtsig('')
    def on_actionAdd_host_triggered(self):
        addr, accepted = QInputDialog.getText(self, 'Add host', 'New host:')
        if accepted:
            self.addHost(addr)

    @qtsig('')
    def on_actionAbout_triggered(self):
        QMessageBox.about(
            self, 'About Marche GUI',
            '''
            <h2>About Marche GUI</h2>
            <p style="font-style: italic">
              (C) 2015 MLZ instrument control
            </p>
            <p>
              Marche GUI is a graphical interface for the Marche process control system.
            </p>
            <h3>Authors:</h3>
            <ul>
              <li>Copyright (C) 2015
                <a href="mailto:g.brandl@fz-juelich.de">Georg Brandl</a></li>
              <li>Copyright (C) 2015
                <a href="mailto:alexander.lenz@frm2.tum.de">Alexander Lenz</a></li>
            </ul>
            <p>
              Marche is published under the
              <a href="http://www.gnu.org/licenses/gpl.html">GPL
                (GNU General Public License)</a>
            </p>
            <p style="font-weight: bold">
              Version: %s
            </p>
            ''' % get_version())

    def on_hostListWidget_currentItemChanged(self, current, previous):
        self.openHost(current.text())

    def addHost(self, addr):
        if ':' not in addr:
            addr += ':8124'
        host, port = addr.split(':')
        self._clients[addr] = Client(host, port)

        self.hostListWidget.addItem(addr)

    def removeHost(self, addr):
        if addr in self._clients:
            del self._clients[addr]

        item = self.hostListWidget.findItem(addr)
        self.hostListWidget.takeItem(item)

    def openHost(self, addr):
        prev = self.surface.layout().takeAt(0)

        if prev:
            prev.widget().hide()
            prev.widget().deleteLater()

        widget = HostTree(self, self._clients[addr])

        self.surface.layout().addWidget(widget)
        widget.show()