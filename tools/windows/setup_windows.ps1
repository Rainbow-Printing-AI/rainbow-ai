# Rainbow tools - Windows setup for the shop PC (RAINBOW-AI).
# Start it with SETUP-WINDOWS.cmd (double-click; it asks for admin). Safe to run again.
#
# Installs, all users:  Python 3.12, Git for Windows (bash), poppler (pdftoppm/pdftotext),
#                       LibreOffice, the pinned Python packages in requirements.txt.
# Sets:                 PYTHONUTF8=1 machine-wide (UTF-8 files and pipes, same as the Mac).
# Checks:               Virtual Machine Platform + VT-x, which Claude's Cowork workspace needs.
# Then runs the same test suites the Mac passes. Log: setup_log.txt next to this script.
# ASCII only on purpose: Windows PowerShell 5.1 reads BOM-less scripts as ANSI.

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'
$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$tools   = Split-Path -Parent $here
$rainbow = Split-Path -Parent $tools
$log     = Join-Path $here 'setup_log.txt'
Start-Transcript -Path $log -Force | Out-Null

$results = [ordered]@{}
$reboot  = $false

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Step($name) { Write-Host ''; Write-Host "== $name" -ForegroundColor Cyan }
function Mark($name, $ok, $note = '') {
    $results[$name] = @([bool]$ok, $note)
    if ($ok) { Say "   OK    $name $note" 'Green' } else { Say "   FAIL  $name $note" 'Red' }
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Add-MachinePath($dir) {
    $mp = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    if (($mp -split ';') -notcontains $dir) {
        [Environment]::SetEnvironmentVariable('Path', ($mp.TrimEnd(';') + ';' + $dir), 'Machine')
    }
    Refresh-Path
}
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget-Install($id, $extra) {
    Say "   winget install $id ..."
    $wa = @('install', '-e', '--id', $id, '--accept-package-agreements', '--accept-source-agreements',
            '--disable-interactivity') + $extra
    & winget @wa | Out-Host
}

# ---------------------------------------------------------------------------------------------
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Say 'Not running as admin. Close this and double-click SETUP-WINDOWS.cmd instead.' 'Red'
    Stop-Transcript | Out-Null
    exit 1
}

Step 'Rainbow folder'
$leaf = Split-Path -Leaf $rainbow
Mark 'Folder is named Rainbow' ($leaf -eq 'Rainbow') "($rainbow)"
if ($leaf -ne 'Rainbow') { Say '   Rename the folder to Rainbow - the skills look for it under that name.' 'Yellow' }
foreach ($sub in 'tools', 'PriceBook') {
    Mark "$sub\ present" (Test-Path (Join-Path $rainbow $sub))
}

Step 'Windows + Cowork virtualization'
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
Say "   $($os.Caption), build $($os.BuildNumber), PC name $env:COMPUTERNAME"
if ($os.Caption -match 'Home') {
    Say '   Windows HOME: no Remote Desktop host and no Hyper-V. Upgrade to Pro (checklist step 01).' 'Yellow'
}
$vmp = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
if ($vmp.State -ne 'Enabled') {
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart | Out-Null
    $reboot = $true
    Mark 'Virtual Machine Platform' $true '(just turned on - restart before using Claude)'
} else {
    Mark 'Virtual Machine Platform' $true '(on)'
}
$inVM = [bool]($cs.Model -match 'Virtual Machine|VMware|VirtualBox')
$fw   = [bool]((Get-CimInstance Win32_Processor | Select-Object -First 1).VirtualizationFirmwareEnabled)
if ($inVM) {
    Say '   This Windows is itself a VM (Hyper-V guest). Cowork runs its own VM inside it, which needs' 'Yellow'
    Say '   nested virtualization. On the HOST, shut this VM down, then in an admin PowerShell run:' 'Yellow'
    Say "     Set-VMProcessor -VMName '$env:COMPUTERNAME' -ExposeVirtualizationExtensions `$true" 'Yellow'
    Say '   (use the name shown in Hyper-V Manager if it differs; keep the VM on static RAM).' 'Yellow'
    Mark 'CPU virtualization' $fw '(guest view - False until nested virtualization is exposed)'
} else {
    Mark 'CPU virtualization (VT-x)' ($fw -or $cs.HypervisorPresent) '(if FAIL: turn on Intel Virtualization Technology in the BIOS)'
}

if (-not (Have 'winget')) {
    Mark 'winget' $false '- install "App Installer" from the Microsoft Store, then run this again'
    Stop-Transcript | Out-Null
    exit 1
}

# ---------------------------------------------------------------------------------------------
Step 'Python 3.12 (all users)'
function Find-Py {
    $p = Join-Path $env:ProgramFiles 'Python312\python.exe'
    if (Test-Path $p) { return $p }
    if (Have 'py') {
        $q = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $q) { return "$q".Trim() }
    }
    return $null
}
$py = Find-Py
if (-not $py) {
    Winget-Install 'Python.Python.3.12' @('--scope', 'machine', '--override',
        '/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 Include_test=0')
    Refresh-Path
    $py = Find-Py
}
Mark 'Python 3.12' ([bool]$py) "$py"

Step 'Git for Windows (bash for the test runner and Claude Code)'
$bash = Join-Path $env:ProgramFiles 'Git\bin\bash.exe'
if (-not (Test-Path $bash)) { Winget-Install 'Git.Git' @('--scope', 'machine'); Refresh-Path }
Mark 'Git bash' (Test-Path $bash) "$bash"

Step 'Poppler (pdftoppm renders every verify; pdftotext for the sheet audit)'
function Find-Poppler($roots) {
    $hit = Get-ChildItem $roots -Recurse -Filter pdftoppm.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { return $hit.DirectoryName }
    return $null
}
if (-not (Have 'pdftoppm')) {
    $pdir = Find-Poppler @('C:\Tools\poppler')
    if (-not $pdir) {
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $rel   = Invoke-RestMethod 'https://api.github.com/repos/oschwartz10612/poppler-windows/releases/latest' `
                        -Headers @{ 'User-Agent' = 'rainbow-setup' }
            $asset = $rel.assets | Where-Object { $_.name -like '*.zip' } | Select-Object -First 1
            $zip   = Join-Path $env:TEMP $asset.name
            Say "   downloading $($asset.name) ..."
            Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
            New-Item -ItemType Directory -Force 'C:\Tools\poppler' | Out-Null
            Expand-Archive $zip -DestinationPath 'C:\Tools\poppler' -Force
            $pdir = Find-Poppler @('C:\Tools\poppler')
        } catch {
            Say "   GitHub download failed ($($_.Exception.Message)) - trying winget" 'Yellow'
        }
    }
    if (-not $pdir) {
        Winget-Install 'oschwartz10612.Poppler' @('--scope', 'machine')
        Refresh-Path
        if (-not (Have 'pdftoppm')) {
            $pdir = Find-Poppler @((Join-Path $env:ProgramFiles 'WinGet\Packages'),
                                   (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'))
        }
    }
    if ($pdir) { Add-MachinePath $pdir }
}
$popOk = (Have 'pdftoppm') -and (Have 'pdftotext')
$popV  = ''
if ($popOk) { $popV = "$(& pdftoppm -v 2>&1 | Select-Object -First 1)" }
Mark 'poppler' $popOk "$popV"

Step 'LibreOffice (renders the counter price sheets to PDF)'
$soffice = Join-Path $env:ProgramFiles 'LibreOffice\program\soffice.exe'
if (-not (Test-Path $soffice)) { Winget-Install 'TheDocumentFoundation.LibreOffice' @('--scope', 'machine') }
Mark 'LibreOffice' (Test-Path $soffice)

Step 'PYTHONUTF8=1'
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'Machine')
$env:PYTHONUTF8 = '1'
Mark 'PYTHONUTF8=1 (machine-wide)' $true

Step 'Python packages (pinned to the Mac VM versions)'
if ($py) {
    & $py -m pip install --disable-pip-version-check -r (Join-Path $here 'requirements.txt') | Out-Host
    Mark 'pip install -r requirements.txt' ($LASTEXITCODE -eq 0)
    & $py -c "import pikepdf, pypdf, reportlab, PIL, numpy, img2pdf, pdfplumber, openpyxl, fontTools, docx, pillow_heif, uharfbuzz, potrace; print('   all imports ok')" | Out-Host
    Mark 'Python imports' ($LASTEXITCODE -eq 0)
} else {
    Mark 'Python packages' $false '(no Python)'
}

# ---------------------------------------------------------------------------------------------
Step 'Test suites (the same ones the Mac passes)'
if ($py -and (Test-Path $bash) -and $popOk) {
    Say '   tools/tests/run_tests.sh (about 1-2 minutes) ...'
    Push-Location $tools
    $tout = & $bash 'tests/run_tests.sh' 2>&1
    $rc = $LASTEXITCODE
    Pop-Location
    $tout | Out-Host
    $n = @($tout | Where-Object { "$_" -match '^PASS' }).Count
    Mark 'tools tests' ($rc -eq 0) "(exit 0; $n PASS lines - 45 on a fresh copy, 46 on re-runs)"

    Push-Location (Join-Path $rainbow 'PriceBook')
    & $py tests/test_pricebook.py 2>&1 | Out-Host
    Mark 'PriceBook tests' ($LASTEXITCODE -eq 0)
    & $py pricebook.py validate 2>&1 | Out-Host
    Mark 'PriceBook validate' ($LASTEXITCODE -eq 0)
    & $py sheets/audit_sheets.py 2>&1 | Out-Host
    Mark 'Counter-sheet audit' ($LASTEXITCODE -eq 0)
    if (Test-Path $soffice) {
        $sheetTmp = Join-Path $env:TEMP 'rainbow_sheet_build_test'
        New-Item -ItemType Directory -Force $sheetTmp | Out-Null
        & $py sheets/build_sheets.py --out $sheetTmp 2>&1 | Out-Host
        Mark 'Counter-sheet rebuild (to TEMP, real sheets untouched)' ($LASTEXITCODE -eq 0)
    }
    Say '   sample lookup:'
    & $py pricebook.py find 24x36 color 2>&1 | Select-Object -First 4 | Out-Host
    Pop-Location
} else {
    Mark 'Test suites' $false '(skipped - Python, Git bash or poppler missing)'
}

# ---------------------------------------------------------------------------------------------
Step 'Summary'
$fails = @($results.Keys | Where-Object { -not $results[$_][0] })
foreach ($k in $results.Keys) {
    if ($results[$k][0]) { Say ("   OK    " + $k) 'Green' } else { Say ("   FAIL  " + $k + " " + $results[$k][1]) 'Red' }
}
Write-Host ''
if ($reboot) { Say 'RESTART WINDOWS before you open Claude (Virtual Machine Platform was just turned on).' 'Yellow' }
if ($fails.Count -eq 0) {
    Say 'RESULT  PASS - the Rainbow tools are ready on this PC.' 'Green'
} else {
    Say "RESULT  FAIL - $($fails.Count) item(s). Give Claude this file: $log" 'Red'
}
Stop-Transcript | Out-Null
