#ifndef MyAppVersion
  #define MyAppVersion "0.4.0"
#endif

#ifndef MySourceDir
  #define MySourceDir "..\dist\SVStudio"
#endif

#ifndef MyOutputDir
  #define MyOutputDir "..\dist"
#endif

[Setup]
AppId={{9125E867-9C7A-4F4A-8FD2-6DBE765E58A7}
AppName=SV Studio
AppVersion={#MyAppVersion}
AppVerName=SV Studio {#MyAppVersion}
AppPublisher=Bingyao Wang
AppPublisherURL=https://github.com/BingyaoWang/sv-studio
AppSupportURL=https://github.com/BingyaoWang/sv-studio/issues
AppUpdatesURL=https://github.com/BingyaoWang/sv-studio/releases
DefaultDirName={localappdata}\Programs\SV Studio
DefaultGroupName=SV Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#MyOutputDir}
OutputBaseFilename=SVStudio-Setup-x64-v{#MyAppVersion}
SetupIconFile=..\assets\branding\sv-studio.ico
UninstallDisplayIcon={app}\SVStudio.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SV Studio"; Filename: "{app}\SVStudio.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\SV Studio"; Filename: "{app}\SVStudio.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\SVStudio.exe"; Description: "Launch SV Studio"; Flags: nowait postinstall skipifsilent
