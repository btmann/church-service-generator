

Declare PtrSafe Function SetTimer Lib "user32" (ByVal hwnd As Long, ByVal nIDEvent As Long, ByVal uElapse As Long, ByVal _
    lpTimerFunc As LongPtr) As Long
Declare PtrSafe Function KillTimer Lib "user32" (ByVal hwnd As Long, ByVal nIDEvent As Long) As Long

Dim lngTimerID As Long
Dim blnTimer As Boolean


Sub PrintShapeID()
    Debug.Print getIDByName("Countdown", 1)
End Sub

Function getIDByName(shapeName As String, slide As Integer)
    Dim ap As Presentation: Set ap = ActivePresentation
    Dim sl As slide: Set sl = ap.Slides(slide)
    Dim sh As Shape: Set sh = sl.Shapes(shapeName)
    getIDByName = sh.Id
End Function


Function getShapeByName(shapeName As String, sl As slide)
    Dim sh As Shape: Set sh = sl.Shapes(shapeName)
    getShapeByName = sh
End Function


Sub StartOnTime()
    If blnTimer Then
        lngTimerID = KillTimer(0, lngTimerID)
        If lngTimerID = 0 Then
            MsgBox "Error : Timer Not Stopped"
            Exit Sub
        End If
        blnTimer = False
        
    Else
        lngTimerID = SetTimer(0, 0, 1000, AddressOf HelloTimer)
        If lngTimerID = 0 Then
            MsgBox "Error : Timer Not Generated "
            Exit Sub
        End If
        blnTimer = True
        
    End If
End Sub

Sub KillOnTime()
    lngTimerID = KillTimer(0, lngTimerID)
    blnTimer = False
End Sub

Sub HelloTimer()
    Dim diff As Date
    diff = Now - #10/17/2020 2:15:00 PM#
    Dim ActiveSlide As slide
    Set ActiveSlide = ActiveWindow.View.slide
    Dim CountdownShape As Shape
    CountdownShape = getShapeByName("Countdown", ActiveSlide)
    If diff > 0 Then
        KillOnTime
        With ActivePresentation
            .Slides(1).Shapes.Placeholders(2).TextFrame.TextRange.Text = "0:00"
        End With
    Else
        countDown = Minute(diff) & ":" & Format(Second(diff), "00")
        With ActivePresentation
            .Slides(1).Shapes.Placeholders(2).TextFrame.TextRange.Text = countDown
        End With
    End If
End Sub


Sub StartDeck()
    StartOnTime
End Sub

Sub OnSlideShowPageChange()
    Dim i As Integer
    i = ActivePresentation.SlideShowWindow.View.CurrentShowPosition
    If i <> 1 Then Exit Sub
    StartOnTime
End Sub

