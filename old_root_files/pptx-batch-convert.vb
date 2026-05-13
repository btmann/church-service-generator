Sub BatchSave()
' Opens each PPT in the target folder and saves as PPT97-2003 format

    Dim sFolder As String
    Dim sOutFolder As String
    Dim sPresentationName As String
    Dim oPresentation As Presentation

    ' Get the foldername:

    sFolder = InputBox("Folder containing PPT files to process", "Folder")

    If sFolder = "" Then
        Exit Sub
    End If

    ' Make sure the folder name has a trailing backslash
    If Right$(sFolder, 1) <> "\" Then
        sFolder = sFolder & "\"
    End If

    ' Are there PPT files there?
    If Len(Dir$(sFolder & "*.PPT")) = 0 Then
        MsgBox "Bad folder name or no PPT files in folder."
        Exit Sub
    End If

	sOutFolder = sFolder & "..\pptx\"

    ' Open and save the presentations
    sPresentationName = Dir$(sFolder & "*.PPT")
    While sPresentationName <> ""
        Set oPresentation = Presentations.Open(sFolder & sPresentationName, , , False)
        Call oPresentation.SaveAs(sOutFolder & sPresentationName & "x", ppSaveAsOpenXMLPresentation)
        oPresentation.Close
        sPresentationName = Dir$()
    Wend

    MsgBox "DONE"

End Sub

