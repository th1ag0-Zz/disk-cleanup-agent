# Windows

Read before Inspect and again before Execute when the host is Windows.

## Run the scanner

`python3` is often missing or opens the Microsoft Store stub: try `py -3`, then `python`, and confirm the version is 3.9+. In PowerShell, pass paths in single quotes, for example `py -3 'C:\path\to\analyze.py' --root 'C:\Users\name'`.

Under WSL the scanner runs as Linux and covers the WSL filesystem. To analyze the Windows profile, run it with Windows Python.

## Review candidates

`cache_candidates` also covers each entry of `AppData\Local\Temp`, known tool caches under `AppData\Local`, `INetCache` and `CrashDumps`. Temp entries can belong to running installers or applications; files in use fail to delete, so report them instead of forcing.

The rest of `AppData\Local`, `AppData\Roaming`, `AppData\Local\Packages` and browser profiles hold settings, sessions and data: review per item and prefer the application's own clear-cache option.

For system-wide space (Windows Update, `hiberfil.sys`, `pagefile.sys`, `C:\Windows`), point the user to Settings > System > Storage (Storage Sense) or Disk Cleanup. These files are never deleted manually.

`cloud_only_files` counts OneDrive and other Files On-Demand placeholders at 0 allocated bytes. Deleting a synced file also deletes it from the cloud and other devices. To free local space in synced folders, suggest "Free up space" (online-only) in the sync client.

## Execute

Recheck each approved target with `Get-Item -LiteralPath` and refuse targets whose `Attributes` include `ReparsePoint`.

For permanent removal of an approved directory, use Python `shutil.rmtree` with the literal path; it removes junctions without deleting their targets. Windows PowerShell 5.1 `Remove-Item -Recurse` can follow junctions, so keep it away from directories that may contain them.

To send personal files to the Recycle Bin, use PowerShell with the literal path in single quotes:

```powershell
Add-Type -AssemblyName Microsoft.VisualBasic
[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('C:\path\to\folder', 'OnlyErrorDialogs', 'SendToRecycleBin')
[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('C:\path\to\file.zip', 'OnlyErrorDialogs', 'SendToRecycleBin')
```

Measure free space with the scanner's `disk` field or `Get-PSDrive C`.
