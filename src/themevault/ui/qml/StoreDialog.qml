import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: store

    modal: true
    focus: true
    padding: 0
    width: 780
    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape

    property var results: []
    property bool searching: false
    property bool installing: false
    property string status: ""
    property bool failed: false

    signal notify(string message, bool error)

    function openWith(text) {
        input.text = text || ""
        results = []
        status = ""
        failed = false
        open()
        if (input.text.length > 0)
            doSearch()
        else
            input.forceActiveFocus()
    }

    function doSearch() {
        if (input.text.trim().length === 0 || searching || installing)
            return
        searching = true
        failed = false
        status = "Buscando en la tienda…"
        backend.searchStore(input.text.trim())
    }

    function install(item) {
        if (installing)
            return
        installing = true
        failed = false
        status = "Instalando " + item.name + "…"
        backend.installStoreWidget(item.id)
    }

    Connections {
        target: backend

        function onStoreResults(list) {
            store.searching = false
            store.results = list
            store.failed = false
            store.status = (list && list.length > 0) ? "" : "Sin resultados para esa búsqueda."
        }

        function onStoreInstalled(info) {
            store.installing = false
            store.status = "Instalado: " + info.name
            store.notify("Widget instalado: " + info.name, false)
        }

        function onFailed(action, message) {
            if (action !== "store_search" && action !== "store_install")
                return
            store.searching = false
            store.installing = false
            store.failed = true
            store.status = message
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
            spacing: 4

            Text {
                text: "Tienda de widgets"
                color: Theme.text
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }

            Text {
                text: "store.kde.org · se instala con KPackage en tu usuario"
                color: Theme.textDim
                font.pixelSize: 12
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.topMargin: 16
            spacing: 10

            TextField {
                id: input
                Layout.fillWidth: true
                placeholderText: "Buscar: reloj, clima, sistema…"
                placeholderTextColor: Theme.textFaint
                color: Theme.text
                font.pixelSize: 13
                selectByMouse: true

                background: Rectangle {
                    implicitHeight: 40
                    radius: Theme.radiusInput
                    color: Theme.surfaceAlt
                    border.width: 1
                    border.color: input.activeFocus ? Theme.accentLine : Theme.border
                }

                Keys.onReturnPressed: store.doSearch()
            }

            AppButton {
                text: "Buscar"
                variant: "primary"
                enabled: !store.searching && !store.installing
                onClicked: store.doSearch()
            }
        }

        Item { Layout.preferredHeight: 14 }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.preferredHeight: Math.min(380, Math.max(120, contentHeight))
            visible: count > 0
            clip: true
            spacing: 6
            model: store.results

            ScrollBar.vertical: ScrollBar {
                id: bar
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle {
                    implicitWidth: 6
                    radius: 3
                    color: bar.pressed ? Theme.textDim : Theme.borderStrong
                }
            }

            delegate: Rectangle {
                width: list.width
                height: 76
                radius: Theme.radiusSmall
                color: hoverArea.containsMouse ? Theme.surfaceHover : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 12

                    Rectangle {
                        width: 56
                        height: 56
                        radius: 10
                        color: Theme.surfaceAlt
                        border.width: 1
                        border.color: Theme.border
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: modelData.preview || ""
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            visible: (modelData.preview || "").length > 0
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            Layout.fillWidth: true
                            text: modelData.name || ""
                            color: Theme.text
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            text: (modelData.author || "") + "  ·  " + (modelData.downloads || "") + " descargas"
                            color: Theme.textFaint
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            text: modelData.summary || ""
                            color: Theme.textDim
                            font.pixelSize: 10
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }
                    }

                    AppButton {
                        text: "Instalar"
                        variant: "subtle"
                        small: true
                        enabled: !store.installing
                        onClicked: store.install(modelData)
                    }
                }

                MouseArea {
                    id: hoverArea
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                }
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.topMargin: 10
            visible: store.status.length > 0
            text: store.status
            color: store.failed ? Theme.danger : Theme.textDim
            font.pixelSize: 11
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.topMargin: 8
            Layout.fillWidth: true
            text: "Es código de terceros: se instala en tu carpeta personal con kpackagetool6."
            color: Theme.textFaint
            font.pixelSize: 10
            wrapMode: Text.WordWrap
        }

        Item { Layout.preferredHeight: 18 }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 22
            spacing: 10

            Item { Layout.fillWidth: true }

            AppButton {
                text: "Cerrar"
                variant: "primary"
                onClicked: store.close()
            }
        }
    }
}
