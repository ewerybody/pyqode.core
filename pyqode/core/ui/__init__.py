#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 Colin Duquesnoy
#
# This file is part of pyQode.
#
# pyQode is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# pyQode is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with pyQode. If not, see http://www.gnu.org/licenses/.
#
"""
This package contains the ui files and their compiled version.

.. warning: To make it easy to use the *.ui and *.qrc with all python version
            and different qt bindings, we compile the ui and qrc file using
            pyuic4/pyrcc4 (with -py3 switchà then manually edit those files
            to import QtCore and QtGui from pyqode.qt instead of PyQt4.

            The compile_ui script automates this task, simply run it to update
            all *.ui/*.qrc.
"""
