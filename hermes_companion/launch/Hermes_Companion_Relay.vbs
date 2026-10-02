' Hermes Companion - LAN Relay autostart (hidden)
' Launches the fleet relay at boot. The relay reads its token from
' %LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt (auto-created).
Option Explicit
Dim shell
Set shell = CreateObject("WScript.Shell")
Dim here
here = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run "cmd.exe /c """ & here & "\companion-relay.cmd""", 0, False
