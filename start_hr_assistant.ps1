# HR Analytica Launcher
# Starts Streamlit server if not running, waits for readiness, opens browser.
Add-Type -AssemblyName System.Windows.Forms

$projectDir = "C:\Users\ASUS\Desktop\work\project-001-人力与财务数据分析报告助手"
Set-Location $projectDir

$port = 8501
$log = Join-Path $projectDir "streamlit_log.txt"
$err = Join-Path $projectDir "streamlit_err.txt"
$pythonExe = "C:\Users\ASUS\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

# Check if port is already serving
$running = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue

if (-not $running) {
    Add-Content -Path $log -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting Streamlit server..."
    $proc = Start-Process -FilePath $pythonExe -ArgumentList "-m","streamlit","run","app.py","--server.port","8501" -WorkingDirectory $projectDir -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
    # Wait up to 30 seconds for the server to be ready
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 1
        $running = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($running) { break }
    }
}

if ($running) {
    Start-Process "http://localhost:$port"
} else {
    Add-Content -Path $log -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: Server did not start within 30 seconds."
    [System.Windows.Forms.MessageBox]::Show("HR Analytica 启动失败，请查看 streamlit_err.txt", "启动失败")
}
