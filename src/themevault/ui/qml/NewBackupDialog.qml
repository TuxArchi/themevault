import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: dlg

    modal: true
    focus: true
    padding: 0
    width: 540
    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape

    property bool withPreview: true

    function openDialog() {
        labelInput.text = ""
        withPreview = true
        previewSwitch.checked = true
        open()
        labelInput.forceActiveFocus()
    }

    function create() {
        backend.createBackup(labelInput.text, "", dlg.withPreview)
        close()
    }

    Overlay.modal: Rectangle {
        color: "#9905050a"
    }

    background: Rectangle {
        color: Theme.surface
        radius: 18
        border.width: 1
        border.color: Theme.border
    }

    contentItem: ColumnLayout {
        spacing: 0

        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.topMargin: 24
            spacing: 6

            Text {
                text: "Nueva copia"
                color: Theme.text
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }

            Text {
                text: "Se guardan temas, iconos, cursores, fuentes, fondos y los ajustes del escritorio detectado."
                color: Theme.textDim
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        Item { Layout.preferredHeight: 18 }

        Text {
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 6
            text: "NOMBRE (OPCIONAL)"
            color: Theme.textFaint
            font.pixelSize: 10
            font.weight: Font.DemiBold
            font.letterSpacing: 0.8
        }

        TextField {
            id: labelInput
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            placeholderText: "Ej. Catppuccin Mocha de verano"
            placeholderTextColor: Theme.textFaint
            color: Theme.text
            font.pixelSize: 13
            selectByMouse: true

            background: Rectangle {
                implicitHeight: 42
                radius: Theme.radiusInput
                color: Theme.surfaceAlt
                border.width: 1
                border.color: labelInput.activeFocus ? Theme.accentLine : Theme.border

                Behavior on border.color {
                    ColorAnimation { duration: 120 }
                }
            }

            Keys.onReturnPressed: dlg.create()
        }

        Item { Layout.preferredHeight: 16 }

        Rectangle {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            implicitHeight: 62
            radius: Theme.radiusSmall
            color: Theme.surfaceAlt

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Text {
                    text: "Incluir portada (captura y fondo)"
                    color: Theme.text
                    font.pixelSize: 12
                }

                Text {
                    text: "Si lo desactivás, la copia solo guarda configuración y no copia imágenes."
                    color: Theme.textFaint
                    font.pixelSize: 10
                }
            }

            AppSwitch {
                id: previewSwitch
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                checked: dlg.withPreview
                onToggled: function(value) { dlg.withPreview = value }
            }
        }

        Item { Layout.preferredHeight: 24 }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 24
            spacing: 10

            Item { Layout.fillWidth: true }

            AppButton {
                text: "Cancelar"
                variant: "ghost"
                onClicked: dlg.close()
            }

            AppButton {
                text: "Crear copia"
                variant: "primary"
                enabled: !backend.busy
                onClicked: dlg.create()
            }
        }
    }
}
