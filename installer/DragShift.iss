; Inno Setup script — per-user install, no admin rights needed.
#define AppVersion GetEnv("DS_VERSION")
#if AppVersion == ""
  #define AppVersion "2.0.0"
#endif

[Setup]
AppId={{6C1E2B0A-7D5F-4E8B-9F3A-D7A5F1C2B3E4}
AppName=DragShift
AppVersion={#AppVersion}
AppPublisher=Prithwiraj Mukherjee
AppCopyright=Copyright (C) 2026 Prithwiraj Mukherjee. Made by Prithwiraj Mukherjee.
AppPublisherURL=https://github.com/prithwirajmukherjee15-cmd/dragshift
VersionInfoCompany=Prithwiraj Mukherjee
VersionInfoCopyright=Copyright (C) 2026 Prithwiraj Mukherjee
DefaultDirName={localappdata}\Programs\DragShift
DefaultGroupName=DragShift
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=DragShift-Setup
SetupIconFile=..\dragshift\assets\dragshift.ico
UninstallDisplayIcon={app}\DragShift.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "autostart"; Description: "Start DragShift when I sign in to Windows"; Flags: checkedonce
Name: "contextmenu"; Description: "Add ""DragShift"" to the right-click menu for files"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\DragShift\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\DragShift"; Filename: "{app}\DragShift.exe"
Name: "{autodesktop}\DragShift"; Filename: "{app}\DragShift.exe"; Tasks: desktopicon
Name: "{usersendto}\DragShift"; Filename: "{app}\DragShift.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DragShift"; ValueData: """{app}\DragShift.exe"" --quiet"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\*\shell\DragShift"; ValueType: string; ValueName: "MUIVerb"; ValueData: "DragShift…"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\DragShift"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\DragShift.exe"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DragShift"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DragShift\command"; ValueType: string; ValueName: ""; ValueData: """{app}\DragShift.exe"" ""%1"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\DragShift"; Flags: uninsdeletekey

[Run]
Filename: "{app}\DragShift.exe"; Description: "Launch DragShift now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM DragShift.exe"; Flags: runhidden; RunOnceId: "KillDragShift"
