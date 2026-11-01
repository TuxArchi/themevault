import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: bar

    property int currentIndex: 0
    property int backupCount: 0
    property string storageText: ""

    signal navigate(int index)
    signal newBackup()

    color: Theme.surface

    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Theme.border
    }

    component NavItem: Rectangle {
        id: nav

        property string label: ""
        property bool active: false

        signal activated()

        implicitHeight: 40
        radius: Theme.radiusSmall
        color: nav.active ? Theme.accentSoft : (hover.containsMouse ? Theme.surfaceHover : "transparent")

        Behavior on color {
            ColorAnimation { duration: 130 }
        }

        Rectangle {
            width: 3
            height: 16
            radius: 2
            color: Theme.accent
            visible: nav.active
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 16
            text: nav.label
            color: nav.active ? Theme.text : Theme.textDim
            font.pixelSize: 14
            font.weight: nav.active ? Font.DemiBold : Font.Normal
        }

        MouseArea {
            id: hover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: nav.activated()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 8

        RowLayout {
            Layout.topMargin: 2
            spacing: 12

            Rectangle {
                width: 38
                height: 38
                radius: 12

                gradient: Gradient {
                    GradientStop { position: 0; color: Theme.accent }
                    GradientStop { position: 1; color: Theme.accent2 }
                }

                Text {
                    anchors.centerIn: parent
                    text: "T"
                    color: "#ffffff"
                    font.pixelSize: 20
                    font.weight: Font.Black
                }
            }

            ColumnLayout {
                spacing: 0

                Text {
                    text: "ThemeVault"
                    color: Theme.text
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }

                Text {
                    text: "v" + Theme.appVersion
                    color: Theme.textFaint
                    font.pixelSize: 10
                }
            }
        }

        Item { Layout.preferredHeight: 14 }

        NavItem {
            Layout.fillWidth: true
            label: "Copias"
            active: bar.currentIndex === 0
            onActivated: bar.navigate(0)
        }

        NavItem {
            Layout.fillWidth: true
            label: "Comunidad"
            active: bar.currentIndex === 1
            onActivated: bar.navigate(1)
        }

        NavItem {
            Layout.fillWidth: true
            label: "Sistema"
            active: bar.currentIndex === 2
            onActivated: bar.navigate(2)
        }

        AppButton {
            Layout.fillWidth: true
            Layout.topMargin: 14
            text: "+  Nueva copia"
            variant: "primary"
            onClicked: bar.newBackup()
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: storage.implicitHeight + 28
            radius: Theme.radiusSmall + 2
            color: Theme.surfaceAlt
            border.width: 1
            border.color: Theme.border

            ColumnLayout {
                id: storage
                anchors.fill: parent
                anchors.margins: 14
                spacing: 5

                Text {
                    text: "ALMACENAMIENTO"
                    color: Theme.textFaint
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }

                Text {
                    Layout.fillWidth: true
                    text: bar.storageText
                    color: Theme.text
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }

                AppButton {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    text: "Abrir carpeta"
                    variant: "ghost"
                    small: true
                    onClicked: backend.openFolder()
                }
            }
        }
    }
}
