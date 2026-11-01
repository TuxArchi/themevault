import QtQuick
import QtQuick.Layouts

Item {
    id: card

    property string backupId: ""
    property string cardTitle: ""
    property string cardSubtitle: ""
    property string deLabel: ""
    property string sizeText: ""
    property string itemsText: ""
    property string thumb: ""
    property bool hasThumb: false
    property var covers: []
    property int coverIndex: 0
    property var swatches: []
    property string notes: ""

    signal opened()
    signal restoreRequested()

    function nextCover() {
        if (covers.length > 1)
            coverIndex = (coverIndex + 1) % covers.length
    }

    function prevCover() {
        if (covers.length > 1)
            coverIndex = (coverIndex - 1 + covers.length) % covers.length
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: card.opened()
    }

    Rectangle {
        id: body
        anchors.fill: parent
        radius: Theme.radius
        color: mouse.containsMouse ? Theme.surfaceHover : Theme.surface
        border.width: 1
        border.color: mouse.containsMouse ? Theme.accentLine : Theme.border
        clip: true

        Behavior on color {
            ColorAnimation { duration: 140 }
        }
        Behavior on border.color {
            ColorAnimation { duration: 140 }
        }

        // ---------------------------------------------------------- portada
        Item {
            id: media
            x: 0
            y: 0
            width: body.width
            height: Math.round(width * 9 / 16)
            clip: true

            Rectangle {
                anchors.fill: parent
                visible: !card.hasThumb

                gradient: Gradient {
                    GradientStop {
                        position: 0
                        color: card.swatches.length > 0 ? card.swatches[0] : "#20202e"
                    }
                    GradientStop {
                        position: 1
                        color: card.swatches.length > 1 ? card.swatches[1] : "#0e0e16"
                    }
                }

                Rectangle {
                    width: parent.height * 1.6
                    height: parent.height * 1.6
                    radius: height / 2
                    x: parent.width - width * 0.55
                    y: -height * 0.45
                    color: "#262dd4bf"
                }

                Rectangle {
                    width: parent.height
                    height: parent.height
                    radius: height / 2
                    x: -width * 0.35
                    y: parent.height * 0.55
                    color: "#1a6366f1"
                }
            }

            Image {
                anchors.fill: parent
                source: card.covers.length > 0
                        ? card.covers[Math.min(card.coverIndex, card.covers.length - 1)]
                        : card.thumb
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                visible: card.hasThumb
                scale: mouse.containsMouse ? 1.03 : 1.0

                Behavior on scale {
                    NumberAnimation { duration: 420; easing.type: Easing.OutCubic }
                }
            }

            // -------------------------------------------------- selector de monitor
            Rectangle {
                visible: card.covers.length > 1
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.margins: 10
                height: 20
                width: counter.implicitWidth + 14
                radius: 10
                color: "#b30a0a0f"

                Text {
                    id: counter
                    anchors.centerIn: parent
                    text: (card.coverIndex + 1) + " / " + card.covers.length
                    color: "#dcdce8"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                }
            }

            Rectangle {
                visible: card.covers.length > 1
                width: 42
                height: 42
                radius: 21
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 10
                color: "#d10a0a0f"
                border.width: 1
                border.color: prevArea.containsMouse ? Theme.accent : "#40ffffff"
                opacity: prevArea.containsMouse ? 1 : 0.78

                Behavior on opacity {
                    NumberAnimation { duration: 120 }
                }

                Text {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -1
                    text: "‹"
                    color: "#ffffff"
                    font.pixelSize: 26
                }

                MouseArea {
                    id: prevArea
                    objectName: "prevArrow"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: card.prevCover()
                }
            }

            Rectangle {
                visible: card.covers.length > 1
                width: 42
                height: 42
                radius: 21
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                // la portada trae el panel de muestras a la derecha (22,5 %):
                // las flechas quedan dentro del area del escritorio.
                anchors.rightMargin: Math.round(parent.width * 0.225) + 10
                color: "#d10a0a0f"
                border.width: 1
                border.color: nextArea.containsMouse ? Theme.accent : "#40ffffff"
                opacity: nextArea.containsMouse ? 1 : 0.78

                Behavior on opacity {
                    NumberAnimation { duration: 120 }
                }

                Text {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -1
                    text: "›"
                    color: "#ffffff"
                    font.pixelSize: 26
                }

                MouseArea {
                    id: nextArea
                    objectName: "nextArrow"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: card.nextCover()
                }
            }

            AppButton {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.margins: 12
                text: "Restaurar"
                variant: "subtle"
                small: true
                opacity: mouse.containsMouse ? 1 : 0
                enabled: opacity > 0.5

                Behavior on opacity {
                    NumberAnimation { duration: 160 }
                }

                onClicked: card.restoreRequested()
            }
        }

        // ----------------------------------------------------------- datos
        ColumnLayout {
            x: 14
            y: media.height + 12
            width: body.width - 28
            height: body.height - media.height - 20
            spacing: 4

            Text {
                Layout.fillWidth: true
                text: card.cardTitle
                color: Theme.text
                font.pixelSize: 15
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 1
                spacing: 8

                Rectangle {
                    height: 18
                    width: deText.implicitWidth + 14
                    radius: 9
                    color: Theme.accentSoft
                    border.width: 1
                    border.color: Theme.accentLine

                    Text {
                        id: deText
                        anchors.centerIn: parent
                        text: card.deLabel
                        color: Theme.text
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: card.cardSubtitle
                    color: Theme.textDim
                    font.pixelSize: 11
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Row {
                    spacing: 5

                    Repeater {
                        model: card.swatches.slice(0, 6)

                        Rectangle {
                            width: 20
                            height: 6
                            radius: 3
                            color: modelData
                            border.width: 1
                            border.color: "#22ffffff"
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    Layout.rightMargin: 14
                    text: card.itemsText
                    color: Theme.textFaint
                    font.pixelSize: 10
                    elide: Text.ElideLeft
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}
