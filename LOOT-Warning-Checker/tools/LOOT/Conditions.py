"""
Conditions
==========

Parsing and evaluation of LOOT masterlist conditions.

References:
- https://loot-api.readthedocs.io/en/latest/metadata/conditions.html

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

GPL License and Copyright Notice ============================================
 Parts of this file are based on code from Wrye Bash:
 https://github.com/wrye-bash/wrye-bash/blob/dev/Mopy/bash/loot_conditions.py

 Wrye Bash is free software: you can redistribute it and/or
 modify it under the terms of the GNU General Public License
 as published by the Free Software Foundation, either version 3
 of the License, or (at your option) any later version.

 Wrye Bash is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with Wrye Bash.  If not, see <https://www.gnu.org/licenses/>.

 Wrye Bash copyright (C) 2005-2009 Wrye, 2010-2024 Wrye Bash Team
 https://github.com/wrye-bash

=============================================================================
"""
import operator
import os
import re
from ast import literal_eval
from typing import Any, Callable, Generator, List, Optional, Tuple, Union
from zlib import crc32

import mobase
from PyQt6.QtCore import qCritical, qDebug

from .Plugins import GamebryoPlugin


class InvalidConditionError(ValueError):
    pass


def _computeCRC32(pluginPath: Union[str, bytes, os.PathLike]) -> int:
    """Compute the CRC32 of a file.

    Args:
        pluginPath: The path to the file to compute the CRC32 of.

    Returns:
        The CRC32 of the file.
    """
    with open(pluginPath, "rb") as f:
        return crc32(f.read())


def isRegex(arg: str) -> bool:
    """Check if an argument is a regex according to LOOT.

    https://loot-api.readthedocs.io/en/latest/metadata/conditions.html#functions

    Args:
        arg: The argument to check.

    Returns:
        True if the argument is a regex
    """
    return any(char in arg for char in r":\*?|")


def _splitOnUnquotedCommas(string: str) -> List[str]:
    """Split a string on commas that are not between quotes.

    Args:
        string: The string to split.

    Returns:
        A list of strings.
    """
    splitParts = []
    currentPart = []
    inQuotes = False
    for char in string:
        if char == '"':  # TODO: Handle a mix of single and double quotes
            inQuotes = not inQuotes
            currentPart.append(char)
        elif char == "," and not inQuotes:
            splitParts.append("".join(currentPart).strip())
            currentPart = []
        else:
            currentPart.append(char)
    splitParts.append("".join(currentPart).strip())
    return splitParts


def _evalBooleanExpression(booleanExpression: str) -> bool:
    """Safely evaluate a string as a boolean expression.

    This is needed because `ast.literal_eval` does not parse boolean operators.

    Args:
        booleanExpression (str): A string to evaluate containing only booleans and boolean operators

    Returns:
        bool: True if the condition is met

    Raises:
        InvalidCondition: If the condition contains invalid tokens
    """
    for token in booleanExpression.replace("(", "").replace(")", "").split():
        if token not in ("True", "False", "and", "or", "not"):
            raise InvalidConditionError(f"Condition contains invalid token: {token}")
    return eval(booleanExpression)


class LOOTConditionEvaluator:
    """Evaluates LOOT masterlist conditions."""

    _STRING_RE = re.compile(r'".*?"|\'.*?\'')
    _COMPARATORS = {
        "==": operator.eq,
        "!=": operator.ne,
        "<": operator.lt,
        ">": operator.gt,
        ">=": operator.ge,
        "<=": operator.le,
    }

    def __init__(self, organizer: mobase.IOrganizer) -> None:
        """
        Args:
            organizer (mobase.IOrganizer): The Mod Organizer interface to use to get data from
        """
        self._organizer = organizer
        self._gameDir = os.path.normpath(self._organizer.managedGame().dataDirectory().absoluteFilePath(".."))
        self._pluginList = organizer.pluginList()
        self._functionMapping = (
            (re.compile(r"(?:^|[\s\(])(?P<func>file\((?P<args>.*?)\))"), self._file),
            (re.compile(r"(?:^|[\s\(])(?P<func>readable\((?P<args>.*?)\))"), self._readable),
            (
                re.compile(r"(?:^|[\s\(])(?P<func>active\((?P<args>.*?)\))"),
                self._active,
            ),
            (re.compile(r"(?:^|[\s\(])(?P<func>many\((?P<args>.*?)\))"), self._many),
            (
                re.compile(r"(?:^|[\s\(])(?P<func>many_active\((?P<args>.*?)\))"),
                self._manyActive,
            ),
            (
                re.compile(r"(?:^|[\s\(])(?P<func>is_master\((?P<args>.*?)\))"),
                self._isMaster,
            ),
            (
                re.compile(r"(?:^|[\s\(])(?P<func>checksum\((?P<args>.*?)\))"),
                self._checksum,
            ),
            (
                re.compile(r"(?:^|[\s\(])(?P<func>version\((?P<args>.*?)\))"),
                self._version,
            ),
            (
                re.compile(r"(?:^|[\s\(])(?P<func>product_version\((?P<args>.*?)\))"),
                self._productVersion,
            ),
        )

    def evalCondition(self, condition: str, plugin: Optional[GamebryoPlugin] = None) -> bool:
        """Evaluate a LOOT masterlist condition.

        Strategy:
            - Extract functions, parse their arguments and evaluate them
            - Replace the functions with boolean values
            - Evaluate the resulting expression

        Args:
            condition (str): A condition to evaluate, as specified in the masterlist
            plugin (Optional[GamebryoPlugin]): The plugin to evaluate the condition for

        Returns:
            bool: True if the condition is met

        Raises:
            InvalidCondition: If the condition is invalid
        """
        qDebug(f"Evaluating condition: {condition}")
        # Temporarily replace strings to prevent function regexes from matching parentheses between quotes
        condition, strings = self._replaceStringsWithPlaceholders(condition)
        # Match and evaluate functions
        for lootFunctionRegex, mo2Function in self._functionMapping:
            for match in lootFunctionRegex.finditer(condition):
                # Replace strings back
                rawArgs = match.group("args").format(*strings)
                parsedArgs = self._parseArgs(mo2Function, rawArgs)
                # Evaluate and replace the function with its result
                result = self._evalFunction(mo2Function, parsedArgs, plugin)
                qDebug(f"{match.group('func').rsplit('(', 1)[0]}({rawArgs}) = {result}")
                condition = condition.replace(match.group("func"), str(result))
        result = _evalBooleanExpression(condition)
        qDebug(f"Final evaluation: {condition} = {result}")
        return result

    def _evalFunction(
        self, mo2Function: Callable, parsedArgs: Generator[Any, None, None], plugin: Optional[GamebryoPlugin] = None
    ) -> bool:
        """Evaluate a function.

        Args:
            mo2Function (Callable): The function to evaluate
            parsedArgs (Generator[Any, None, None]): The arguments to pass to the function
            plugin (Optional[GamebryoPlugin]): The plugin to evaluate the function for

        Returns:
            bool: The result of the function
        """
        if plugin is None or mo2Function != self._checksum:
            return mo2Function(*parsedArgs)
        # Special case: if filePath matches plugin path, use the CRC32 of the plugin in case it's already loaded
        filePath, expectedCRC = parsedArgs
        return plugin.crc == expectedCRC if filePath == plugin.path else self._checksum(filePath, expectedCRC)

    def _replaceStringsWithPlaceholders(self, condition: str) -> Tuple[str, List[str]]:
        """Replace strings in a condition with placeholders.

        Args:
            condition (str): A condition to evaluate, as specified in the masterlist

        Returns:
            Tuple[str, List[str]]: The condition with strings replaced with placeholders, and the list of strings
        """
        strings = []
        for match in self._STRING_RE.finditer(condition):
            string = match.group()
            condition = condition.replace(string, f"{{{len(strings)}}}")
            strings.append(string)
        return condition, strings

    def _parseArgs(self, function: Callable, rawArgs: str) -> Generator[Any, None, None]:
        """Parse arguments for a function.

        Args:
            function (Callable): The function to parse arguments for
            rawArgs (str): The raw arguments to parse

        Yields:
            Any: The parsed arguments

        Raises:
            InvalidCondition: If any of the arguments are invalid
        """
        parsedArgs = _splitOnUnquotedCommas(rawArgs)
        if function == self._checksum:
            # In the masterlist, checksum format is hexadecimal (without 0x or double quotes)
            parsedArgs[1] = int(parsedArgs[1], 16)
        elif function in (self._version, self._productVersion):
            # Convert comparison operator string to a function
            try:
                parsedArgs[2] = self._COMPARATORS[parsedArgs[2]]
            except KeyError:
                raise InvalidConditionError(f"Invalid comparator: {parsedArgs[2]}")
        for arg in parsedArgs:
            if isinstance(arg, str):
                try:
                    # Evaluate as raw strings to escape backslashes
                    yield literal_eval(f"r{arg}")
                except (
                    ValueError,
                    TypeError,
                    SyntaxError,
                    MemoryError,
                    RecursionError,
                ) as exc:
                    qCritical(f"Exception occurred while evaluating arg: {arg}:\n{exc}")
                    raise InvalidConditionError(f"Invalid arg: {arg}") from exc
            else:
                yield arg

    def _getAbsolutePath(self, relativePath: str) -> str:
        """Get the absolute path of a file.

        Args:
            relativePath (str): A path relative to the data directory

        Returns:
            str: The absolute path of the file

        Raises:
            FileNotFoundError: If the file does not exist
            InvalidConditionError: If the path is not in the game directory
        """
        if relativePath.startswith("../"):
            return self._getAbsolutePathOutsideDataDir(relativePath[3:])
        relativeDir, relativeFile = os.path.split(relativePath)
        if files := self._organizer.findFiles(relativeDir, lambda f: f == relativeFile):
            return files[0]
        raise FileNotFoundError(f"File not found: {relativePath}")

    def _getAbsolutePathOutsideDataDir(self, relativePath: str) -> str:
        """Get the absolute path of a file outside the data directory.

        Args:
            relativePath (str): A path relative to the game directory

        Returns:
            str: The absolute path of the file

        Raises:
            FileNotFoundError: If the file does not exist
            InvalidConditionError: If the path is not in the game directory
        """
        absolutePath = os.path.normpath(os.path.join(self._gameDir, relativePath))
        if absolutePath.startswith(self._gameDir):
            if self._isRootBuilderEnabled() and (
                files := self._organizer.findFiles("Root", lambda f: f == absolutePath[len(self._gameDir) + 1 :])
            ):
                qDebug(f"Found '{relativePath}' in Kezyma's Root Builder folder")
                return files[0]
            if os.path.exists(absolutePath):
                return absolutePath
            raise FileNotFoundError(f"File not found: {absolutePath}")
        raise InvalidConditionError(f"{relativePath} is not inside the game directory.")

    def _getAbsolutePaths(self, relativePattern: str) -> Generator[str, None, None]:
        """Get the absolute paths of files matching a pattern.

        Args:
            relativePattern (str): A pattern relative to the data directory to match files against

        Yields:
            str: The absolute paths of the files

        Raises:
            InvalidConditionError: If the pattern is invalid or not in the game directory
        """
        # returns -1 if the character is not found, so directory is "" if no slash is found
        # used in favor of `os.path.split` because patterns can contain backslashes
        splitIdx = relativePattern.rfind("/") + 1
        relativeDir, pattern = relativePattern[:splitIdx], f"{relativePattern[splitIdx:]}$"
        if relativeDir.startswith("../"):
            absoluteDir = os.path.normpath(os.path.join(self._gameDir, relativeDir[3:]))
            if not absoluteDir.startswith(self._gameDir):
                raise InvalidConditionError(f"{relativePattern} is not inside the game directory.")
            if self._isRootBuilderEnabled() and (
                files := self._organizer.findFiles(
                    os.path.join(absoluteDir[len(self._gameDir) + 1 :], "Root"), lambda f: bool(re.match(pattern, f))
                )
            ):
                qDebug(f"Found '{relativePattern}' in Kezyma's Root Builder folder")
                yield from files
            try:
                matchesRegex = re.compile(pattern).match
            except re.error as exc:
                raise InvalidConditionError(f"Invalid pattern: {pattern}") from exc
            for fileName in os.listdir(absoluteDir):
                if matchesRegex(fileName):
                    yield os.path.join(absoluteDir, fileName)
        elif files := self._organizer.findFiles(relativeDir, lambda f: bool(re.match(pattern, f))):
            yield from files

    def _isRootBuilderEnabled(self) -> bool:
        """Check if Kezyma's Root Builder is enabled.

        https://kezyma.github.io/?p=rootbuilder

        Returns:
            bool: True if Kezyma's Root Builder is enabled
        """
        return self._organizer.isPluginEnabled("RootBuilder")

    def _file(self, relativePathOrPattern: str) -> bool:
        """Check if a file exists.

        Args:
            relativePathOrPattern (str): A path or pattern relative to the data directory

        Returns:
            bool: True if the file exists

        Raises:
            InvalidConditionError: If the path or pattern is not in the game directory
        """
        if isRegex(relativePathOrPattern):
            return bool(next(self._getAbsolutePaths(relativePathOrPattern), False))
        try:
            absolutePath = self._getAbsolutePath(relativePathOrPattern)
        except FileNotFoundError:
            return False
        return os.path.isfile(absolutePath)

    def _readable(self, relativePath: str) -> bool:
        """Check if a file or directory is readable.

        Args:
            relativePath (str): A path relative to the data directory

        Returns:
            bool: True if the file or directory is readable
        """
        try:
            absolutePath = self._getAbsolutePath(relativePath)
        except FileNotFoundError:
            return False
        return os.access(absolutePath, os.R_OK)

    def _active(self, pluginNameOrPattern: str) -> bool:
        """Check if a plugin is active.

        Args:
            pluginNameOrPattern (str): The name or pattern of the plugin(s)

        Returns:
            bool: True if any plugin matching the name or pattern is active

        Raises:
            InvalidConditionError: If the pattern is invalid
        """
        if isRegex(pluginNameOrPattern):
            try:
                matchesRegex = re.compile(pluginNameOrPattern + "$").match
            except re.error as exc:
                raise InvalidConditionError(f"Invalid pattern: {pluginNameOrPattern}") from exc
            return any(
                matchesRegex(plugin) and self._pluginList.state(plugin) == mobase.PluginState.ACTIVE
                for plugin in self._pluginList.pluginNames()
            )
        return self._pluginList.state(pluginNameOrPattern) == mobase.PluginState.ACTIVE

    def _many(self, pattern: str) -> bool:
        """Check if more than one files matching the pattern are present.

        Args:
            pattern (str): A regex pattern to match against, relative to the data folder

        Returns:
            bool: True if more than one files are found

        Raises:
            InvalidConditionError: If the pattern is invalid or not in the game directory
        """
        oneFound = False
        for _ in self._getAbsolutePaths(pattern):
            if oneFound:
                return True
            oneFound = True
        return False

    def _manyActive(self, pattern: str) -> bool:
        """Check if more than one plugin matching the pattern are active.

        Args:
            pattern (str): A regex pattern to match against, relative to the data folder

        Returns:
            bool: True if more than one plugins are found

        Raises:
            InvalidConditionError: If the pattern is invalid
        """
        try:
            matchesRegex = re.compile(pattern + "$").match
        except re.error as exc:
            raise InvalidConditionError(f"Invalid pattern: {pattern}") from exc
        oneFound = False
        for plugin in self._pluginList.pluginNames():
            if matchesRegex(plugin) and self._organizer.isPluginEnabled(plugin):
                if oneFound:
                    return True
                oneFound = True
        return False

    def _isMaster(self, pluginName: str) -> bool:
        """Check if a plugin is ESM-flagged.

        Args:
            pluginName (str): The name of the plugin

        Returns:
            bool: True if the plugin is flagged as an ESM
        """
        return self._pluginList.isMaster(pluginName)

    def _checksum(self, filePath: str, expectedChecksum: int) -> bool:
        """Check if the CRC32 checksum of a file matches the expected checksum.

        Args:
            filePath (str): The path of the file relative to the data directory
            expectedChecksum (int): The expected checksum

        Returns:
            bool: True if the file was found and the checksum matches

        Raises:
            InvalidConditionError: If the file is not in the game directory
        """
        try:
            filePath = self._getAbsolutePath(filePath)
        except FileNotFoundError:
            return False
        if os.path.isfile(filePath):
            return _computeCRC32(filePath) == expectedChecksum
        return False

    def _version(
        self,
        relativeFilePath: str,
        givenVersion: str,
        comparisonOperator: Callable[[str, str], bool],
    ) -> bool:
        """Compare a binary or plugin file's version to a given version.

        Args:
            relativeFilePath (str): The path of the file relative to the data directory
            givenVersion (str): The version to compare to
            comparisonOperator (Callable[[str, str], bool]): The comparison operator to use

        Returns:
            bool: The result of the comparison

        Raises:
            InvalidConditionError: If the file is invalid or not in the game directory
        """
        try:
            absolutePath = self._getAbsolutePath(relativeFilePath)
        except FileNotFoundError:
            return False
        extension = os.path.splitext(relativeFilePath)[1]
        if os.path.isfile(absolutePath):
            if extension in (".exe", ".dll"):
                # "If filepath does not exist or does not have a version number, its version is assumed to be 0"
                actualVersion = mobase.VersionInfo(mobase.getFileVersion(absolutePath) or "0.0.0.0")
            elif extension in (".esp", ".esm", ".esl"):
                if origins := self._organizer.getFileOrigins(relativeFilePath):
                    mod = self._organizer.modList().getMod(origins[0])
                    actualVersion = mod.version()
                else:
                    return False
            else:
                raise InvalidConditionError(f"{relativeFilePath} is not a valid binary or plugin file.")
            return comparisonOperator(actualVersion, mobase.VersionInfo(givenVersion))
        return False

    def _productVersion(
        self,
        relativeFilePath: str,
        givenVersion: str,
        comparisonOperator: Callable[[str, str], bool],
    ) -> bool:
        """Compare a binary file's product version to a given version.

        Args:
            relativeFilePath (str): The path of the file relative to the data directory
            givenVersion (str): The version to compare to
            comparisonOperator (Callable[[str, str], bool]): The comparison operator to use

        Returns:
            bool: The result of the comparison

        Raises:
            InvalidConditionError: If the file is invalid or not in the game directory
        """
        try:
            absolutePath = self._getAbsolutePath(relativeFilePath)
        except FileNotFoundError:
            return False
        extension = os.path.splitext(relativeFilePath)[1]
        if os.path.isfile(absolutePath) and extension in (".exe", ".dll"):
            # "If filepath does not exist or does not have a version number, its version is assumed to be 0"
            version = mobase.getProductVersion(absolutePath) or "0.0.0.0"
            return comparisonOperator(version, givenVersion)
        raise InvalidConditionError(f"{relativeFilePath} is not a valid binary file.")
