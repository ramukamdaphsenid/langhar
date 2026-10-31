#define AppName "Langhar"
#define AppVersion "1.0.0"
#define AppExeName "Langhar.exe"

[Setup]
AppId={{A4D9A126-1EB0-4A1A-A85E-2A1763A0E9A0}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Langhar
DefaultDirName={localappdata}\Programs\Langhar
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
OutputDir=..\..\dist\installer
OutputBaseFilename=Langhar-Setup
SetupIconFile=..\..\frontend\public\langhar-app.ico
UninstallDisplayIcon={app}\{#AppExeName}
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\..\dist\windows\Langhar\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Langhar"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Langhar"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Langhar"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent
