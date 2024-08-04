"""
Plugins
=======

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

import os
from zlib import crc32

from esplugin import Plugin


class PluginParseError(Exception):
    """Raised when a plugin fails to parse."""


class GamebryoPlugin:
    """Gamebryo plugin.

    Attributes:
        masterlistRepo (str): The name of the masterlist repository the plugin belongs to
        path (str): Path to the plugin file
        name (str): Plugin name
    """

    def __init__(self, masterlistRepo: str, path: str) -> None:
        """
        Args:
            masterlistRepo (str): The name of the masterlist repository the plugin belongs to
            path (str): The path to the plugin
        """
        self.masterlistRepo = masterlistRepo
        self.path = path
        self.name = os.path.basename(path)
        self._esplugin = None  # None if unloaded, False if not applicable
        self._crc = None

    @property
    def crc(self) -> int:
        """Get the CRC32 of the plugin (lazy loaded).

        Returns:
            int: The CRC32 of the plugin
        """
        if self._crc is None:
            self._loadData()
        return self._crc  # type: ignore

    def _loadData(self) -> None:
        """Load the plugin data from the file content.

        Raises:
            PluginParseError: Raised when the plugin fails to parse.
        """
        if os.stat(self.path).st_size == 0:
            self._esplugin = False
            self._crc = 0
            return
        with open(self.path, "rb") as f:
            content = f.read()
            self._crc = crc32(content)
            if self.masterlistRepo in ("skyrimse", "skyrimvr", "enderal"):
                self._esplugin = Plugin("SkyrimSE", self.path)
            elif self.masterlistRepo in ("fallout4", "fallout4vr"):
                self._esplugin = Plugin("Fallout4", self.path)
            elif self.masterlistRepo == "starfield":
                self._esplugin = Plugin("Starfield", self.path)
            else:
                self._esplugin = False
                return
            try:
                self._esplugin.parse(content, False)
            except ValueError as err:
                raise PluginParseError(err)

    def isLightPlugin(self) -> bool:
        """Check if the plugin is a light plugin (ESL).

        Returns:
            bool: True if the plugin is a light plugin

        Raises:
            PluginParseError: Raised when the plugin fails to parse.
        """
        if self.name.endswith(".esl"):
            return True
        if self._esplugin is None:
            self._loadData()
        if not self._esplugin:
            return False
        return self._esplugin.is_light_plugin()

    def isValidAsLightPlugin(self) -> bool:
        """Check if the plugin is valid as a light plugin (ESL).

        A plugin is valid as a light plugin if the game supports light plugins and all FormIDs are in the valid range for
        the game. This does not check if the plugin is actually a light plugin.

        Returns:
            bool: True if the plugin is valid as a light plugin

        Raises:
            PluginParseError: Raised when the plugin fails to parse.
        """
        if self._esplugin is None:
            self._loadData()
        if not self._esplugin:
            return False
        return self._esplugin.is_valid_as_light_plugin()

    def isMediumPlugin(self) -> bool:
        """Check if the plugin is a medium plugin (for Starfield).

        Returns:
            bool: True if the plugin is a medium plugin

        Raises:
            PluginParseError: Raised when the plugin fails to parse.
        """
        if self.name.endswith(".esl"):
            return False
        if self._esplugin is None:
            self._loadData()
        if not self._esplugin:
            return False
        return not self._esplugin.is_medium_plugin()

    def isValidAsMediumPlugin(self) -> bool:
        """Check if the plugin is valid as a medium plugin (for Starfield).

        A plugin is valid as a medium plugin if the game supports medium plugins and all FormIDs are in the valid range for
        the game. This does not check if the plugin is actually a medium plugin.

        Returns:
            bool: True if the plugin is valid as a medium plugin

        Raises:
            PluginParseError: Raised when the plugin fails to parse.
        """
        if self._esplugin is None:
            self._loadData()
        if not self._esplugin:
            return False
        return self._esplugin.is_valid_as_medium_plugin()

    def isUpdatePlugin(self) -> bool:
        """Check if the plugin is an update plugin (for Starfield).

        Returns:
            bool: True if the plugin is an update plugin

        Raises:
            PluginParseError: Raised when the plugin fails to parse.
        """
        if self.name.endswith(".esl"):
            return False
        if self._esplugin is None:
            self._loadData()
        if not self._esplugin:
            return False
        return self._esplugin.is_update_plugin()

    def isValidAsUpdatePlugin(self) -> bool:
        """Check if the plugin is valid as an update plugin (for Starfield).

        A plugin is valid as an update plugin if the game supports update plugins and all records override an existing record.
        This does not check if the plugin is actually an update plugin.

        Returns:
            bool: True if the plugin is valid as an update plugin

        Raises:
            PluginParseError: Raised when the plugin fails to parse.
        """
        if self._esplugin is None:
            self._loadData()
        if not self._esplugin:
            return False
        return self._esplugin.is_valid_as_update_plugin()
