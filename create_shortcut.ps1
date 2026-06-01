# Crée un raccourci OpenVox sur le Bureau (icône incluse), lançant l'app sans console.
# Usage : clic droit → « Exécuter avec PowerShell », ou : powershell -File create_shortcut.ps1
$proj = $PSScriptRoot
$pythonw = Join-Path $proj ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Host "Environnement .venv introuvable. Fais d'abord l'installation (voir README)." -ForegroundColor Yellow
    return
}
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "OpenVox.lnk"))
$lnk.TargetPath = $pythonw
$lnk.Arguments = "main.py"
$lnk.WorkingDirectory = $proj
$lnk.IconLocation = Join-Path $proj "assets\icon.ico"
$lnk.Description = "OpenVox - lecture de la selection a voix haute"
$lnk.Save()
Write-Host "Raccourci OpenVox cree sur le Bureau." -ForegroundColor Green
