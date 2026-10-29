# Public CC BY 4.0 UK wet/dry pothole benchmark, DOI 10.17632/tp95cdvgm8.1.
# Dib, Sirlantzis and Howells (2023). Preserve it as an external evaluation set.
param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('Potholes.zip','Dashcam-Front.mp4','Dashcam-Rear.mp4')][string]$FileName='Potholes.zip'
)
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$files=Invoke-RestMethod 'https://data.mendeley.com/public-api/datasets/tp95cdvgm8/files?folder_id=root&version=1'
$metadata=$files | Where-Object filename -EQ $FileName
if ($null -eq $metadata) { throw 'Requested benchmark file is missing' }
$target=Join-Path $OutputDirectory $FileName
if (Test-Path -LiteralPath $target) { throw "Refusing to overwrite $target" }
$temporary="$target.part"
Invoke-WebRequest -Uri $metadata.content_details.download_url -OutFile $temporary
$digest=(Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
if ($digest -ne $metadata.content_details.sha256_hash -or (Get-Item -LiteralPath $temporary).Length -ne $metadata.size) {
    throw 'Dataset hash or size mismatch; incomplete file retained as .part'
}
Move-Item -LiteralPath $temporary -Destination $target
@{
    metadata=$metadata
    doi='10.17632/tp95cdvgm8.1'
    authors=@('Jihad Dib','Konstantinos Sirlantzis','Gareth Howells')
    license='CC BY 4.0'
    license_url='https://creativecommons.org/licenses/by/4.0/'
    source='https://data.mendeley.com/datasets/tp95cdvgm8/1'
    sha256=$digest
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$target.provenance.json" -Encoding utf8
Write-Output "$FileName verified: $digest"
