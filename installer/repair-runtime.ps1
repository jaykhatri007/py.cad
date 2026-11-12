# Invoked with $pycadRuntimeFile set by the verified-download caller.
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pycadRuntimeFile) | Out-Null
Invoke-WebRequest -UseBasicParsing 'https://aka.ms/vc14/vc_redist.x64.exe' -OutFile $pycadRuntimeFile
$signature = Get-AuthenticodeSignature -LiteralPath $pycadRuntimeFile
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'Microsoft installer signature verification failed; nothing was executed'
}
try {
    # The application stays per-user; only the Microsoft runtime asks for UAC.
    $process = Start-Process -FilePath $pycadRuntimeFile -Verb RunAs -ArgumentList '/install','/passive','/norestart' -Wait -PassThru
} catch {
    throw ('Windows runtime authorization was cancelled or could not start. Approve the Microsoft UAC prompt and retry. ' + $_.Exception.Message)
}
if ($process.ExitCode -notin 0,3010,1638) {
    throw ('Microsoft runtime installation failed: ' + $process.ExitCode)
}
if ($process.ExitCode -eq 3010) {
    Write-Output 'Microsoft requests a Windows restart; restart if the dependency check still fails.'
}
