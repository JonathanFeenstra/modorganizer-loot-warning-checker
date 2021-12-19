"""
Masterlist
==========

Detection and parsing of the LOOT masterlist and userlist files.

Copyright (C) 2021 Jonathan Feenstra

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
from typing import Any, Dict, Generator, List, NamedTuple, Union
from urllib.error import URLError
from urllib.request import urlopen

from mobase import IOrganizer
from PyQt5.QtCore import qCritical, qDebug, qWarning
from yaml import CSafeLoader, YAMLError, load

from .Conditions import InvalidConditionError, LOOTConditionEvaluator, computeCRC32
from .Warnings import DirtyPluginWarning, IncompatibilityWarning, LOOTWarning, MessageWarning, MissingRequirementWarning


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


def findMasterlistDir(gameFolder: str) -> str:
    """
    Find the masterlist's directory for the given game folder (create it if it doesn't exist).

    Args:
        gameFolder (str): Name of the game's local appdata folder

    Returns:
        str: Path to the masterlist's directory

    Raises:
        FileExistsError: If a file already exists at the expected path
    """
    lootDir = os.path.expandvars(r"%LOCALAPPDATA%\LOOT")
    if not os.path.isdir(lootDir):
        os.mkdir(lootDir)
    masterlistDir = os.path.join(lootDir, gameFolder)
    if not os.path.isdir(masterlistDir):
        os.mkdir(masterlistDir)
    return masterlistDir


# TODO: Consider using GitPython to keep track of the masterlist's current version
def downloadMasterlist(masterlistRepo: str, filePath: Union[str, os.PathLike]) -> None:
    """Download the masterlist from GitHub to the given file path.

    Args:
        masterlistRepo (str): Name of the masterlist's GitHub repository (not the full URL)
        filePath (str): Path to the masterlist's file (download location)

    Raises:
        urllib.error.URLError: If the download fails
        OSError: If the file cannot be written to
    """
    # Version branch may change if the masterlist syntax changes
    masterlistURL = f"https://raw.githubusercontent.com/loot/{masterlistRepo}/v0.17/masterlist.yaml"
    with urlopen(masterlistURL) as response:
        with open(filePath, "wb") as file:
            file.write(response.read())


def _parseMasterlist(masterlistPath: Union[str, bytes, os.PathLike]) -> Dict[str, Dict[str, Any]]:
    """Parse the masterlist file at the given path.

    Args:
        masterlistPath (str): Path to the masterlist's file

    Returns:
        Dict[str, Dict[str, Any]]: Plugin names mapped to their metadata

    Raises:
        FileNotFoundError: If the masterlist file does not exist
        yaml.YAMLError: If the masterlist file cannot be parsed
        ValueError: If the masterlist file contains invalid data
    """
    with open(masterlistPath, "r", encoding="utf-8") as file:
        masterlist = load(file, CSafeLoader)
    if not isinstance(masterlist, dict) or masterlist.get("plugins") is None:
        raise ValueError("Invalid masterlist file.")
    return {plugin.pop("name"): plugin for plugin in masterlist["plugins"]}


def _mergeLists(masterlist: Dict[str, Dict[str, Any]], userlist: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Merge the masterlist and userlist into a single dictionary.

    Currently only merges data used by the MO2 plugin.

    https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-plugin-merge

    Args:
        masterlist (Dict[str, Dict[str, Any]]): Parsed masterlist
        userlist (Dict[str, Dict[str, Any]]): Parsed userlist

    Returns:
        Dict[str, Dict[str, Any]]: Merged masterlist and userlist
    """
    for pluginName, userData in userlist.items():
        if pluginName not in masterlist:
            masterlist[pluginName] = userData
        else:
            masterData = masterlist[pluginName]
            masterData = _mergePluginData(masterData, userData)
    return masterlist


def _mergePluginData(masterData: Dict[str, Any], userData: Dict[str, Any]) -> Dict[str, Any]:
    """Merge the masterlist and userlist plugin data.

    Currently only merges data used by the MO2 plugin.

    https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-plugin-merge

    Args:
        masterData (Dict[str, Any]): Parsed masterlist plugin data
        userData (Dict[str, Any]): Parsed userlist plugin data

    Returns:
        Dict[str, Any]: Merged masterlist and userlist plugin data
    """
    if userReq := userData.get("req"):
        masterData["req"] = _mergeFileSets(masterData.get("req", []), userReq)
    if userInc := userData.get("inc"):
        masterData["inc"] = _mergeFileSets(masterData.get("inc", []), userInc)
    if userMsg := userData.get("msg"):
        masterData["msg"] = _mergeMessageLists(masterData.get("msg", []), userMsg)
    if userDirty := userData.get("dirty"):
        masterData["dirty"] = _mergeDirtyInfoSets(masterData.get("dirty", []), userDirty)
    return masterData


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

    def _loadLists(self) -> Dict[str, Dict[str, Any]]:
        """Load the masterlist and userlist files.

        Returns:
            Dict[str, Dict[str, Any]]: The masterlist merged with the userlist as a dictionary
        """
        masterlistDir = findMasterlistDir(self._game.folder)
        masterlistPath = os.path.join(masterlistDir, "masterlist.yaml")
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
            masterlist = _parseMasterlist(masterlistPath)
        except (FileNotFoundError, YAMLError, ValueError) as exc:
            qCritical(f"Failed to parse masterlist for {self._game.folder}.\n{exc}")
            return {}
        userlistPath = os.path.join(masterlistDir, "userlist.yaml")
        if os.path.isfile(userlistPath):
            try:
                userlist = _parseMasterlist(userlistPath)
            except (FileNotFoundError, YAMLError, ValueError) as exc:
                qCritical(f"Failed to parse userlist for {self._game.folder}.\n{exc}")
                return masterlist
            masterlist = _mergeLists(masterlist, userlist)
        return masterlist

    def getWarnings(self, includeInfo: bool = False) -> Generator[LOOTWarning, None, None]:
        """Get a list of warnings from LOOT for the loaded list of plugins.

        Args:
            includeInfo (bool): Whether to include info messages in the warnings

        Yields:
            LOOTWarning: LOOT's warnings
        """
        for pluginPath in self._organizer.findFiles("", "*.es[lmp]"):
            pluginName = os.path.basename(pluginPath)
            if (pluginData := self._masterlist.get(pluginName, None)) is not None:
                try:
                    yield from self._getPluginWarnings(pluginPath, pluginData, includeInfo)
                except Exception as exc:
                    # Prevent unexpected errors from checking the rest of the plugins
                    qCritical(f"Error while processing {pluginName}: {exc}")

    def _getPluginWarnings(
        self, pluginPath: str, pluginData: Dict[str, Any], includeInfo: bool = False
    ) -> Generator[LOOTWarning, None, None]:
        """Get LOOT's warnings for the given plugin.

        Args:
            pluginPath (str): Path to the plugin's file
            pluginData (dict): Plugin's metadata
            includeInfo (bool): Whether to include info messages in the warnings

        Yields:
            LOOTWarning: LOOT's warnings for the given plugin
        """
        pluginName = os.path.basename(pluginPath)
        if isinstance(requiredFiles := pluginData.get("req"), list):
            qDebug(f"Checking {pluginName} for missing requirements")
            yield from self._getMissingRequirementWarnings(pluginName, requiredFiles)
        if isinstance(incompatibleFiles := pluginData.get("inc"), list):
            qDebug(f"Checking {pluginName} for incompatible files")
            yield from self._getIncompatibilityWarnings(pluginName, incompatibleFiles)
        if isinstance(messages := pluginData.get("msg"), list):
            qDebug(f"Checking {pluginName} for messages")
            yield from self._getMessageWarnings(pluginName, messages, includeInfo)
        if isinstance(dirtyInfos := pluginData.get("dirty"), list):
            qDebug(f"Checking if {pluginName} is dirty")
            yield from self._getDirtyWarnings(pluginPath, dirtyInfos)

    def _getMissingRequirementWarnings(
        self, pluginName: str, requiredFiles: List[Union[str, Dict]]
    ) -> Generator[LOOTWarning, None, None]:
        """Get LOOT warnings for missing requirements.

        Args:
            pluginName (str): Name of the plugin
            requiredFiles (List[Union[str, Dict]]): List of required files

        Yields:
            MissingRequirementWarning: Missing requirement warning
        """
        for file in requiredFiles:
            if isinstance(file, str):
                if self._conditionEvaluator._file(file):
                    continue
                yield MissingRequirementWarning(pluginName, file)
            else:
                # file datastructure: https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-file
                fileName = file["name"]
                if self._conditionEvaluator._file(fileName):
                    continue
                if (condition := file.get("condition")) is not None:
                    try:
                        if self._conditionEvaluator.evalCondition(condition):
                            yield MissingRequirementWarning(pluginName, file)
                    except InvalidConditionError as exc:
                        qCritical(f"Invalid condition in {pluginName}'s masterlist entry: {condition}\n{exc}")
                else:
                    yield MissingRequirementWarning(pluginName, file)

    def _getIncompatibilityWarnings(
        self, pluginName: str, incompatibleFiles: List[Union[str, Dict]]
    ) -> Generator[IncompatibilityWarning, None, None]:
        """Get LOOT warnings for incompatible files.

        Args:
            pluginName (str): Name of the plugin
            incompatibleFiles (List[Union[str, Dict]]): List of incompatible files

        Yields:
            IncompatibilityWarning: Incompatibility warning
        """
        for file in incompatibleFiles:
            if isinstance(file, str):
                if self._conditionEvaluator._file(file):
                    yield IncompatibilityWarning(pluginName, file)
            else:
                # file datastructure: https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-file
                fileName = file["name"]
                if self._conditionEvaluator._file(fileName):
                    if (condition := file.get("condition")) is not None:
                        try:
                            if self._conditionEvaluator.evalCondition(condition):
                                yield IncompatibilityWarning(pluginName, file)
                        except InvalidConditionError:
                            qCritical(f"Invalid condition in {pluginName}'s masterlist entry: {condition}")
                    else:
                        yield IncompatibilityWarning(pluginName, file)

    def _getMessageWarnings(
        self, pluginName: str, messages: List[Dict[str, Any]], includeInfo: bool = False
    ) -> Generator[MessageWarning, None, None]:
        """Get LOOT warnings for messages.

        https://loot-api.readthedocs.io/en/latest/metadata/data_structures/message.html
        https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-message

        Args:
            pluginName (str): Name of the plugin
            messages (List[Dict[str, Any]]): List of messages
            includeInfo (bool): Whether to include info messages in the warnings

        Yields:
            MessageWarning: Message warning
        """
        for msg in messages:
            if includeInfo or msg["type"] in ("warn", "error"):
                if (condition := msg.get("condition", None)) is None:
                    yield MessageWarning(pluginName, msg)
                else:
                    try:
                        if self._conditionEvaluator.evalCondition(condition):
                            yield MessageWarning(pluginName, msg)
                    except InvalidConditionError as exc:
                        qWarning(f"Invalid condition in {pluginName}'s masterlist entry: {condition}\n{exc}")
                        continue

    def _getDirtyWarnings(
        self, pluginPath: str, dirtyInfos: List[Dict[str, Any]]
    ) -> Generator[DirtyPluginWarning, None, None]:
        """Get LOOT warnings for dirty plugins.

        https://loot.github.io/docs/0.9.2/LOOT%20Metadata%20Syntax.html#structs-dirty

        Args:
            pluginPath (str): Path to the plugin
            dirtyInfos (List[Dict[str, Any]]): List of dirty info data structures

        Yields:
            DirtyPluginWarning: Dirty plugin warning
        """
        pluginCRC = computeCRC32(pluginPath)
        for dirtyInfo in dirtyInfos:
            if dirtyInfo["crc"] == pluginCRC:
                yield DirtyPluginWarning(os.path.basename(pluginPath), dirtyInfo)
