' Launch Rnote Formula Helper (windowless)
Set fso = CreateObject("Scripting.FileSystemObject")
d = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.Run """" & d & "\.venv\Scripts\pythonw.exe"" """ & d & "\app.py""", 0, False
