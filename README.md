# LOOT Warning Checker
![Downloads](https://img.shields.io/github/downloads/JonathanFeenstra/modorganizer-loot-warning-checker/total)
![License](https://img.shields.io/github/license/JonathanFeenstra/modorganizer-loot-warning-checker)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer) plugin to check for [LOOT](https://github.com/loot/loot) warnings and display them as notifications, without needing to sort the load order. Also available on [Nexus Mods](https://nexusmods.com/site/mods/323).

![example](/img/example.png)

## Features
- Parse LOOT's masterlist and userlist to diagnose your modlist for warnings
- Display the warnings as notifications in Mod Organizer
- Guided fix for cleaning dirty plugins using [xEdit](https://github.com/TES5Edit/TES5Edit) (unless a manual fix is required)
- Configurable settings to:
    - Enable/disable automatically updating LOOT's masterlist
    - Enable/disable displaying non-warning messages
    - Set the paths of the LOOT masterlist and the xEdit executable
    - Set the path of the game's Data-directory to use in xEdit (the [`-D:<path>` command line argument](https://tes5edit.github.io/docs/2-overview.html#CommandLineSwitches))
    - Ignore warnings that match any regular expressions listed in a specified file
- Tool menu option to quickly toggle whether to check for LOOT warnings
- Support for:
    - Morrowind
    - Oblivion
    - Skyrim
    - Skyrim Special Edition
    - Skyrim VR
    - Enderal
    - Enderal Special Edition
    - Nehrim
    - Fallout 3
    - Fallout New Vegas
    - Fallout 4
    - Fallout 4 VR
    - Starfield

## Installation
Add the [LOOT-Warning-Checker folder](/LOOT-Warning-Checker) to your Mod Organizer plugins folder or install it using [Kezyma's Plugin Finder](https://www.nexusmods.com/skyrimspecialedition/mods/59869). Remove the contents of the existing folder before updating to a newer version.