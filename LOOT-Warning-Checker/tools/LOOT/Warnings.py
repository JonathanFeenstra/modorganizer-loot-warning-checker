"""
Warnings
========

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
import re
from abc import ABC
from typing import Dict, List, Union

_MARKDOWN_BOLD_RE = re.compile(r"\*\*(?P<content>.*?)\*\*")
_MARKDOWN_HYPERLINK_RE = re.compile(r"\[(?P<content>.*?)\]\((?P<url>.*?)\)")


def _stripMarkdown(markdownText: str) -> str:
    """
    Strip markdown from a string.

    Currently only supports bold and hyperlinks.

    Args:
        markdownText (str): The markdown text to strip.

    Returns:
        str: The stripped text.
    """
    return re.sub(
        _MARKDOWN_BOLD_RE,
        r"\g<content>",
        re.sub(_MARKDOWN_HYPERLINK_RE, r"\g<content>", markdownText),
    )


def _convertMarkdownToHTML(markdownText: str) -> str:
    """
    Convert LOOT's markdown text to MO2's HTML.

    Currently only supports bold and hyperlinks.

    Args:
        markdownText (str): Markdown text

    Returns:
        str: HTML text
    """
    return re.sub(
        _MARKDOWN_HYPERLINK_RE,
        r'<a href="\g<url>">\g<content></a>',
        re.sub(_MARKDOWN_BOLD_RE, r"<b>\g<content></b>", markdownText),
    )


class LOOTWarning(ABC):
    """Warning returned by LOOT, to be displayed by MO2.

    Attributes:
        pluginName (str): Name of the plugin that caused the warning
        fullDescription (str): Full description of the warning. Supports HTML syntax.
        shortDescription (str): Short description of the warning. Does not support HTML syntax.
    """

    pluginName: str
    fullDescription: str
    shortDescription: str


class MessageWarning(LOOTWarning):
    """LOOT warning from a plugin entry's message list.

    Attributes:
        pluginName (str): Name of the plugin that caused the warning
        fullDescription (str): Full description of the warning
        shortDescription (str): Short description of the warning
    """

    def __init__(self, pluginName: str, msgData: Dict[str, Union[str, List]]) -> None:
        """
        Args:
            pluginName (str): Name of the plugin that caused the warning
            msgData (Dict[str, Union[str, List]]): Message datastructure
        """
        self.pluginName = pluginName
        content = msgData["content"]
        # content[0] = English localization
        content = content[0]["text"] if isinstance(content, list) else content
        if subs := msgData.get("subs", []):
            content = content.format(*subs)
        self.fullDescription = f"{pluginName}: {_convertMarkdownToHTML(content)}"
        self.shortDescription = f"{pluginName}: {_stripMarkdown(content)}"


class MissingRequirementWarning(LOOTWarning):
    """LOOT warning for when a plugin is missing a required file.

    Attributes:
        pluginName (str): Name of the plugin that caused the warning
        fullDescription (str): Full description of the warning
        shortDescription (str): Short description of the warning
        filePath (str): Path of the missing file
    """

    def __init__(self, pluginName: str, fileData: Union[str, Dict[str, str]]) -> None:
        """
        Args:
            pluginName (str): Name of the plugin that caused the warning
            fileData (Union[str, Dict[str, str]]): Path (str) or file datastructure (dict) of the missing file
        """
        self.pluginName = pluginName
        if isinstance(fileData, str):
            self.filePath = fileData
            content = f"{self.pluginName} requires '{self.filePath}' to be installed, but it is missing."
        else:
            self.filePath = fileData["name"]
            fileData.get("detail", "")
            content = (
                f"{self.pluginName} requires '{fileData.get('display', self.filePath)}' to be "
                f"installed, but it is missing. {fileData.get('detail', '')}"
            )
        self.shortDescription = _stripMarkdown(content)
        self.fullDescription = _convertMarkdownToHTML(content)


class IncompatibilityWarning(LOOTWarning):
    """LOOT warning for when a plugin is incompatible with a file.

    Attributes:
        pluginName (str): Name of the plugin that caused the warning
        fullDescription (str): Full description of the warning
        shortDescription (str): Short description of the warning
        filePath (str): Path of the incompatible file
    """

    def __init__(self, pluginName: str, fileData: Union[str, Dict[str, str]]) -> None:
        """
        Args:
            pluginName (str): Name of the plugin that caused the warning
            fileData (Union[str, Dict[str, str]]): Path (str) or file datastructure (dict) of the incompatible file
        """
        self.pluginName = pluginName
        if isinstance(fileData, str):
            self.filePath = fileData
            content = f"{self.pluginName} is incompatible with '{self.filePath}', but both are present."
        else:
            self.filePath = fileData["name"]
            fileData.get("detail", "")
            content = (
                f"{self.pluginName} is incompatible with '{fileData.get('display', self.filePath)}', but both "
                f"are present. {fileData.get('detail', '')}"
            )
        self.shortDescription = _stripMarkdown(content)
        self.fullDescription = _convertMarkdownToHTML(content)


class FormID_OutOfRangeWarning(LOOTWarning):
    """LOOT warning for light plugins with FormIDs that are out of range."""

    def __init__(self, pluginName: str) -> None:
        """
        Args:
            pluginName (str): Name of the plugin that caused the warning
        """
        self.pluginName = pluginName
        self.shortDescription = (
            f"{pluginName} contains records that have FormIDs outside the valid range for an ESL plugin. "
            "Using this plugin will cause irreversible damage to your game saves."
        )
        self.fullDescription = (
            f"{self.shortDescription}<br><br>If this plugin was uploaded in this "
            "state, the error should be reported to the author."
        )


class DirtyPluginWarning(LOOTWarning):
    """LOOT warning for a dirty plugin.

    See: https://loot.github.io/docs/help/Dirty-Edits,-Mod-Cleaning-&-CRCs.html

    Attributes:
        pluginName (str): Name of the plugin that caused the warning
        fullDescription (str): Full description of the warning
        shortDescription (str): Short description of the warning
        requiresManualFix (bool): Whether the plugin requires a manual fix
        itm (Optional[int]): Number of ITMs in the dirty plugin, or None if unknown
        udr (Optional[int]): Number of UDRs in the dirty plugin, or None if unknown
        nav (Optional[int]): Number of NAVs in the dirty plugin, or None if unknown
    """

    def __init__(self, pluginName: str, dirtyInfo: Dict) -> None:
        self.pluginName = pluginName
        # "intentional" ITMs are ignored by LOOT: https://github.com/loot/loot.github.io/issues/89
        self.itm = dirtyInfo.get("itm")
        self.udr = dirtyInfo.get("udr")
        self.nav = dirtyInfo.get("nav")
        content = _convertMarkdownToHTML(dirtyInfo["detail"])
        # If the plugin requires a manual fix, description will be:
        # "It is strongly recommended not to use mods that contain..."
        # Presence of NAV does not directly imply manual fix: quick clean can still be used on masters
        self.requiresManualFix = content.startswith("I")
        self.shortDescription = (
            f"{pluginName} is dirty and {'contains deleted navmeshes' if self.requiresManualFix else 'requires cleaning.'}"
        )
        if not self.requiresManualFix:
            self.fullDescription = f'{self.shortDescription} Click the "Fix" button to clean it.<br/><br/>{content}'
        else:
            self.fullDescription = f"{self.shortDescription}<br/><br/>{content}"
        if any((self.itm, self.udr, self.nav)):
            self.fullDescription += "<br/><br/>Details:<ul>"
            if self.itm is not None:
                self.fullDescription += f"<li>{self.itm} Identical To Master records (ITMs)</li>"
            if self.udr is not None:
                self.fullDescription += f"<li>{self.udr} Undeleted and Disabled References (UDRs)</li>"
            if self.nav is not None:
                self.fullDescription += f"<li>{self.nav} Deleted Navmeshes (NAVs)</li>"
            self.fullDescription += "</ul>"
