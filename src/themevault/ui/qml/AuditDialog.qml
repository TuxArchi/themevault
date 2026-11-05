import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: dlg

    modal: true
    focus: true
    padding: 0
    width: 640
    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape

    property string backupId: ""
    property var report: null
    property bool busy: false
    property string errorText: ""
    property string exportedTo: ""

    signal notify(string message, bool error)

    function openFor(id) {
        backupId = id
        report = null
        errorText = ""
        exportedTo = ""
        busy = false
        open()
        backend.auditBackup(id)
    }

    function riskLabel(value) {
        if (value === "high") return "Alto"
        if (value === "medium") return "Medio"
        return "Bajo"
    }

    function riskColor(value) {
        if (value === "high") return Theme.danger
        if (value === "medium") return Theme.warn
        return Theme.ok
    }

    Connections {
        target: backend

        function onAuditReady(info) {
            if (!dlg.visible || info.id !== dlg.backupId)
                return
            dlg.report = info
            dlg.busy = false
        }

        function onSanitizedExported(info) {
            if (!dlg.visible || info.id !== dlg.backupId)
                return
            dlg.busy = false
            dlg.exportedTo = info.path || ""
            dlg.notify("Copia saneada creada", false)
        }

        function onFailed(action, message) {
            if (!dlg.visible)
                return
            if (action === "audit" || action === "sanitized") {
                dlg.busy = false
                dlg.errorText = message
            }
        }
    }

    Overlay.modal: Rectangle { color: "#9905050a" }

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
            spacing: 5

            Text {
                text: "Auditoría de la copia"
                color: Theme.text
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                text: "Qué datos personales contiene antes de compartirla."
                color: Theme.textDim
                font.pixelSize: 12
            }
        }

        Item { Layout.preferredHeight: 16 }

        ColumnLayout {
            visible: dlg.report === null && dlg.errorText === ""
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 26
            spacing: 8

            Text {
                text: "Analizando rutas, imágenes, dconf, shells y atajos…"
                color: Theme.textDim
                font.pixelSize: 12
            }
        }

        ColumnLayout {
            visible: dlg.errorText !== ""
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 26
            spacing: 8

            Text {
                Layout.fillWidth: true
                text: dlg.errorText
                color: Theme.danger
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
        }

        ColumnLayout {
            visible: dlg.report !== null
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            spacing: 10

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 46
                radius: Theme.radiusSmall
                color: Theme.surfaceAlt
                border.width: 1
                border.color: Theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10

                    Rectangle {
                        width: 9
                        height: 9
                        radius: 5
                        color: dlg.report ? dlg.riskColor(dlg.report.risk) : Theme.border
                    }

                    Text {
                        Layout.fillWidth: true
                        text: dlg.report ? "Riesgo: " + dlg.riskLabel(dlg.report.risk) : ""
                        color: Theme.text
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }

                    Text {
                        text: dlg.report && dlg.report.safe_to_share ? "Compartible" : "No compartir crudo"
                        color: dlg.report && dlg.report.safe_to_share ? Theme.ok : Theme.warn
                        font.pixelSize: 10
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                visible: (dlg.report && dlg.report.findings || []).length === 0
                text: "No se encontraron datos personales evidentes."
                color: Theme.ok
                font.pixelSize: 12
            }

            Repeater {
                model: dlg.report ? (dlg.report.findings || []) : []

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        Layout.fillWidth: true
                        text: "· " + modelData.label + " (" + modelData.count + ")"
                        color: modelData.severity === "high" ? Theme.danger
                               : (modelData.severity === "medium" ? Theme.warn : Theme.ok)
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                    }

                    Repeater {
                        model: modelData.examples || []

                        Text {
                            Layout.fillWidth: true
                            text: "    " + modelData
                            color: Theme.textFaint
                            font.pixelSize: 10
                            elide: Text.ElideMiddle
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.topMargin: 4
                text: "La copia original no se modifica. La copia saneada omite historial, shells, configuración privada de applets, atajos inseguros e imágenes."
                color: Theme.textFaint
                font.pixelSize: 10
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                visible: dlg.exportedTo.length > 0
                text: "Copia saneada: " + dlg.exportedTo
                color: Theme.ok
                font.pixelSize: 10
                wrapMode: Text.WordWrap
            }
        }

        Item { Layout.preferredHeight: 18 }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 24
            spacing: 10

            Item { Layout.fillWidth: true }

            AppButton {
                text: "Cerrar"
                variant: "ghost"
                onClicked: dlg.close()
            }

            AppButton {
                text: dlg.busy ? "Creando…" : "Exportar copia saneada"
                variant: "primary"
                enabled: dlg.report !== null && !dlg.busy
                onClicked: {
                    dlg.busy = true
                    backend.exportSanitized(dlg.backupId, "", true)
                }
            }
        }
    }
}
