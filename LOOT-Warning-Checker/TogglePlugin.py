"""
Toggle Plugin
=============

The plugin to toggle LOOT warnings.

Copyright (C) 2021-2024 Jonathan Feenstra

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
from typing import List, Optional

import mobase
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QWidget

from .Games import SUPPORTED_GAMES


class LOOTWarningToggle(mobase.IPluginTool):
    def __init__(self) -> None:
        super().__init__()
        self.__parentWidget: Optional[QWidget] = None

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self.__organizer = organizer
        return True

    def name(self) -> str:
        return "LOOT Warning Toggle"

    def author(self) -> str:
        return "Jonathan Feenstra"

    def description(self) -> str:
        return self.__tr("Toggles LOOT warnings.")

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.BETA)

    def requirements(self) -> List[mobase.IPluginRequirement]:
        return [mobase.PluginRequirementFactory.gameDependency(games=list(SUPPORTED_GAMES.keys()))]

    def settings(self) -> List[mobase.PluginSetting]:
        return [mobase.PluginSetting("enable-warnings", self.__tr("Enable LOOT warnings"), True)]

    def display(self) -> None:
        self.__organizer.setPluginSetting(self.name(), "enable-warnings", not self.__warningsEnabled())

    def displayName(self) -> str:
        return self.__tr(f"{'Disable' if self.__warningsEnabled() else 'Enable'} LOOT warnings")

    def icon(self) -> QIcon:
        return QIcon("plugins/LOOT-Warning-Checker/resources/icon.ico")

    def setParentWidget(self, parent: QWidget) -> None:
        self.__parentWidget = parent

    def tooltip(self) -> str:
        return self.__tr("Toggles checking for LOOT warnings from the LOOT Warning Checker plugin.")

    def __tr(self, txt: str) -> str:
        return QApplication.translate("LOOTWarningToggle", txt)

    def __warningsEnabled(self) -> bool:
        return self.__organizer.pluginSetting(self.name(), "enable-warnings")  # type: ignore
