"""
Masterlist
==========

Detection and parsing of the LOOT masterlist and userlist files.

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
import re
from typing import Any, Dict, Final, Generator, List, NamedTuple, Optional, Union
from urllib.error import URLError
from urllib.request import urlopen

from mobase import IOrganizer
from PyQt5.QtCore import qCritical, qDebug, qWarning
from yaml import CLoader, YAMLError, load

from .Conditions import InvalidConditionError, LOOTConditionEvaluator, isRegex
from .Plugins import GamebryoPlugin, PluginParseError
from .Warnings import (
    DirtyPluginWarning,
    FormID_OutOfRangeWarning,
    IncompatibilityWarning,
    LOOTWarning,
    MessageWarning,
    MissingRequirementWarning,
)

_CHECKER_PLUGIN_NAME: Final[str] = "LOOT Warning Checker"


class LOOTGame(NamedTuple):
    r"""Game supported by LOOT.

    See: %LOCALAPPDATA%\LOOT\settings.toml

    References:
        - https://github.com/loot/loot/blob/master/src/gui/state/loot_settings.cpp
        - https://github.com/loot/loot/blob/master/src/gui/state/game/game_settings.cpp

    Attributes:
        masterlistRepo (str): Name of the masterlist's GitHub repository (not the full URL)
        folder (str): Name of LOOT's local appdata folder for this game
    """

    masterlistRepo: str
    folder: str


class _LOOTMasterlist:
    """LOOT masterlist containing metadata for plugin warnings.

    Attributes:
        path (Union[str, bytes, os.PathLike]): Path to the masterlist file
    """

    def __init__(self, path: Union[str, bytes, os.PathLike]) -> None:
        """Initialize the masterlist.

        Args:
            path (Union[str, bytes, os.PathLike]): Path to the masterlist file

        Raises:
            FileNotFoundError: If the masterlist file does not exist
            yaml.YAMLError: If the masterlist file cannot be parsed
            ValueError: If the masterlist file contains invalid data
        """
        self.path = path

        qDebug(f"Loading masterlist from {path}")
        with open(path, "r", encoding="utf-8") as file:
            data = load(file, CLoader)

        if not isinstance(data, dict) or data.get("plugins") is None:
            raise ValueError("Invalid masterlist file.")

        self._nameEntries: Dict[str, Dict[str, Any]] = {}
        self._regexEntries: Dict[str, Dict[str, Any]] = {}

        self._addEntries(data)

    def _addEntries(self, data: Dict[str, Any]) -> None:
        for entry in data["plugins"]:
            # PyYAML seems to make some names lowercase, so this makes it consistent
            name = entry.pop("name").lower()

            if isRegex(name):
                self._addRegex(entry, name)
            else:
                self._nameEntries[name] = entry

    def _addRegex(self, entry: Dict[str, Any], name: str) -> None:
        try:
            entry["regex"] = re.compile(name)
        except re.error:
            qWarning(f"Invalid regular expression in masterlist: {name}")
        else:
            self._regexEntries[name] = entry

    def getEntry(self, pluginName: str) -> Optional[Dict[str, Any]]:
        """Get the masterlist entry for the given plugin name.

        Args:
            pluginName (str): Name of the plugin

        Returns:
            Optional[Dict[str, Any]]: The masterlist entry, or None if it does not exist
        """
        pluginName = pluginName.lower()
        return self._nameEntries.get(pluginName, None) or self._getRegexEntry(pluginName)

    def _getRegexEntry(self, pluginName: str) -> Optional[Dict[str, Any]]:
        for entry in self._regexEntries.values():
            if entry["regex"].match(pluginName):
                return entry
        return None

    def merge(self, other: "_LOOTMasterlist") -> None:
        """Merge the given masterlist into this one.

        Currently only merges data used by the MO2 plugin.

        https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-plugin-merge

        Args:
            other (_LOOTMasterlist): Masterlist to merge into this one
        """
        for pluginName, entry in other._nameEntries.items():
            if pluginName not in self._nameEntries:
                self._nameEntries[pluginName] = entry
            else:
                _mergeEntry(self._nameEntries[pluginName], other._nameEntries[pluginName])

        for regex, entry in other._regexEntries.items():
            if regex not in self._regexEntries:
                self._regexEntries[regex] = entry
            else:
                _mergeEntry(self._regexEntries[regex], other._regexEntries[regex])


def _mergeEntry(entry1: Dict[str, Any], entry2: Dict[str, Any]) -> None:
    """Merge the given masterlist entries.

    https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-file

    Args:
        entry1 (Dict[str, Any]): First masterlist entry
        entry2 (Dict[str, Any]): Second masterlist entry
    """
    if req := entry2.get("req"):
        entry1["req"] = _mergeFileSets(entry1.get("req", []), req)
    if inc := entry2.get("inc"):
        entry1["inc"] = _mergeFileSets(entry1.get("inc", []), inc)
    if msg := entry2.get("msg"):
        entry1["msg"] = _mergeMessageLists(entry1.get("msg", []), msg)
    if dirty := entry2.get("dirty"):
        entry1["dirty"] = _mergeDirtyInfoSets(entry1.get("dirty", []), dirty)


def _mergeFileSets(masterFileSet: List[Union[str, Dict]], userFileSet: List[Union[str, Dict]]) -> List[Union[str, Dict]]:
    """Merge the masterlist and userlist file sets.

    https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-file

    Args:
        masterFileSet ([List[Union[str, Dict]]]): Parsed masterlist file set
        userFileSet (List[Union[str, Dict]]): Parsed userlist file set

    Returns:
        List[Union[str, Dict]]: Merged masterlist and userlist file set
    """
    if not masterFileSet:
        return userFileSet
    for userFile in userFileSet:
        userFileName = userFile["name"] if isinstance(userFile, dict) else userFile
        masterFile = next(
            (
                file
                for file in masterFileSet
                if file == userFileName or isinstance(file, dict) and file["name"] == userFileName
            ),
            None,
        )
        if masterFile is None:
            masterFileSet.append(userFile)
        elif isinstance(userFile, dict):
            if isinstance(masterFile, str):
                masterFileSet.remove(masterFile)
                masterFileSet.append(userFile)
            elif isinstance(masterFile, dict):
                masterFile.update(userFile)
    return masterFileSet


def _mergeMessageLists(
    masterMessageList: List[Dict[str, Any]], userMessageList: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge the masterlist and userlist message lists.

    https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-message

    Args:
        masterMessageList (List[Dict[str, Any]]): Parsed masterlist message list
        userMessageList (List[Dict[str, Any]]): Parsed userlist message list

    Returns:
        List[Dict[str, Any]]: Merged masterlist and userlist message list
    """
    for userMessage in userMessageList:
        if userMessage not in masterMessageList:
            masterMessageList.append(userMessage)
    return masterMessageList


def _mergeDirtyInfoSets(
    masterDirtyInfoSet: List[Dict[str, Any]], userDirtyInfoSet: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge the masterlist and userlist dirty info sets.

    https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-dirty

    Args:
        masterDirtyInfoSet (List[Dict[str, Any]]): Parsed masterlist dirty info set
        userDirtyInfoSet (List[Dict[str, Any]]): Parsed userlist dirty info set

    Returns:
        List[Dict[str, Any]]: Merged masterlist and userlist dirty info set
    """
    for userDirtyInfo in userDirtyInfoSet:
        masterDirtyInfo = next(
            (dirtyInfo for dirtyInfo in masterDirtyInfoSet if dirtyInfo["crc"] == userDirtyInfo["crc"]),
            None,
        )
        if masterDirtyInfo is None:
            masterDirtyInfoSet.append(userDirtyInfo)
        else:
            masterDirtyInfo.update(userDirtyInfo)
    return masterDirtyInfoSet


def getMasterlistPath(pluginDataPath: str, gameFolder: str) -> str:
    """
    Get the path to the masterlist for the given game folder (create it if it doesn't exist).

    Args:
        pluginDataPath (str): MO2's directory for the plugin's data, typically /plugins/data/<plugin name>
        gameFolder (str): Name of the game's local appdata folder

    Returns:
        str: Path to the masterlist.yaml file

    Raises:
        FileExistsError: If a file already exists at the expected path
    """
    masterlistDir = os.path.join(pluginDataPath, gameFolder)
    os.makedirs(masterlistDir, exist_ok=True)
    return os.path.join(masterlistDir, "masterlist.yaml")


def downloadMasterlist(masterlistRepo: str, filePath: Union[str, os.PathLike]) -> None:
    """Download the masterlist from GitHub to the given file path.

    https://github.com/loot/loot/issues/1490

    Args:
        masterlistRepo (str): Name of the masterlist's GitHub repository (not the full URL)
        filePath (str): Path to the masterlist's file (download location)

    Raises:
        urllib.error.URLError: If the download fails
        OSError: If the file cannot be written to
    """
    # Version branch may change if the masterlist syntax changes
    masterlistURL = f"https://raw.githubusercontent.com/loot/{masterlistRepo}/v0.18/masterlist.yaml"
    with urlopen(masterlistURL) as response:
        with open(filePath, "wb") as file:
            file.write(response.read())


class LOOTMasterlistLoader:
    """Loader for the LOOT masterlist data."""

    def __init__(self, organizer: IOrganizer, game: LOOTGame) -> None:
        """
        Args:
            organizer (IOrganizer): Organizer instance
            game (LOOTGame): Game to parse the masterlist for
        """
        self._organizer = organizer
        self._game = game
        self._conditionEvaluator = LOOTConditionEvaluator(organizer)
        self._masterlist = self._loadLists()

    def _loadLists(self) -> _LOOTMasterlist:
        """Load the masterlist and userlist files.

        Returns:
            _LOOTMasterlist: Parsed masterlist data
        """
        masterlistPath = getMasterlistPath(
            os.path.join(self._organizer.getPluginDataPath(), _CHECKER_PLUGIN_NAME), self._game.folder
        )
        if not os.path.isfile(masterlistPath):
            qDebug(f"Masterlist not found at {masterlistPath}, downloading...")
            try:
                downloadMasterlist(self._game.masterlistRepo, masterlistPath)
            except URLError:
                qCritical(f"Failed to download masterlist for {self._game.folder}.")
                raise
            except OSError:
                qCritical(f"Failed to write masterlist for {self._game.folder}.")
                raise
            else:
                qDebug("Masterlist download complete.")
        try:
            masterlist = _LOOTMasterlist(masterlistPath)
        except (FileNotFoundError, YAMLError, ValueError) as exc:
            qCritical(f"Failed to parse masterlist for {self._game.folder}.\n{exc}")
            return {}

        userlistPath = self._getUserlistPath()
        if os.path.isfile(userlistPath):
            try:
                userlist = _LOOTMasterlist(userlistPath)
            except (FileNotFoundError, YAMLError, ValueError) as exc:
                qCritical(f"Failed to parse userlist for {self._game.folder}.\n{exc}")
            else:
                masterlist.merge(userlist)
        return masterlist

    def _getUserlistPath(self) -> str:
        userlistsDir = self._organizer.pluginSetting(_CHECKER_PLUGIN_NAME, "userlists-directory")
        if userlistsDir == "":
            userlistsDir = os.path.join(self._organizer.getPluginDataPath(), _CHECKER_PLUGIN_NAME)
            self._organizer.setPluginSetting(_CHECKER_PLUGIN_NAME, "userlists-directory", userlistsDir)
        return os.path.join(userlistsDir, self._game.folder, "userlist.yaml")

    def getWarnings(self, includeInfo: bool = False) -> Generator[LOOTWarning, None, None]:
        """Get a list of warnings from LOOT for the loaded list of plugins.

        Args:
            includeInfo (bool): Whether to include info messages in the warnings

        Yields:
            LOOTWarning: LOOT's warnings
        """
        for pluginPath in self._organizer.findFiles("", "*.es[lmp]"):
            plugin = GamebryoPlugin(self._game.masterlistRepo, pluginPath)
            try:
                isInvalidLightPlugin = plugin.isLightPlugin() and not plugin.isValidAsLightPlugin()
            except PluginParseError as err:
                qWarning(f"Failed to parse plugin {pluginPath}: {err}.")
            else:
                if isInvalidLightPlugin:
                    qDebug(f"Invalid light plugin detected: {plugin.name}")
                    yield FormID_OutOfRangeWarning(plugin.name)
            if (entry := self._masterlist.getEntry(plugin.name)) is not None:
                try:
                    yield from self._getPluginWarnings(plugin, entry, includeInfo)
                except Exception as exc:
                    # Prevent unexpected errors from checking the rest of the plugins
                    qCritical(f"Error while processing {plugin.name}: {exc}")
            else:
                qDebug(f"Plugin {plugin.name} not found in masterlist.")

    def _getPluginWarnings(
        self, plugin: GamebryoPlugin, entry: Dict[str, Any], includeInfo: bool = False
    ) -> Generator[LOOTWarning, None, None]:
        """Get LOOT's warnings for the given plugin.

        Args:
            plugin (GamebryoPlugin): Plugin to check
            entry (dict): Plugin's entry in the masterlist
            includeInfo (bool): Whether to include info messages in the warnings

        Yields:
            LOOTWarning: LOOT's warnings for the given plugin
        """
        if isinstance(requiredFiles := entry.get("req"), list):
            qDebug(f"Checking {plugin.name} for missing requirements...")
            yield from self._getMissingRequirementWarnings(plugin, requiredFiles)
        if isinstance(incompatibleFiles := entry.get("inc"), list):
            qDebug(f"Checking {plugin.name} for incompatible files...")
            yield from self._getIncompatibilityWarnings(plugin, incompatibleFiles)
        if isinstance(messages := entry.get("msg"), list):
            qDebug(f"Checking {plugin.name} for messages...")
            yield from self._getMessageWarnings(plugin, messages, includeInfo)
        if isinstance(dirtyInfos := entry.get("dirty"), list):
            qDebug(f"Checking if {plugin.name} is dirty...")
            yield from self._getDirtyWarnings(plugin, dirtyInfos)

    def _getMissingRequirementWarnings(
        self, plugin: GamebryoPlugin, requiredFiles: List[Union[str, Dict]]
    ) -> Generator[LOOTWarning, None, None]:
        """Get LOOT warnings for missing requirements.

        Args:
            plugin (GamebryoPlugin): The plugin to check for missing requirements
            requiredFiles (List[Union[str, Dict]]): List of required files

        Yields:
            MissingRequirementWarning: Missing requirement warning
        """
        for file in requiredFiles:
            if isinstance(file, str):
                if self._conditionEvaluator._file(file):
                    continue
                yield MissingRequirementWarning(plugin.name, file)
            else:
                # file datastructure: https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-file
                fileName = file["name"]
                if self._conditionEvaluator._file(fileName):
                    continue
                if (condition := file.get("condition")) is not None:
                    try:
                        if self._conditionEvaluator.evalCondition(condition, plugin):
                            yield MissingRequirementWarning(plugin.name, file)
                    except InvalidConditionError as exc:
                        qCritical(f"Invalid condition in {plugin.name}'s masterlist entry: {condition}\n{exc}")
                else:
                    yield MissingRequirementWarning(plugin.name, file)

    def _getIncompatibilityWarnings(
        self, plugin: GamebryoPlugin, incompatibleFiles: List[Union[str, Dict]]
    ) -> Generator[IncompatibilityWarning, None, None]:
        """Get LOOT warnings for incompatible files.

        Args:
            plugin (GamebryoPlugin): The plugin to check for incompatible files
            incompatibleFiles (List[Union[str, Dict]]): List of incompatible files

        Yields:
            IncompatibilityWarning: Incompatibility warning
        """
        for file in incompatibleFiles:
            if isinstance(file, str):
                if self._conditionEvaluator._file(file):
                    yield IncompatibilityWarning(plugin.name, file)
            else:
                # file datastructure: https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-file
                fileName = file["name"]
                if self._conditionEvaluator._file(fileName):
                    if (condition := file.get("condition")) is not None:
                        try:
                            if self._conditionEvaluator.evalCondition(condition, plugin):
                                yield IncompatibilityWarning(plugin.name, file)
                        except InvalidConditionError:
                            qCritical(f"Invalid condition in {plugin.name}'s masterlist entry: {condition}")
                    else:
                        yield IncompatibilityWarning(plugin.name, file)

    def _getMessageWarnings(
        self, plugin: GamebryoPlugin, messages: List[Dict[str, Any]], includeInfo: bool = False
    ) -> Generator[MessageWarning, None, None]:
        """Get LOOT warnings for messages.

        https://loot-api.readthedocs.io/en/latest/metadata/data_structures/message.html
        https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-message

        Args:
            plugin (GamebryoPlugin): The plugin to check for messages
            messages (List[Dict[str, Any]]): List of messages
            includeInfo (bool): Whether to include info messages in the warnings

        Yields:
            MessageWarning: Message warning
        """
        for msg in messages:
            if includeInfo or msg["type"] in ("warn", "error"):
                if (condition := msg.get("condition", None)) is None:
                    yield MessageWarning(plugin.name, msg)
                else:
                    try:
                        if self._conditionEvaluator.evalCondition(condition, plugin):
                            yield MessageWarning(plugin.name, msg)
                    except InvalidConditionError as exc:
                        qWarning(f"Invalid condition in {plugin.name}'s masterlist entry: {condition}\n{exc}")
                        continue

    def _getDirtyWarnings(
        self, plugin: GamebryoPlugin, dirtyInfos: List[Dict[str, Any]]
    ) -> Generator[DirtyPluginWarning, None, None]:
        """Get LOOT warnings for dirty plugins.

        https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-dirty

        Args:
            plugin (GamebryoPlugin): Plugin to check
            dirtyInfos (List[Dict[str, Any]]): List of dirty info data structures

        Yields:
            DirtyPluginWarning: Dirty plugin warning
        """
        for dirtyInfo in dirtyInfos:
            if dirtyInfo["crc"] == plugin.crc:
                yield DirtyPluginWarning(plugin.name, dirtyInfo)
