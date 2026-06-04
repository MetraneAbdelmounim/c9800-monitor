$files = Get-ChildItem -Recurse -Include "*.ts","*.html"
foreach ($f in $files) {
  $c = Get-Content $f.FullName -Raw
  # Backgrounds (reverse)
  $c = $c -replace '#1C1C1C','#0c1526'
  $c = $c -replace '#0F0F0F','#0a1120'
  $c = $c -replace '#242424','#0f1d35'
  $c = $c -replace '#2A2A2A','#1a2a44'
  $c = $c -replace '#333333','#141f33'
  # Text (reverse)
  $c = $c -replace '#F0EDED','#e8f0f8'
  $c = $c -replace '#A8A0A0','#8a9bb5'
  $c = $c -replace '#706868','#5a6f8a'
  $c = $c -replace '#504848','#3a4f6a'
  # Accents (reverse)
  $c = $c -replace '#C74634','#00c9ff'
  $c = $c -replace '#34C759','#00e68a'
  $c = $c -replace '#E8A838','#ffb020'
  $c = $c -replace '#E07830','#ff7b3a'
  $c = $c -replace '#9B72CF','#a78bfa'
  # Font (reverse)
  $c = $c -replace 'JetBrains Mono','DM Mono'
  Set-Content $f.FullName $c
}