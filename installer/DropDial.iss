; Inno Setup script — per-user install, no admin rights needed.
#define AppVersion GetEnv("DS_VERSION")
#if AppVersion == ""
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{6C1E2B0A-7D5F-4E8B-9F3A-D7A5F1C2B3E4}
AppName=DropDial
AppVersion={#AppVersion}
AppPublisher=Prithwiraj Mukherjee
AppCopyright=Copyright (C) 2026 Prithwiraj Mukherjee. Made by Prithwiraj Mukherjee.
AppPublisherURL=https://github.com/prithwirajmukherjee15-cmd/DropDial
VersionInfoCompany=Prithwiraj Mukherjee
VersionInfoCopyright=Copyright (C) 2026 Prithwiraj Mukherjee
DefaultDirName={localappdata}\Programs\DropDial
DefaultGroupName=DropDial
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=DropDial-Setup
SetupIconFile=..\dropdial\assets\dropdial.ico
UninstallDisplayIcon={app}\DropDial.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; branded artwork (1x and 2x for high-DPI screens), made by packaging/make_art.py
WizardImageFile=wizard-large.bmp,wizard-large@2x.bmp
WizardSmallImageFile=wizard-small.bmp,wizard-small@2x.bmp
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "autostart"; Description: "Start DropDial when I sign in to Windows"; Flags: checkedonce
Name: "contextmenu"; Description: "Add ""DropDial"" to the right-click menu for files"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\DropDial\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\DropDial"; Filename: "{app}\DropDial.exe"
Name: "{autodesktop}\DropDial"; Filename: "{app}\DropDial.exe"; Tasks: desktopicon
Name: "{usersendto}\DropDial"; Filename: "{app}\DropDial.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DropDial"; ValueData: """{app}\DropDial.exe"" --quiet"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\*\shell\DropDial"; ValueType: string; ValueName: "MUIVerb"; ValueData: "DropDial…"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\DropDial"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\DropDial.exe"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DropDial"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DropDial\command"; ValueType: string; ValueName: ""; ValueData: """{app}\DropDial.exe"" ""%1"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\DropDial"; Flags: uninsdeletekey

[Run]
Filename: "{app}\DropDial.exe"; Description: "Launch DropDial now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM DropDial.exe"; Flags: runhidden; RunOnceId: "KillDropDial"
