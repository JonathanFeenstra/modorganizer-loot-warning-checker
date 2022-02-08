"""
xEdit
=====

Detection of the xEdit executable for Quick Auto Clean.

Copyright (C) 2021-2022 Jonathan Feenstra

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
import winreg
from typing import NamedTuple

from PyQt5.QtCore import qDebug


class xEditGame(NamedTuple):
    """Game supported by xEdit.

    Attributes:
        generalPrefix (str): Prefix of the franchise's executable ("xTES" for The Elder Scrolls, "xFO" for Fallout)
        specificPrefix (str): Prefix of the game's executable ("SSE" for Skyrim Special Edition, "FO3" for Fallout 3)
    """

    generalPrefix: str
    specificPrefix: str


def scan_xEditDirectoryForExecutable(xEditDir: str, game: xEditGame) -> str:
    """Scan the xEdit directory for the executable of the specified game and return its path when found.

    Args:
        xEditDir (str): The path to the xEdit directory
        game (xEditGame): The game to search the executable for

    Returns:
        str: The path to the xEdit executable, or None if not found

    Raises:
        FileNotFoundError: If the specified xEdit directory is not a directory, or no executable is found
    """
    qDebug(f"Scanning {xEditDir} for {game.specificPrefix}, {game.generalPrefix} or xEdit")
    if not os.path.isdir(xEditDir):
        qDebug(f"{xEditDir} is not a directory")
        raise FileNotFoundError(f"{xEditDir} is not a directory")

    for fileName in os.listdir(xEditDir):
        qDebug(f"Checking {fileName}...")
        if compile_xEditFileNameRegex(game).match(fileName):
            qDebug(f"Found {fileName}")
            return os.path.join(xEditDir, fileName)
    raise FileNotFoundError(f"Could not find {game.specificPrefix}Edit, {game.generalPrefix}Edit or xEdit in {xEditDir}")


def compile_xEditFileNameRegex(game: xEditGame) -> re.Pattern:
    """Return the regex pattern to match the xEdit executable for the specified game.

    Args:
        game (xEditGame): The game to search the executable for

    Returns:
        re.Pattern: The regex pattern to match the xEdit executable for the specified game

    Raises:
        re.error: If the regex pattern is invalid
    """
    return re.compile(fr"(?:{game.specificPrefix}|{game.generalPrefix}|x)Edit\.(?:exe|lnk)")


def get_xEditPathFromRegistry(specificPrefix: str) -> str:
    """Return the path to the xEdit executable from the registry.

    Args:
        specificPrefix (str): The specific prefix of the game's executable

    Returns:
        str: The path to the xEdit executable

    Raises:
        OSError: If an error occurs while reading the registry
    """
    with winreg.ConnectRegistry(None, winreg.HKEY_CLASSES_ROOT) as key:
        with winreg.OpenKey(key, f"{specificPrefix}Script") as subkey:
            return winreg.QueryValue(subkey, "DefaultIcon")
