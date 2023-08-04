"""
LOOT Warning Checker
====================

The LOOT Warning Checker plugin module.

Copyright (C) 2021-2023 Jonathan Feenstra

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import os
import site
from typing import List

site.addsitedir(os.path.join(os.path.dirname(__file__), "lib"))

from mobase import IPlugin

from .CheckerPlugin import LOOTWarningChecker
from .TogglePlugin import LOOTWarningToggle


def createPlugins() -> List[IPlugin]:
    return [LOOTWarningChecker(), LOOTWarningToggle()]
