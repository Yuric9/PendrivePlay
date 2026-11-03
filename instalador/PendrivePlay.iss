; Script do Inno Setup: gera o instalador PendrivePlay_Instalador.exe
; Ele é rodado pelo CRIAR_INSTALADOR.bat (ou pelo GitHub Actions).

#define AppNome "PendrivePlay"
#define AppVersao "1.0.0"
#define AppExe "PendrivePlay.exe"

[Setup]
; O AppId identifica o programa no Windows. Não mude depois de publicar.
AppId={{004D7D46-E793-49DC-B6EE-E2CD55F68290}
AppName={#AppNome}
AppVersion={#AppVersao}
AppVerName={#AppNome} {#AppVersao}
DefaultDirName={autopf}\{#AppNome}
DefaultGroupName={#AppNome}
DisableProgramGroupPage=yes
; Instala sem pedir senha de administrador (na pasta do usuário).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\saida
OutputBaseFilename=PendrivePlay_Instalador_{#AppVersao}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\PendrivePlay\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppNome}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppNome}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppNome}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppNome}}"; Flags: nowait postinstall skipifsilent
