import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page

    property string pageId: "detail"
    property string backupId: ""
    property var info: ({})
    property var metaRows: []
    property int heroIndex: 0

    signal back()
    signal restoreRequested()
    signal shareRequested(string notes, string name)

    function load() {
        var detail = backend.detail(backupId || "")
        info = detail
        heroIndex = 0
        var i = detail || {}
        metaRows = [
            { label: "Sistema", value: i.distro || "—" },
            { label: "Escritorio", value: i.deLabel || "—" },
            { label: "Sesión", value: i.session || "—" },
            { label: "Contenido", value: i.itemsText || "—" },
            { label: "Tamaño", value: i.sizeText || "—" }
        ]
    }

    function themeName(key) {
        var t = page.info.themes || {}
        return t[key] || "—"
    }

    function itemPreview(items) {
        var list = items || []
        var out = []
        for (var i = 0; i < Math.min(list.length, 3); i++)
            out.push("· " + list[i].name)
        if (list.length > 3)
            out.push("+" + (list.length - 3) + " más")
        return out.join("\n")
    }

    Component.onCompleted: load()
    onBackupIdChanged: load()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppButton {
                text: "‹  Copias"
                variant: "ghost"
                small: true
                onClicked: page.back()
            }

            Item { Layout.fillWidth: true }

            AppButton {
                text: "Eliminar"
                variant: "danger"
                small: true
                onClicked: deleteDialog.open()
            }

            AppButton {
                text: "Compartir…"
                variant: "ghost"
                small: true
                onClicked: page.shareRequested(page.info.notes || "", page.info.label || "")
            }

            AppButton {
                text: "Ver carpeta"
                variant: "ghost"
                small: true
                onClicked: backend.openFolder()
            }

            AppButton {
                text: "Restaurar…"
                variant: "primary"
                enabled: !backend.busy
                onClicked: page.restoreRequested()
            }
        }

        ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ScrollBar.vertical: ScrollBar {
                id: detailBar
                policy: ScrollBar.AsNeeded

                contentItem: Rectangle {
                    implicitWidth: 6
                    radius: 3
                    color: detailBar.pressed ? Theme.textDim : Theme.borderStrong
                    opacity: detailBar.active ? 1 : 0
                }
            }

            ColumnLayout {
                width: scroll.availableWidth
                spacing: 20

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 18

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 360
                        radius: Theme.radius
                        color: Theme.surfaceAlt
                        clip: true

                        Rectangle {
                            anchors.fill: parent
                            visible: !page.info.hasHero
                            gradient: Gradient {
                                GradientStop {
                                    position: 0
                                    color: (page.info.palette || []).length > 0 ? page.info.palette[0] : "#1b1b28"
                                }
                                GradientStop {
                                    position: 1
                                    color: (page.info.palette || []).length > 1 ? page.info.palette[1] : "#0d0d14"
                                }
                            }
                        }

                        Image {
                            anchors.fill: parent
                            source: {
                                var list = page.info.heroes || []
                                if (list.length > 0)
                                    return list[Math.min(page.heroIndex, list.length - 1)]
                                return page.info.hero || ""
                            }
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            visible: page.info.hasHero === true
                        }

                        // ---------------------------------------- selector de monitor
                        Rectangle {
                            visible: (page.info.heroes || []).length > 1
                            anchors.top: parent.top
                            anchors.right: parent.right
                            anchors.margins: 14
                            height: 24
                            width: heroCounter.implicitWidth + 16
                            radius: 12
                            color: "#b30a0a0f"

                            Text {
                                id: heroCounter
                                anchors.centerIn: parent
                                text: {
                                    var list = page.info.screens || []
                                    var screen = list[page.heroIndex] || {}
                                    var pos = (page.heroIndex + 1) + " / " + (page.info.heroes || []).length
                                    return screen.name ? screen.name + "   " + pos : pos
                                }
                                color: "#dcdce8"
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                            }
                        }

                        Rectangle {
                            visible: (page.info.heroes || []).length > 1
                            width: 46
                            height: 46
                            radius: 23
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 14
                            color: "#d10a0a0f"
                            border.width: 1
                            border.color: heroPrevArea.containsMouse ? Theme.accent : "#40ffffff"
                            opacity: heroPrevArea.containsMouse ? 1 : 0.8

                            Behavior on opacity {
                                NumberAnimation { duration: 120 }
                            }

                            Text {
                                anchors.centerIn: parent
                                anchors.verticalCenterOffset: -1
                                text: "‹"
                                color: "#ffffff"
                                font.pixelSize: 28
                            }

                            MouseArea {
                                id: heroPrevArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var n = (page.info.heroes || []).length
                                    if (n > 0) page.heroIndex = (page.heroIndex - 1 + n) % n
                                }
                            }
                        }

                        Rectangle {
                            visible: (page.info.heroes || []).length > 1
                            width: 46
                            height: 46
                            radius: 23
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.rightMargin: 14
                            color: "#d10a0a0f"
                            border.width: 1
                            border.color: heroNextArea.containsMouse ? Theme.accent : "#40ffffff"
                            opacity: heroNextArea.containsMouse ? 1 : 0.8

                            Behavior on opacity {
                                NumberAnimation { duration: 120 }
                            }

                            Text {
                                anchors.centerIn: parent
                                anchors.verticalCenterOffset: -1
                                text: "›"
                                color: "#ffffff"
                                font.pixelSize: 28
                            }

                            MouseArea {
                                id: heroNextArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var n = (page.info.heroes || []).length
                                    if (n > 0) page.heroIndex = (page.heroIndex + 1) % n
                                }
                            }
                        }

                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: 180

                            gradient: Gradient {
                                GradientStop { position: 0; color: "#00000000" }
                                GradientStop { position: 0.5; color: "#aa06060b" }
                                GradientStop { position: 1; color: "#f206060b" }
                            }
                        }

                        ColumnLayout {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 22
                            spacing: 4

                            Text {
                                Layout.fillWidth: true
                                text: page.info.deLabel || ""
                                color: "#c9c9dd"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.8
                            }

                            Text {
                                Layout.fillWidth: true
                                text: page.info.title || "Copia"
                                color: "#ffffff"
                                font.pixelSize: 26
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                text: (page.info.created || "") + "  ·  " + (page.info.sizeText || "")
                                color: "#b9b9cc"
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                text: {
                                    var list = page.info.screens || []
                                    var screen = list[page.heroIndex] || {}
                                    return screen.summary || ""
                                }
                                color: "#9a9ab0"
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: 320
                        Layout.preferredHeight: 360
                        radius: Theme.radius
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.border

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 0

                            Text {
                                text: "DETALLES"
                                color: Theme.textFaint
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.8
                                Layout.bottomMargin: 12
                            }

                            Repeater {
                                model: page.metaRows

                                Item {
                                    Layout.fillWidth: true
                                    implicitHeight: 30

                                    Text {
                                        anchors.left: parent.left
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.label
                                        color: Theme.textDim
                                        font.pixelSize: 12
                                    }

                                    Text {
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 190
                                        text: modelData.value
                                        color: Theme.text
                                        font.pixelSize: 12
                                        horizontalAlignment: Text.AlignRight
                                        elide: Text.ElideRight
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true }

                            Text {
                                visible: (page.info.notes || "").length > 0
                                Layout.fillWidth: true
                                Layout.bottomMargin: 12
                                text: page.info.notes || ""
                                color: Theme.textDim
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                                maximumLineCount: 3
                                elide: Text.ElideRight
                            }

                            Text {
                                visible: (page.info.palette || []).length > 0
                                text: "PALETA"
                                color: Theme.textFaint
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.8
                                Layout.bottomMargin: 8
                            }

                            Row {
                                spacing: 8

                                Repeater {
                                    model: page.info.palette || []

                                    Column {
                                        spacing: 5

                                        Rectangle {
                                            width: 44
                                            height: 34
                                            radius: 9
                                            color: modelData
                                            border.width: 1
                                            border.color: "#14ffffff"
                                        }

                                        Text {
                                            width: 44
                                            text: modelData
                                            color: Theme.textFaint
                                            font.pixelSize: 8
                                            horizontalAlignment: Text.AlignHCenter
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ------------------------------------------------------ widgets
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    spacing: 12
                    visible: (page.info.containers || []).length > 0

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "Widgets y paneles"
                            color: Theme.text
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            text: (page.info.widgetCount || 0)
                                  + ((page.info.widgetCount || 0) === 1 ? " widget" : " widgets")
                            color: Theme.textFaint
                            font.pixelSize: 11
                        }
                    }

                    Repeater {
                        model: page.info.containers || []

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: containerCol.implicitHeight + 30
                            radius: Theme.radius
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.border

                            ColumnLayout {
                                id: containerCol
                                anchors.fill: parent
                                anchors.margins: 15
                                spacing: 10

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    Text {
                                        text: modelData.name
                                        color: Theme.text
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.items.length > 0 ? (modelData.summary || "") : ""
                                        color: Theme.textDim
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        visible: modelData.items.length > 0
                                        text: modelData.items.length
                                        color: Theme.accent
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                    }
                                }

                                // ajustes de un dock (GNOME): no hay franja que recortar
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 7
                                    visible: (modelData.settings || []).length > 0

                                    Repeater {
                                        model: modelData.settings || []

                                        Rectangle {
                                            height: 26
                                            width: settingText.implicitWidth + 22
                                            radius: 13
                                            color: Theme.surfaceAlt
                                            border.width: 1
                                            border.color: Theme.border

                                            Text {
                                                id: settingText
                                                anchors.centerIn: parent
                                                text: modelData.label + ": " + modelData.value
                                                color: Theme.text
                                                font.pixelSize: 11
                                            }
                                        }
                                    }
                                }

                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 7

                                    Repeater {
                                        model: modelData.items

                                        Rectangle {
                                            height: 26
                                            width: chip.implicitWidth + 26
                                            radius: 13
                                            color: modelData.installed ? Theme.surfaceAlt : "#12fbbf24"
                                            border.width: 1
                                            border.color: modelData.installed ? Theme.border : "#33fbbf24"

                                            Row {
                                                id: chip
                                                anchors.centerIn: parent
                                                spacing: 7
                                                height: 15

                                                Rectangle {
                                                    y: 4
                                                    width: 6
                                                    height: 6
                                                    radius: 3
                                                    color: modelData.installed ? Theme.ok : Theme.warn
                                                }

                                                Text {
                                                    text: modelData.name
                                                    color: modelData.installed ? Theme.text : Theme.warn
                                                    font.pixelSize: 11
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ----------------------------------------------------- muestra
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    spacing: 10
                    visible: (page.info.sampleCursor || "").length > 0
                             || (page.info.sampleIcons || []).length > 0

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: "Muestra del tema"
                            color: Theme.text
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            Layout.maximumWidth: 420
                            text: "Iconos: " + page.themeName("icons") + "  ·  Cursor: " + page.themeName("cursor")
                            color: Theme.textFaint
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                    }

                    Row {
                        spacing: 10

                        Rectangle {
                            visible: (page.info.sampleCursor || "").length > 0
                            width: 88
                            height: 88
                            radius: 16
                            color: Theme.surfaceAlt
                            border.width: 1
                            border.color: Theme.border

                            Image {
                                anchors.fill: parent
                                anchors.margins: 12
                                source: page.info.sampleCursor || ""
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                            }
                        }

                        Repeater {
                            model: page.info.sampleIcons || []

                            Rectangle {
                                width: 70
                                height: 70
                                radius: 14
                                color: Theme.surfaceAlt
                                border.width: 1
                                border.color: Theme.border

                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 9
                                    source: modelData
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                }
                            }
                        }
                    }

                    // barras de tareas recortadas de la captura
                    Repeater {
                        model: page.info.panels || []

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 8
                            spacing: 6

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    text: modelData.name || "Barra"
                                    color: Theme.text
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.summary || ""
                                    color: Theme.textFaint
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                            }

                            Rectangle {
                                id: panelShot
                                readonly property bool vertical: (modelData.height || 0) > (modelData.width || 0)

                                Layout.fillWidth: !panelShot.vertical
                                Layout.preferredWidth: panelShot.vertical
                                    ? Math.max(18, Math.round(220 * (modelData.width || 72) / (modelData.height || 1080)) + 6)
                                    : -1
                                Layout.preferredHeight: panelShot.vertical ? 220 : 58
                                Layout.alignment: panelShot.vertical ? Qt.AlignLeft : Qt.AlignHCenter
                                radius: 10
                                color: Theme.surfaceAlt
                                border.width: 1
                                border.color: Theme.border
                                clip: true

                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 2
                                    source: modelData.url || ""
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                }
                            }
                        }
                    }
                }

                Text {
                    Layout.topMargin: 6
                    text: "Contenido"
                    color: Theme.text
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }

                Flow {
                    id: catFlow
                    Layout.fillWidth: true
                    spacing: 14

                    Repeater {
                        model: page.info.categories || []

                        Rectangle {
                            width: Math.floor((catFlow.width - 28) / 3)
                            height: 138
                            radius: Theme.radius
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.border

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 4

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.label
                                        color: Theme.text
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }

                                    Rectangle {
                                        width: 24
                                        height: 20
                                        radius: 10
                                        color: Theme.accentSoft

                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.count
                                            color: Theme.accent
                                            font.pixelSize: 10
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.sizeText
                                    color: Theme.textFaint
                                    font.pixelSize: 10
                                }

                                Item { Layout.fillHeight: true }

                                Text {
                                    Layout.fillWidth: true
                                    text: page.itemPreview(modelData.items)
                                    color: Theme.textDim
                                    font.pixelSize: 11
                                    lineHeight: 1.25
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 3
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    Layout.bottomMargin: 8
                    visible: (page.info.skipped || []).length > 0
                    implicitHeight: skippedCol.implicitHeight + 30
                    radius: Theme.radius
                    color: "#0dfbbf24"
                    border.width: 1
                    border.color: "#33fbbf24"

                    ColumnLayout {
                        id: skippedCol
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 4

                        Text {
                            text: "Elementos omitidos durante el respaldo"
                            color: Theme.warn
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: {
                                var list = page.info.skipped || []
                                var out = []
                                for (var i = 0; i < list.length; i++)
                                    out.push("· " + list[i].path + " — " + list[i].reason)
                                return out.join("\n")
                            }
                            color: Theme.textDim
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        }
    }

    Shortcut {
        sequence: "Esc"
        onActivated: page.back()
    }

    Popup {
        id: deleteDialog

        modal: true
        focus: true
        padding: 0
        width: 430
        anchors.centerIn: parent
        closePolicy: Popup.CloseOnEscape

        Overlay.modal: Rectangle {
            color: "#9905050a"
        }

        background: Rectangle {
            color: Theme.surface
            radius: Theme.radius
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 0

            ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: 24
                spacing: 6

                Text {
                    text: "Eliminar copia"
                    color: Theme.text
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    text: "Se borrarán los archivos de «" + (page.info.title || "") + "» de forma permanente."
                    color: Theme.textDim
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.bottomMargin: 22
                spacing: 10

                Item { Layout.fillWidth: true }

                AppButton {
                    text: "Cancelar"
                    variant: "ghost"
                    onClicked: deleteDialog.close()
                }

                AppButton {
                    text: "Eliminar"
                    variant: "danger"
                    onClicked: {
                        backend.deleteBackup(page.backupId)
                        deleteDialog.close()
                        page.back()
                    }
                }
            }
        }
    }
}
