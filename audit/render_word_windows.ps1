param([string]$OutputDirectory = 'audit/gemini_revision_render')
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$renderDirectory = Join-Path $projectDirectory $OutputDirectory
New-Item -ItemType Directory -Path $renderDirectory -Force | Out-Null
# Dedicated hidden Word instance; never attach to or close the user's documents.
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    foreach ($name in @('DOCUMENTAZIONE_PROGETTO', 'PROJECT_DOCUMENTATION_EN')) {
        $document = $null
        try {
            $document = $word.Documents.Open((Join-Path $projectDirectory "$name.docx"), $false, $true)
            $document.ExportAsFixedFormat((Join-Path $renderDirectory "$name.pdf"), 17)
            Write-Output "$name exported"
        } finally {
            if ($null -ne $document) { $document.Close(0) }
        }
    }
} finally {
    $word.Quit()
}
