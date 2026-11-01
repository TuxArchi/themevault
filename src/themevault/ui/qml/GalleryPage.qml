import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page

    property string pageId: "gallery"

    signal openBackup(string backupId)
    signal newBackup()
    signal restoreRequested(string backupId)

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 32
        anchors.rightMargin: 32
        anchors.topMargin: 26
        anchors.bottomMargin: 6
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            ColumnLayout {
                spacing: 4

                Text {
                    text: "Copias guardadas"
                    color: Theme.text
                    font.pixelSize: 26
                    font.weight: Font.DemiBold
                }

                Text {
                    text: backend.backupCount === 0
                          ? "Guardá el aspecto de tu escritorio y volvé a él cuando quieras"
                          : backend.backupCount + (backend.backupCount === 1 ? " copia" : " copias")
                            + "  ·  " + backend.storageSummary
                    color: Theme.textDim
                    font.pixelSize: 13
                }
            }

            Item { Layout.fillWidth: true }

            AppButton {
                text: "Actualizar"
                variant: "ghost"
                onClicked: backend.refresh()
            }

            AppButton {
                text: "+  Nueva copia"
                variant: "primary"
                onClicked: page.newBackup()
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            GridView {
                id: grid
                anchors.fill: parent
                visible: count > 0
                clip: true
                cacheBuffer: 600
                boundsBehavior: Flickable.StopAtBounds

                property int columns: Math.max(2, Math.floor(width / 340))
                cellWidth: Math.floor(width / columns)
                cellHeight: 360

                model: backend.backups

                add: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 240 }
                }

                displaced: Transition {
                    NumberAnimation { properties: "x,y"; duration: 200; easing.type: Easing.OutCubic }
                }

                ScrollBar.vertical: ScrollBar {
                    id: gridBar
                    policy: ScrollBar.AsNeeded

                    contentItem: Rectangle {
                        implicitWidth: 6
                        radius: 3
                        color: gridBar.pressed ? Theme.textDim : Theme.borderStrong
                        opacity: gridBar.active ? 1 : 0
                    }
                }

                delegate: Item {
                    width: grid.cellWidth
                    height: grid.cellHeight

                    BackupCard {
                        anchors.fill: parent
                        anchors.margins: 9
                        backupId: model.backupId
                        cardTitle: model.title
                        cardSubtitle: model.subtitle
                        deLabel: model.deLabel
                        sizeText: model.sizeText
                        itemsText: model.itemsText
                        thumb: model.thumb
                        hasThumb: model.hasThumb
                        covers: model.covers
                        swatches: model.palette
                        notes: model.notes

                        onOpened: page.openBackup(model.backupId)
                        onRestoreRequested: page.restoreRequested(model.backupId)
                    }
                }
            }

            Item {
                anchors.fill: parent
                visible: backend.backupCount === 0

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 14

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 78
                        height: 78
                        radius: 26
                        color: Theme.accentSoft
                        border.width: 1
                        border.color: Theme.accentLine

                        Text {
                            anchors.centerIn: parent
                            text: "+"
                            color: Theme.accent
                            font.pixelSize: 40
                            font.weight: Font.Light
                        }
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Todavía no hay copias"
                        color: Theme.text
                        font.pixelSize: 19
                        font.weight: Font.DemiBold
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.maximumWidth: 440
                        text: "ThemeVault guarda temas, iconos, cursores, fuentes, fondos y los ajustes del escritorio para poder volver a este aspecto cuando quieras."
                        color: Theme.textDim
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        lineHeight: 1.3
                    }

                    AppButton {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 8
                        text: "Crear la primera copia"
                        variant: "primary"
                        onClicked: page.newBackup()
                    }
                }
            }
        }
    }
}
