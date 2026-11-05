import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: dlg

    modal: true
    focus: true
    padding: 0
    width: 720
    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape

    property string backupId: ""
    property var preview: ({})
    property string license: "CC-BY-SA-4.0"
    property bool includeCover: false
    property bool includeWallpaper: true
    property bool includePlugins: true
    property bool includeKeybinds: true
    property bool includeLayout: true
    property bool exporting: false
    property string errorText: ""
    property string exportedTo: ""

    signal notify(string message, bool error)

    readonly property var licenses: ["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "MIT", "GPL-3.0-or-later"]
    readonly property var shareOptions: [
        { prop: "includeWallpaper", title: "Incluir fondo", hint: "Imagen o video, sin audio ni metadatos." },
        { prop: "includePlugins", title: "Incluir plugins y assets", hint: "Código de terceros con hash y confirmación." },
        { prop: "includeKeybinds", title: "Incluir atajos seguros", hint: "Solo combinaciones sin rutas, URLs ni secretos." },
        { prop: "includeLayout", title: "Incluir layout", hint: "Paneles, posiciones y widgets aplicados." }
    ]
    readonly property bool authorMismatch: backend.githubUser.length > 0
                                           && authorInput.text.length > 0
                                           && authorInput.text.trim().toLowerCase() !== backend.githubUser.toLowerCase()

    function openFor(id, notes, suggestedName, suggestedAuthor) {
        backupId = id
        preview = ({})
        license = "CC-BY-SA-4.0"
        includeCover = false
        includeWallpaper = true
        includePlugins = true
        includeKeybinds = true
        includeLayout = true
        exporting = false
        errorText = ""
        exportedTo = ""
        nameInput.text = suggestedName || ""
        authorInput.text = suggestedAuthor || backend.githubUser || ""
        descInput.text = notes || ""
        destination.text = backend.exportDir
        backend.detectGithubUser()
        open()
        nameInput.forceActiveFocus()
        refresh()
    }

    function refresh() {
        backend.profilePreview(backupId, nameInput.text, authorInput.text,
                               license, descInput.text, includeCover,
                               includeWallpaper, includePlugins,
                               includeKeybinds, includeLayout)
    }

    function canExport() {
        return nameInput.text.trim().length > 0
               && authorInput.text.trim().length > 0
               && (preview.problems || []).length === 0
               && !exporting
    }

    function exportNow() {
        if (!canExport())
            return
        exporting = true
        errorText = ""
        backend.profileExport(backupId, nameInput.text, authorInput.text,
                              license, descInput.text, includeCover,
                              includeWallpaper, includePlugins,
                              includeKeybinds, includeLayout, destination.text)
    }

    function requirementChips(requires) {
        var names = { plasma_style: "Estilo", color_scheme: "Esquema", icons: "Iconos", cursor: "Cursor", gtk: "GTK" }
        var out = []
        if (!requires)
            return out
        for (var key in names) {
            if (requires[key])
                out.push(names[key] + ": " + requires[key])
        }
        return out
    }

    function settingLine(s) {
        if (!s)
            return ""
        if (s.backend === "ini")
            return (s.file || "") + " · " + (s.group || "") + "/" + (s.key || "") + " = " + (s.value || "")
        if (s.backend === "dconf")
            return (s.path || "") + (s.key || "") + " = " + (s.value || "")
        return (s.channel || "") + " " + (s.prop || "") + " = " + (s.value || "")
    }

    function desktopLabel(value) {
        var names = { kde: "KDE Plasma", gnome: "GNOME", xfce: "Xfce", cinnamon: "Cinnamon",
                      mate: "MATE", budgie: "Budgie", lxqt: "LXQt", i3: "i3",
                      openbox: "Openbox", cosmic: "COSMIC", hyprland: "Hyprland",
                      niri: "niri", sway: "Sway", river: "River", wayfire: "Wayfire",
                      labwc: "labwc", other: "Otro" }
        return names[value] || value || ""
    }

    Timer {
        id: debounce
        interval: 260
        onTriggered: dlg.refresh()
    }

    Connections {
        target: backend

        function onProfilePreviewed(info) {
            if (!dlg.visible || dlg.exporting)
                return
            dlg.preview = info
        }

        function onProfileExported(info) {
            dlg.exporting = false
            dlg.exportedTo = info.path || ""
            dlg.notify("Perfil exportado", false)
        }

        function onGithubUserChanged() {
            if (dlg.visible && authorInput.text.length === 0)
                authorInput.text = backend.githubUser
        }

        function onFailed(action, message) {
            if (action === "profile_preview" || action === "profile_export") {
                dlg.exporting = false
                dlg.errorText = message
            }
        }
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
            spacing: 5

            Text {
                text: dlg.exportedTo.length > 0 ? "Perfil listo para compartir" : "Compartir perfil"
                color: Theme.text
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                text: dlg.exportedTo.length > 0
                      ? "Revisá el archivo y subilo como pull request al repositorio de perfiles."
                      : "Se comparte la configuración del aspecto, no tus archivos. Revisá la lista antes de exportar."
                color: Theme.textDim
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(300, Math.min(610, (dlg.parent ? dlg.parent.height : 900) - 200))

            // ------------------------------------------------------------ formulario
            ScrollView {
                id: formScroll
                anchors.fill: parent
                anchors.topMargin: 16
                visible: dlg.exportedTo.length === 0
                clip: true
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ScrollBar.vertical: ScrollBar {
                    id: formBar
                    policy: ScrollBar.AsNeeded
                    contentItem: Rectangle {
                        implicitWidth: 6
                        radius: 3
                        color: formBar.pressed ? Theme.textDim : Theme.borderStrong
                        opacity: formBar.active ? 1 : 0
                    }
                }

                ColumnLayout {
                    width: formScroll.availableWidth
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        spacing: 10

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5

                            Text {
                                text: "NOMBRE"
                                color: Theme.textFaint
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.8
                            }

                            TextField {
                                id: nameInput
                                Layout.fillWidth: true
                                placeholderText: "Ej. Catppuccin Mocha"
                                placeholderTextColor: Theme.textFaint
                                color: Theme.text
                                font.pixelSize: 13
                                selectByMouse: true
                                onTextChanged: debounce.restart()

                                background: Rectangle {
                                    implicitHeight: 38
                                    radius: Theme.radiusInput
                                    color: Theme.surfaceAlt
                                    border.width: 1
                                    border.color: nameInput.activeFocus ? Theme.accentLine : Theme.border
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.preferredWidth: 210
                            spacing: 5

                            Text {
                                text: "AUTOR (@GITHUB)"
                                color: Theme.textFaint
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.8
                            }

                            TextField {
                                id: authorInput
                                Layout.fillWidth: true
                                placeholderText: "tu-usuario"
                                placeholderTextColor: Theme.textFaint
                                color: Theme.text
                                font.pixelSize: 13
                                selectByMouse: true
                                onTextChanged: debounce.restart()
                                onAccepted: dlg.exportNow()

                                background: Rectangle {
                                    implicitHeight: 38
                                    radius: Theme.radiusInput
                                    color: Theme.surfaceAlt
                                    border.width: 1
                                    border.color: authorInput.activeFocus ? Theme.accentLine : Theme.border
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: backend.githubUser.length > 0
                                text: dlg.authorMismatch
                                      ? "Tu sesión de gh es @" + backend.githubUser + "; el PR como @"
                                        + authorInput.text.trim() + " va a fallar en CI."
                                      : "Coincide con tu sesión de gh: @" + backend.githubUser
                                color: dlg.authorMismatch ? Theme.warn : Theme.ok
                                font.pixelSize: 9
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        spacing: 5

                        Text {
                            text: "DESCRIPCIÓN"
                            color: Theme.textFaint
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.8
                        }

                        TextField {
                            id: descInput
                            Layout.fillWidth: true
                            placeholderText: "Qué la hace distinta (opcional)"
                            placeholderTextColor: Theme.textFaint
                            color: Theme.text
                            font.pixelSize: 12
                            selectByMouse: true
                            onTextChanged: debounce.restart()

                            background: Rectangle {
                                implicitHeight: 36
                                radius: Theme.radiusInput
                                color: Theme.surfaceAlt
                                border.width: 1
                                border.color: descInput.activeFocus ? Theme.accentLine : Theme.border
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        spacing: 6

                        Text {
                            text: "LICENCIA"
                            color: Theme.textFaint
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.8
                        }

                        Flow {
                            Layout.fillWidth: true
                            spacing: 6

                            Repeater {
                                model: dlg.licenses

                                AppButton {
                                    text: modelData
                                    small: true
                                    variant: dlg.license === modelData ? "primary" : "ghost"
                                    onClicked: {
                                        dlg.license = modelData
                                        dlg.refresh()
                                    }
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        spacing: 6

                        Repeater {
                            model: dlg.shareOptions

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 52
                                radius: Theme.radiusSmall
                                color: Theme.surfaceAlt

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 14
                                    anchors.rightMargin: 14
                                    spacing: 12

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1

                                        Text {
                                            text: modelData.title
                                            color: Theme.text
                                            font.pixelSize: 12
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.hint
                                            color: Theme.textFaint
                                            font.pixelSize: 10
                                            elide: Text.ElideRight
                                        }
                                    }

                                    AppSwitch {
                                        checked: dlg[modelData.prop] === true
                                        onToggled: function(value) {
                                            dlg[modelData.prop] = value
                                            dlg.refresh()
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 62
                            radius: Theme.radiusSmall
                            color: Theme.surfaceAlt

                            Column {
                                anchors.left: parent.left
                                anchors.leftMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2

                                Text {
                                    text: "Incluir portada"
                                    color: Theme.text
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: "La portada se genera desde el fondo, no desde una captura de tus ventanas."
                                    color: Theme.textFaint
                                    font.pixelSize: 10
                                }
                            }

                            AppSwitch {
                                id: coverSwitch
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                enabled: dlg.includeWallpaper
                                checked: dlg.includeCover && dlg.includeWallpaper
                                onToggled: function(value) {
                                    dlg.includeCover = value
                                    dlg.refresh()
                                }
                            }
                        }
                    }

                    // ------------------------------------------------ vista previa
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        implicitHeight: previewCol.implicitHeight + 28
                        radius: Theme.radiusSmall
                        color: Theme.surfaceAlt
                        border.width: 1
                        border.color: Theme.border

                        ColumnLayout {
                            id: previewCol
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 9

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Rectangle {
                                    Layout.preferredWidth: 132
                                    Layout.preferredHeight: 74
                                    radius: 10
                                    clip: true
                                    color: (dlg.preview.palette || []).length > 0 ? dlg.preview.palette[0] : Theme.surface

                                    Image {
                                        anchors.fill: parent
                                        source: dlg.preview.cover || ""
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        visible: dlg.preview.hasCover === true
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        visible: dlg.preview.hasCover !== true
                                        text: "sin portada"
                                        color: Theme.textFaint
                                        font.pixelSize: 10
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3

                                    Text {
                                        Layout.fillWidth: true
                                        text: dlg.preview.name && dlg.preview.name.length > 0
                                              ? dlg.preview.name : "Tu perfil"
                                        color: Theme.text
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: "id: " + (dlg.preview.id || "—")
                                              + "  ·  " + dlg.desktopLabel(dlg.preview.desktop)
                                        color: Theme.textDim
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: (dlg.preview.settingsCount || 0) + " ajustes"
                                              + "  ·  " + (dlg.preview.hasWallpaper ? "fondo " + dlg.preview.wallpaperKind : "sin fondo")
                                              + "  ·  " + (dlg.preview.pluginCount || 0) + " plugins"
                                              + "  ·  " + (dlg.preview.keybindCount || 0) + " atajos"
                                              + "  ·  " + (dlg.preview.layoutCount || 0) + " paneles"
                                        color: Theme.textFaint
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }

                                    Row {
                                        spacing: 5
                                        visible: (dlg.preview.palette || []).length > 0

                                        Repeater {
                                            model: dlg.preview.palette || []

                                            Rectangle {
                                                width: 22
                                                height: 7
                                                radius: 3
                                                color: modelData
                                                border.width: 1
                                                border.color: "#22ffffff"
                                            }
                                        }
                                    }
                                }
                            }

                            Flow {
                                Layout.fillWidth: true
                                spacing: 6

                                Repeater {
                                    model: dlg.requirementChips(dlg.preview.requires || ({}))

                                    Rectangle {
                                        height: 22
                                        width: reqText.implicitWidth + 16
                                        radius: 11
                                        color: Theme.surface
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

                            Column {
                                Layout.fillWidth: true
                                spacing: 3

                                Text {
                                    text: "SE COMPARTE"
                                    color: Theme.textFaint
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.8
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "· Fondo: " + (dlg.preview.hasWallpaper ? dlg.preview.wallpaperKind : "no incluido")
                                    color: Theme.textDim
                                    font.pixelSize: 10
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "· Plugins: " + (dlg.preview.pluginCount || 0)
                                          + "  ·  Assets: " + (dlg.preview.assetCount || 0)
                                          + "  ·  Atajos seguros: " + (dlg.preview.keybindCount || 0)
                                          + "  ·  Paneles: " + (dlg.preview.layoutCount || 0)
                                    color: Theme.textDim
                                    font.pixelSize: 10
                                }
                            }

                            Column {
                                Layout.fillWidth: true
                                spacing: 3

                                Text {
                                    text: "NO SE COMPARTE"
                                    color: Theme.textFaint
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.8
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "· Captura del escritorio, historial, shells, configuración privada de widgets y atajos con rutas o secretos."
                                    color: Theme.textFaint
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                }
                            }

                            Column {
                                Layout.fillWidth: true
                                spacing: 3
                                visible: (dlg.preview.settings || []).length > 0

                                Text {
                                    text: "AJUSTES"
                                    color: Theme.textFaint
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.8
                                }

                                Repeater {
                                    model: (dlg.preview.settings || []).slice(0, 4)

                                    Text {
                                        width: previewCol.width - 28
                                        text: "· " + dlg.settingLine(modelData)
                                        color: Theme.textDim
                                        font.pixelSize: 10
                                        elide: Text.ElideMiddle
                                    }
                                }

                                Text {
                                    visible: (dlg.preview.settings || []).length > 4
                                    text: "+" + ((dlg.preview.settings || []).length - 4) + " ajustes más"
                                    color: Theme.textFaint
                                    font.pixelSize: 10
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: (dlg.preview.dropped || []).length > 0
                                text: (dlg.preview.dropped || []).join("  ·  ")
                                color: Theme.textFaint
                                font.pixelSize: 10
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }
                        }
                    }

                    // ------------------------------------------------ avisos
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        visible: dlg.preview.idTaken === true
                        implicitHeight: takenText.implicitHeight + 20
                        radius: Theme.radiusSmall
                        color: "#1afbbf24"
                        border.width: 1
                        border.color: "#33fbbf24"

                        Text {
                            id: takenText
                            anchors.fill: parent
                            anchors.margins: 10
                            text: "Ya hay un perfil con el id «" + (dlg.preview.id || "") + "» en la comunidad. "
                                  + (dlg.preview.suggestedId ? "Probá con «" + dlg.preview.suggestedId + "» o cambiá el nombre." : "Cambiá el nombre para no pisarlo.")
                            color: Theme.warn
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        visible: (dlg.preview.problems || []).length > 0
                                 && nameInput.text.length > 0 && authorInput.text.length > 0
                        text: (dlg.preview.problems || []).join("  ·  ")
                        color: Theme.danger
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        visible: dlg.errorText.length > 0
                        text: dlg.errorText
                        color: Theme.danger
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }

                    // ------------------------------------------------ destino
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        spacing: 5

                        Text {
                            text: "CARPETA DESTINO"
                            color: Theme.textFaint
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.8
                        }

                        TextField {
                            id: destination
                            Layout.fillWidth: true
                            text: backend.exportDir
                            placeholderText: backend.exportDir
                            placeholderTextColor: Theme.textFaint
                            color: Theme.text
                            font.pixelSize: 11
                            selectByMouse: true

                            background: Rectangle {
                                implicitHeight: 34
                                radius: Theme.radiusInput
                                color: Theme.surfaceAlt
                                border.width: 1
                                border.color: destination.activeFocus ? Theme.accentLine : Theme.border
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 26
                        Layout.bottomMargin: 16
                        text: "Se crea " + destination.text + "/" + (dlg.preview.id || "…")
                        color: Theme.textFaint
                        font.pixelSize: 10
                        elide: Text.ElideMiddle
                    }
                }
            }

            // ------------------------------------------------------------ listo
            ColumnLayout {
                anchors.centerIn: parent
                width: parent.width - 52
                visible: dlg.exportedTo.length > 0
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: doneCol.implicitHeight + 32
                    radius: Theme.radius
                    color: Theme.surfaceAlt
                    border.width: 1
                    border.color: Theme.border

                    ColumnLayout {
                        id: doneCol
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 6

                        Text {
                            text: "profile.json"
                                  + (dlg.preview.hasWallpaper ? " + fondo" : "")
                                  + (dlg.preview.pluginCount > 0 ? " + plugins" : "")
                                  + (dlg.preview.assetCount > 0 ? " + assets" : "")
                                  + (dlg.preview.hasCover ? " + portada" : "")
                            color: Theme.text
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: dlg.exportedTo
                            color: Theme.textDim
                            font.pixelSize: 11
                            wrapMode: Text.WrapAnywhere
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "Revisá el contenido y la portada. Después abrí un pull request en "
                                  + "github.com/TuxArchi/themevault-profiles con esa carpeta en profiles/."
                            color: Theme.textFaint
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: "Si tenés el paquete de Python: themevault publish-profile " + dlg.exportedTo
                    color: Theme.textFaint
                    font.pixelSize: 10
                    wrapMode: Text.WrapAnywhere
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    AppButton {
                        text: "Abrir carpeta"
                        variant: "subtle"
                        onClicked: backend.openExportFolder(dlg.exportedTo)
                    }

                    Item { Layout.fillWidth: true }

                    AppButton {
                        text: "Listo"
                        variant: "primary"
                        onClicked: dlg.close()
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 22
            spacing: 10
            visible: dlg.exportedTo.length === 0

            Text {
                Layout.fillWidth: true
                text: "Nunca se sube nada automáticamente."
                color: Theme.textFaint
                font.pixelSize: 10
            }

            AppButton {
                text: "Cancelar"
                variant: "ghost"
                onClicked: dlg.close()
            }

            AppButton {
                text: dlg.exporting ? "Exportando…" : "Exportar perfil"
                variant: "primary"
                enabled: dlg.canExport()
                onClicked: dlg.exportNow()
            }
        }
    }
}
