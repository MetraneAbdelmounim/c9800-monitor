---
name: powershell-bulk-edit-encoding
description: Bulk find/replace via PowerShell 5.1 corrupts UTF-8 non-ASCII chars in this project's files
metadata:
  type: feedback
---

When doing bulk find/replace across files in this project with Windows PowerShell 5.1, `Get-Content -Raw` reads as CP1252 (ANSI) by default and `Set-Content -Encoding utf8` writes a BOM — together they mojibake any non-ASCII characters (em-dash —, ellipsis …, box-drawing ─, ▲▼, the ⎋ logout glyph in Angular templates).

**Why:** the frontend source files are UTF-8 without BOM and contain these glyphs in templates/comments.

**How to apply:** for bulk edits, read/write with an explicit no-BOM UTF-8 encoding — `[IO.File]::ReadAllText($p, $utf8NoBom)` / `[IO.File]::WriteAllText($p, $s, $utf8NoBom)` where `$utf8NoBom = New-Object System.Text.UTF8Encoding($false)`. To reverse existing mojibake: strip BOM, then `utf8.GetString([Text.Encoding]::GetEncoding(1252).GetBytes(text))`. After any bulk edit, grep for `â|Ã|Â` to detect corruption.
