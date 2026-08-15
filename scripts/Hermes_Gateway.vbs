' Hermes Gateway launcher. Retries only immediate Python startup failures.
Option Explicit
Dim sh, env, fso, cfg, cfg_file, line, base_home
Dim home, repo, python, existing_pp, attempt, exit_code, started, elapsed
Set sh = CreateObject("WScript.Shell")
Set env = sh.Environment("PROCESS")
Set fso = CreateObject("Scripting.FileSystemObject")
home = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\hermes"
repo = home & "\hermes-agent"
python = repo & "\.venv\Scripts\python.exe"
cfg = repo & "\.venv\pyvenv.cfg"
If fso.FileExists(cfg) Then
  Set cfg_file = fso.OpenTextFile(cfg, 1)
  Do Until cfg_file.AtEndOfStream
    line = Trim(cfg_file.ReadLine)
    If LCase(Left(line, 7)) = "home = " Then
      base_home = Trim(Mid(line, 8))
      If fso.FileExists(base_home & "\python.exe") Then
        python = base_home & "\python.exe"
      End If
      Exit Do
    End If
  Loop
  cfg_file.Close
End If
env.Item("HERMES_HOME") = home
env.Item("PYTHONIOENCODING") = "utf-8"
env.Item("HERMES_GATEWAY_DETACHED") = "1"
env.Item("VIRTUAL_ENV") = repo & "\.venv"
existing_pp = env.Item("PYTHONPATH")
If Len(existing_pp) > 0 Then
  env.Item("PYTHONPATH") = repo & "\.venv\Lib\site-packages;" & repo & ";" & existing_pp
Else
  env.Item("PYTHONPATH") = repo & "\.venv\Lib\site-packages;" & repo
End If
sh.CurrentDirectory = home

attempt = 0
Do
  attempt = attempt + 1
  started = Timer
  On Error Resume Next
  exit_code = sh.Run(Chr(34) & python & Chr(34) & " -m hermes_cli.main gateway run", 0, True)
  If Err.Number <> 0 Then
    exit_code = 1
    Err.Clear
  End If
  On Error GoTo 0
  elapsed = Timer - started
  If elapsed < 0 Then elapsed = elapsed + 86400
  If exit_code = 0 Or elapsed >= 30 Or attempt >= 3 Then Exit Do
  WScript.Sleep 2000 * attempt
Loop
WScript.Quit exit_code
