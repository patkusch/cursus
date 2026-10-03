# Opens Visio files in Microsoft's free Visio Viewer and reports what it found.
#
# The Viewer is Microsoft's own code for reading and drawing .vsdx files. It is
# not Visio, and it cannot tell us whether Visio would ask to repair a file,
# but it is the closest thing to Visio that runs without a licence.
#
# Usage: powershell -STA -File scripts/open_in_visio_viewer.ps1 <out folder> <file or folder> [...]
param([Parameter(Mandatory)][string]$Out, [Parameter(Mandatory, ValueFromRemainingArguments)][string[]]$Paths)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -ReferencedAssemblies System.Windows.Forms -TypeDefinition @"
using System.Windows.Forms;
public class ViewerHost : AxHost {
    public ViewerHost(string clsid) : base(clsid) {}
    public object Ocx { get { return GetOcx(); } }
}
"@

$clsid = (Get-Item 'Registry::HKEY_CLASSES_ROOT\VisioViewer.Viewer\CLSID').GetValue('')
Write-Host "Viewer class $clsid, apartment $([Threading.Thread]::CurrentThread.ApartmentState)"
New-Item -ItemType Directory -Force $Out | Out-Null

$form = New-Object System.Windows.Forms.Form
$form.Text = 'cursus'; $form.Width = 1900; $form.Height = 900; $form.StartPosition = 'Manual'; $form.Left = 0; $form.Top = 0
$ax = New-Object ViewerHost($clsid.Trim('{}'))
$ax.Dock = 'Fill'
$form.Controls.Add($ax)
$form.Show()
[System.Windows.Forms.Application]::DoEvents()
$viewer = $ax.Ocx
Write-Host "Viewer build $($viewer.MajorVersionNumber).$($viewer.MinorVersionNumber).$($viewer.BuildNumber)"
try { $viewer.AlertsEnabled = $false } catch { Write-Host "AlertsEnabled: $_" }

function Pump([int]$ms) {
    $until = (Get-Date).AddMilliseconds($ms)
    while ((Get-Date) -lt $until) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 50 }
}

$files = foreach ($p in $Paths) { Get-ChildItem $p -Filter *.vsdx -File -ErrorAction SilentlyContinue; if (Test-Path $p -PathType Leaf) { Get-Item $p } }
$report = @()
foreach ($file in ($files | Sort-Object FullName -Unique)) {
    $row = [ordered]@{ file = $file.Name; loaded = $false; pages = 0; shapes = 0; error = ''; names = @(); data = @() }
    try { $viewer.Unload() } catch {}
    try {
        $viewer.Load($file.FullName)
        $waited = 0
        while (-not $viewer.DocumentLoaded -and $waited -lt 20000) { Pump 250; $waited += 250 }
        $row.loaded = [bool]$viewer.DocumentLoaded
        if ($row.loaded) {
            $row.pages = $viewer.PageCount
            $viewer.CurrentPageIndex = 1
            Pump 1500
            $row.shapes = $viewer.ShapeCount
            for ($i = 1; $i -le [Math]::Min($row.shapes, 60); $i++) {
                try { $row.names += $viewer.ShapeName($i) } catch { $row.names += "?($_)"; break }
                try {
                    $n = $viewer.CustomPropertyCount($i)
                    for ($j = 1; $j -le $n; $j++) {
                        $name = $viewer.CustomPropertyName($i, $j)
                        if ($name -match 'Source') { $row.data += "$($viewer.ShapeName($i)): $($viewer.CustomPropertyValue($i, $j))" }
                    }
                } catch {}
            }
            try { $viewer.Zoom = -1 } catch {}
            Pump 1000
            $shot = New-Object System.Drawing.Bitmap($form.ClientSize.Width, $form.ClientSize.Height)
            $g = [System.Drawing.Graphics]::FromImage($shot)
            $g.CopyFromScreen($form.PointToScreen([System.Drawing.Point]::Empty), [System.Drawing.Point]::Empty, $form.ClientSize)
            $shot.Save((Join-Path $Out ($file.BaseName + '.png')))
        }
    } catch { $row.error = "$_" }
    try { if (-not $row.loaded) { $row.error += " code=$($viewer.LastErrorCode) $($viewer.GetErrorMessage($viewer.LastErrorCode))" } } catch { $row.error += " (no error text: $_)" }
    Write-Host ("{0,-40} loaded={1} pages={2} shapes={3} {4}" -f $row.file, $row.loaded, $row.pages, $row.shapes, $row.error)
    $report += [pscustomobject]$row
}
$report | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $Out 'report.json') -Encoding UTF8
$form.Close()
