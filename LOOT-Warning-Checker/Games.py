"""
Games
=====

Games supported by xEdit and LOOT.

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
from typing import NamedTuple

from .tools.LOOT import LOOTGame
from .tools.xEdit import xEditGame


class GameType(NamedTuple):
    xEditGame: xEditGame
    lootGame: LOOTGame


SUPPORTED_GAMES = {
    "Morrowind": GameType(xEditGame("xTES", "TES3"), LOOTGame("morrowind", "Morrowind")),
    "Oblivion": GameType(xEditGame("xTES", "TES4"), LOOTGame("oblivion", "Oblivion")),
    "Skyrim": GameType(xEditGame("xTES", "TES5"), LOOTGame("skyrim", "Skyrim")),
    "Skyrim Special Edition": GameType(xEditGame("xTES", "SSE"), LOOTGame("skyrimse", "Skyrim Special Edition")),
    "Skyrim VR": GameType(xEditGame("xTES", "TES5VR"), LOOTGame("skyrimvr", "Skyrim VR")),
    "Enderal": GameType(xEditGame("xTES", "Enderal"), LOOTGame("skyrim", "Enderal")),
    "Enderal Special Edition": GameType(
        xEditGame("xTES", "EnderalSE"),
        LOOTGame("enderal", "Enderal Special Edition"),
    ),
    "Nehrim": GameType(xEditGame("xTES", "TES4"), LOOTGame("oblivion", "Nehrim")),
    "Fallout 3": GameType(xEditGame("xFO", "FO3"), LOOTGame("fallout3", "Fallout3")),
    "New Vegas": GameType(xEditGame("xFO", "FNV"), LOOTGame("falloutnv", "FalloutNV")),
    "Fallout 4": GameType(xEditGame("xFO", "FO4"), LOOTGame("fallout4", "Fallout4")),
    "Fallout 4 VR": GameType(xEditGame("xFO", "FO4VR"), LOOTGame("fallout4vr", "Fallout4VR")),
}
