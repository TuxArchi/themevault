import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page

    property string pageId: "community"
    property var profiles: []
    property bool loading: false
    property string error: ""
    property string query: ""
    property string desktopFilter: ""

    signal notify(string message, bool error)

    function load(force) {
        loading = true
        error = ""
        backend.communityRefresh(force === true)
    }

    function visibleProfiles() {
        var out = []
        var q = page.query.trim().toLowerCase()
        for (var i = 0; i < page.profiles.length; i++) {
            var p = page.profiles[i]
            if (page.desktopFilter && p.desktop !== page.desktopFilter)
                continue
            if (q) {
                var hay = (p.name + " " + p.author + " " + p.description).toLowerCase()
                if (hay.indexOf(q) < 0)
                    continue
            }
            out.push(p)
        }
        return out
    }

    function countVisible() {
        return visibleProfiles().length
    }

    function requirementLabel(requires) {
        var parts = []
        var names = { plasma_style: "Estilo", color_scheme: "Esquema", icons: "Iconos", cursor: "Cursor", gtk: "GTK" }
        for (var key in names) {
            if (requires && requires[key])
                parts.push(names[key] + ": " + requires[key])
        }
        return parts
    }

    Component.onCompleted: load(false)

    Connections {
        target: backend

        function onCommunityProfiles(list) {
            page.loading = false
            page.error = ""
            page.profiles = list
        }

        function onCommunityApplied(r) {
            detail.close()
            var failed = (r.failures || []).length
            if (failed > 0)
                page.notify(r.failures[0][1] || "no se pudo aplicar el perfil", true)
            else
                page.notify("Perfil aplicado · " + r.applied + (r.applied === 1 ? " cambio" : " cambios"), false)
            if ((r.missing || []).length > 0)
                page.notify("Falta instalar: " + r.missing.join(", "), true)
        }

        function onFailed(action, message) {
            if (action === "community") {
                page.loading = false
                page.error = message
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 32
        anchors.rightMargin: 32
        anchors.topMargin: 26
        anchors.bottomMargin: 6
        spacing: 16

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                spacing: 4

                Text {
                    text: "Comunidad"
                    color: Theme.text
                    font.pixelSize: 26
                    font.weight: Font.DemiBold
                }

                Text {
                    text: "Perfiles de otras personas: configuración y captura, sin archivos ni datos personales"
                    color: Theme.textDim
                    font.pixelSize: 13
                }
            }

            Item { Layout.fillWidth: true }

            AppButton {
                text: "Actualizar"
                variant: "ghost"
                enabled: !page.loading
                onClicked: page.load(true)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            TextField {
                id: search
                Layout.preferredWidth: 300
                placeholderText: "Buscar por nombre o autor…"
                placeholderTextColor: Theme.textFaint
                color: Theme.text
                font.pixelSize: 12
                selectByMouse: true
                onTextChanged: page.query = text

                background: Rectangle {
                    implicitHeight: 36
                    radius: Theme.radiusInput
                    color: Theme.surfaceAlt
                    border.width: 1
                    border.color: search.activeFocus ? Theme.accentLine : Theme.border
                }
            }

            Repeater {
                model: [
                    { key: "", label: "Todos" },
                    { key: "kde", label: "KDE" },
                    { key: "gnome", label: "GNOME" },
                    { key: "xfce", label: "Xfce" }
                ]

                AppButton {
                    text: modelData.label
                    variant: page.desktopFilter === modelData.key ? "primary" : "ghost"
                    small: true
                    onClicked: page.desktopFilter = modelData.key
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: page.loading ? "Cargando…" : page.countVisible() + " perfiles"
                color: Theme.textFaint
                font.pixelSize: 11
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
                cacheBuffer: 400
                boundsBehavior: Flickable.StopAtBounds

                property int columns: Math.max(2, Math.floor(width / 320))
                cellWidth: Math.floor(width / columns)
                cellHeight: 330

                model: page.visibleProfiles()

                ScrollBar.vertical: ScrollBar {
                    id: communityBar
                    policy: ScrollBar.AsNeeded
                    contentItem: Rectangle {
                        implicitWidth: 6
                        radius: 3
                        color: communityBar.pressed ? Theme.textDim : Theme.borderStrong
                        opacity: communityBar.active ? 1 : 0
                    }
                }

                delegate: Item {
                    width: grid.cellWidth
                    height: grid.cellHeight

                    Rectangle {
                        id: card
                        anchors.fill: parent
                        anchors.margins: 9
                        radius: Theme.radius
                        color: Theme.surface
                        border.width: 1
                        border.color: hoverArea.containsMouse ? Theme.accentLine : Theme.border
                        clip: true

                        Image {
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: Math.round(parent.height * 0.58)
                            source: modelData.cover || ""
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            visible: status === Image.Ready
                        }

                        Rectangle {
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: Math.round(parent.height * 0.58)
                            gradient: Gradient {
                                GradientStop { position: 0; color: (modelData.palette && modelData.palette[0]) ? modelData.palette[0] : Theme.surfaceAlt }
                                GradientStop { position: 1; color: (modelData.palette && modelData.palette[1]) ? modelData.palette[1] : Theme.surface }
                            }

                            Image {
                                anchors.fill: parent
                                source: modelData.cover || ""
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                visible: status === Image.Ready
                            }
                        }

                        Rectangle {
                            anchors.top: parent.top
                            anchors.right: parent.right
                            anchors.margins: 10
                            height: 20
                            width: deText.implicitWidth + 14
                            radius: 10
                            color: "#c00a0a0f"
                            border.width: 1
                            border.color: "#33ffffff"

                            Text {
                                id: deText
                                anchors.centerIn: parent
                                text: (modelData.desktop || "").toUpperCase()
                                color: "#e9e9f2"
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                            }
                        }

                        ColumnLayout {
                            anchors.top: parent.top
                            anchors.topMargin: Math.round(parent.height * 0.58) + 12
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.leftMargin: 14
                            anchors.rightMargin: 14
                            anchors.bottomMargin: 12
                            spacing: 2

                            Text {
                                Layout.fillWidth: true
                                text: modelData.name || ""
                                color: Theme.text
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "@" + (modelData.author || "") + "  ·  " + (modelData.settings || 0) + " ajustes"
                                color: Theme.textDim
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }

                            Item { Layout.fillHeight: true }

                            Row {
                                spacing: 5

                                Repeater {
                                    model: (modelData.palette || []).slice(0, 5)

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
                        }

                        MouseArea {
                            id: hoverArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: detail.openFor(modelData)
                        }
                    }
                }
            }

            // estados vacíos
            ColumnLayout {
                anchors.centerIn: parent
                spacing: 10
                visible: !page.loading && page.error === "" && page.countVisible() === 0

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Sin resultados"
                    color: Theme.text
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Probá con otro texto o cambiá el filtro."
                    color: Theme.textDim
                    font.pixelSize: 12
                }
            }

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 10
                visible: page.error.length > 0

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 460
                    text: "No se pudo cargar la comunidad"
                    color: Theme.text
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 460
                    text: page.error
                    color: Theme.textDim
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }

                AppButton {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Reintentar"
                    variant: "primary"
                    onClicked: page.load(true)
                }
            }

            Text {
                anchors.centerIn: parent
                visible: page.loading
                text: "Cargando la comunidad…"
                color: Theme.textDim
                font.pixelSize: 13
            }
        }
    }

    // ------------------------------------------------------------- detalle
    Popup {
        id: detail

        property var item: ({})

        function openFor(data) {
            item = data
            open()
        }

        modal: true
        focus: true
        padding: 0
        width: 640
        anchors.centerIn: parent
        closePolicy: Popup.CloseOnEscape

        Overlay.modal: Rectangle { color: "#9905050a" }

        background: Rectangle {
            color: Theme.surface
            radius: 18
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 240
                radius: 18
                clip: true
                color: detail.item.palette && detail.item.palette.length > 0 ? detail.item.palette[0] : Theme.surfaceAlt

                Image {
                    anchors.fill: parent
                    source: detail.item.cover || ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    visible: status === Image.Ready
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 90
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#00000000" }
                        GradientStop { position: 1; color: "#e605050b" }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.topMargin: 18
                spacing: 6

                Text {
                    Layout.fillWidth: true
                    text: detail.item.name || ""
                    color: Theme.text
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "@" + (detail.item.author || "")
                        color: Theme.accent
                        font.pixelSize: 12

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: backend.openUrl("https://github.com/" + (detail.item.author || ""))
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "·  " + (detail.item.license || "")
                        color: Theme.textDim
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    text: detail.item.description || ""
                    color: Theme.textDim
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }

                Flow {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    spacing: 6

                    Repeater {
                        model: page.requirementLabel(detail.item.requires || ({}))

                        Rectangle {
                            height: 24
                            width: reqText.implicitWidth + 18
                            radius: 12
                            color: Theme.surfaceAlt
                            border.width: 1
                            border.color: Theme.border

                            Text {
                                id: reqText
                                anchors.centerIn: parent
                                text: modelData
                                color: Theme.textDim
                                font.pixelSize: 10
                            }
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    text: "Incluye: "
                          + (detail.item.wallpaper && (detail.item.wallpaper.kind || detail.item.wallpaper.file) ? "fondo, " : "")
                          + (detail.item.plugins || 0) + " plugins, "
                          + (detail.item.assets || 0) + " assets, "
                          + (detail.item.keybinds || 0) + " atajos seguros."
                    color: Theme.textDim
                    font.pixelSize: 10
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    text: "Los plugins son código de terceros: se instalan con hash y confirmación. Aplicar crea un punto de retorno."
                    color: Theme.textFaint
                    font.pixelSize: 10
                    wrapMode: Text.WordWrap
                }
            }

            Item { Layout.preferredHeight: 16 }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.bottomMargin: 22
                spacing: 10

                Item { Layout.fillWidth: true }

                AppButton {
                    text: "Cerrar"
                    variant: "ghost"
                    onClicked: detail.close()
                }

                AppButton {
                    text: backend.busy ? "Aplicando…" : "Aplicar perfil"
                    variant: "primary"
                    enabled: !backend.busy
                    onClicked: applyDialog.openFor(detail.item)
                }
            }
        }
    }

    Popup {
        id: applyDialog

        property var item: ({})
        property bool confirmed: false

        readonly property int plugins: item.plugins || 0
        readonly property int assets: item.assets || 0
        readonly property bool needsConsent: plugins > 0 || assets > 0
        readonly property bool hasWallpaper: !!(item.wallpaper && (item.wallpaper.kind || item.wallpaper.file))

        function openFor(data) {
            item = data
            confirmed = false
            open()
        }

        modal: true
        focus: true
        padding: 0
        width: 560
        anchors.centerIn: parent
        closePolicy: Popup.CloseOnEscape

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
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.topMargin: 22
                spacing: 5

                Text {
                    Layout.fillWidth: true
                    text: "Aplicar «" + (applyDialog.item.name || "perfil") + "»"
                    color: Theme.text
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    text: "Esto va a cambiar tu escritorio actual. Se crea un punto de retorno antes de aplicar."
                    color: Theme.textDim
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                }
            }

            Item { Layout.preferredHeight: 14 }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: 5

                Text {
                    Layout.fillWidth: true
                    text: "Se descargará"
                    color: Theme.textFaint
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }

                Text {
                    Layout.fillWidth: true
                    text: "· profile.json"
                          + (applyDialog.hasWallpaper ? "  ·  fondo" : "")
                          + (applyDialog.plugins > 0 ? "  ·  " + applyDialog.plugins + " plugins" : "")
                          + (applyDialog.assets > 0 ? "  ·  " + applyDialog.assets + " assets" : "")
                    color: Theme.textDim
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    text: "Se aplicará"
                    color: Theme.textFaint
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }

                Text {
                    Layout.fillWidth: true
                    text: "· Apariencia y ajustes seguros"
                          + (applyDialog.hasWallpaper ? "  ·  fondo" : "")
                          + (applyDialog.plugins > 0 ? "  ·  instalación de plugins" : "")
                    color: Theme.textDim
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    text: "Queda manual"
                    color: Theme.textFaint
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }

                Text {
                    Layout.fillWidth: true
                    text: "· Atajos y layout: se muestran en el perfil, pero todavía no se aplican solos."
                    color: Theme.textDim
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.topMargin: 12
                implicitHeight: consentRow.implicitHeight + 20
                radius: Theme.radiusSmall
                color: Theme.surfaceAlt
                border.width: 1
                border.color: Theme.border
                visible: applyDialog.needsConsent

                RowLayout {
                    id: consentRow
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            Layout.fillWidth: true
                            text: "Código de terceros"
                            color: Theme.warn
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "Se instalarán " + applyDialog.plugins + " plugins y "
                                  + applyDialog.assets + " assets con hash verificado. Revisá su licencia antes de continuar."
                            color: Theme.textFaint
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }

                    AppSwitch {
                        checked: applyDialog.confirmed
                        onToggled: function(value) { applyDialog.confirmed = value }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.topMargin: 16
                Layout.bottomMargin: 22
                spacing: 10

                Item { Layout.fillWidth: true }

                AppButton {
                    text: "Cancelar"
                    variant: "ghost"
                    onClicked: applyDialog.close()
                }

                AppButton {
                    text: "Aplicar"
                    variant: "primary"
                    enabled: !applyDialog.needsConsent || applyDialog.confirmed
                    onClicked: {
                        applyDialog.close()
                        backend.communityApply(applyDialog.item.id, true)
                    }
                }
            }
        }
    }
}
