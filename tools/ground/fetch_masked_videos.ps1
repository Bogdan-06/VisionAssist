# Ihsan, Harjoko and Amrizal (2024), Pothole Videos V3, CC BY 4.0.
# This is labelled evaluation media, not model weights. No training uses these files.
param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$expectedHash='34a98a297f2e29c646cbdada37d820d2c8648e2ed5d15a28f72744d365fe9522'
$expectedBytes=1025786813
$files=Invoke-RestMethod 'https://data.mendeley.com/public-api/datasets/5bwfg4v4cd/files?folder_id=root&version=3'
$metadata=@($files | Where-Object filename -EQ 'pothole_video.zip')
if ($metadata.Count -ne 1) { throw 'Expected exactly one published video archive' }
$metadata=$metadata[0]
if ($metadata.content_details.sha256_hash -ne $expectedHash -or $metadata.size -ne $expectedBytes) {
    throw 'Published archive metadata changed; inspect before downloading'
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$target=Join-Path $OutputDirectory 'pothole_video.zip'
$temporary=$target+'.part'
if ((Test-Path -LiteralPath $target) -or (Test-Path -LiteralPath $temporary)) {
    throw 'An archive or partial download already exists; inspect it instead of overwriting'
}
$ProgressPreference='SilentlyContinue'
Invoke-WebRequest -Uri $metadata.content_details.download_url -OutFile $temporary
$digest=(Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
if ($digest -ne $expectedHash -or (Get-Item -LiteralPath $temporary).Length -ne $expectedBytes) {
    throw 'Archive checksum or size mismatch; partial file retained'
}
Move-Item -LiteralPath $temporary -Destination $target
@{
    doi='10.17632/5bwfg4v4cd.3'
    authors=@('Muhammad Ihsan','Agus Harjoko','Muhammad Alfian Amrizal')
    license='CC BY 4.0'
    license_url='https://creativecommons.org/licenses/by/4.0/'
    source='https://data.mendeley.com/datasets/5bwfg4v4cd/3'
    paper='https://doi.org/10.1016/j.dib.2024.110131'
    sha256=$digest
    bytes=$expectedBytes
    metadata=$metadata
    intended_use='External labelled-video evaluation only; not used for training'
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ($target+'.provenance.json') -Encoding UTF8
Write-Output "Verified pothole_video.zip: $digest"
