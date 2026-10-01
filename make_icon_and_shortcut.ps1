# Build icon.ico and create the Desktop shortcut for Rnote Formula Helper (ASCII-only script)
$ErrorActionPreference = "Continue"
$base = $PSScriptRoot

# ---- icon ----
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap(64, 64)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::Transparent)
$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$r = 16
$w = 62
$path.AddArc(2, 2, $r, $r, 180, 90)
$path.AddArc($w - $r, 2, $r, $r, 270, 90)
$path.AddArc($w - $r, $w - $r, $r, $r, 0, 90)
$path.AddArc(2, $w - $r, $r, $r, 90, 90)
$path.CloseFigure()
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 58, 92, 168))
$g.FillPath($brush, $path)
$font = New-Object System.Drawing.Font("Segoe UI", 28, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$sf = New-Object System.Drawing.StringFormat
$sf.Alignment = [System.Drawing.StringAlignment]::Center
$sf.LineAlignment = [System.Drawing.StringAlignment]::Center
$rect = New-Object System.Drawing.RectangleF(0, 0, 64, 64)
$g.DrawString("fx", $font, [System.Drawing.Brushes]::White, $rect, $sf)
$g.Dispose()
$hicon = $bmp.GetHicon()
$icon = [System.Drawing.Icon]::FromHandle($hicon)
$icoPath = Join-Path $base "icon.ico"
$fs = [System.IO.File]::Create($icoPath)
$icon.Save($fs)
$fs.Close()
Write-Output ("icon: " + (Test-Path $icoPath))

# ---- shortcut ----
$pyw = Join-Path $base ".venv\Scripts\pythonw.exe"
Write-Output ("pythonw: " + (Test-Path $pyw))
if (Test-Path $pyw) {
    $name = [System.IO.File]::ReadAllText((Join-Path $base "shortcut_name.txt"), [System.Text.Encoding]::UTF8).Trim()
    $desktop = [Environment]::GetFolderPath("Desktop")
    $lnk = Join-Path $desktop ($name + ".lnk")
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath = $pyw
    $sc.Arguments = '"' + (Join-Path $base "app.py") + '"'
    $sc.WorkingDirectory = $base
    $sc.IconLocation = $icoPath
    $sc.Description = "Rnote Formula Helper"
    $sc.Save()
    Write-Output ("shortcut: " + (Test-Path $lnk))
    Write-Output ("shortcut path: " + $lnk)
} else {
    Write-Output "pythonw not found - shortcut skipped"
}
