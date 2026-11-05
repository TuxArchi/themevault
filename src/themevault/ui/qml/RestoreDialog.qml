import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: dlg

    modal: true
    focus: true
    padding: 0
    width: 620
    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape

    property string backupId: ""
    property var plan: null
    property var result: null
    property var selected: ({})
    property int selectedCount: 0
    property bool safety: true
    property bool applying: false
    property string errorText: ""
    property bool perScreen: false
    property var screenMapping: ({})

    signal finished()
    signal storeRequested(string query)
    signal notify(string message, bool error)

    function openFor(id) {
        backupId = id
        plan = null
        result = null
        selected = ({})
        selectedCount = 0
        applying = false
        safety = true
        safetySwitch.checked = true
        perScreen = false
        screenMapping = ({})
        errorText = ""
        open()
        backend.requestPlan(id)
    }

    function setPlan(p) {
        plan = p
        var sel = ({})
        var count = 0
        var cats = p.categories || []
        for (var i = 0; i < cats.length; i++) {
            sel[cats[i].name] = cats[i].ok > 0
            if (cats[i].ok > 0)
                count += cats[i].ok
        }
        selected = sel
        selectedCount = count

        var map = ({})
        var targets = p.targetScreens || []
        var screens = p.screens || []
        for (var i = 0; i < screens.length; i++) {
            var source = screens[i].index
            var chosenTarget = -1
            for (var j = 0; j < targets.length; j++) {
                if (targets[j].index === source) {
                    chosenTarget = source
                    break
                }
            }
            if (chosenTarget < 0 && targets.length > 0)
                chosenTarget = targets[0].index
            map[source] = chosenTarget
        }
        screenMapping = map
    }

    function setTarget(source, target) {
        var map = ({})
        for (var key in dlg.screenMapping)
            map[key] = dlg.screenMapping[key]
        map[source] = target
        dlg.screenMapping = map
    }

    function screenRows() {
        var rows = []
        var screens = (dlg.plan && dlg.plan.screens) || []
        var targets = (dlg.plan && dlg.plan.targetScreens) || []
        for (var i = 0; i < screens.length; i++) {
            var source = screens[i]
            var cells = []
            for (var j = 0; j < targets.length; j++) {
                cells.push({
                    source: source.index,
                    target: targets[j].index,
                    label: targets[j].name,
                    selected: dlg.screenMapping[source.index] === targets[j].index
                })
            }
            cells.push({
                source: source.index,
                target: -1,
                label: "No",
                selected: dlg.screenMapping[source.index] === -1
            })

            var warning = ""
            var picked = dlg.screenMapping[source.index]
            for (var k = 0; k < targets.length; k++) {
                if (targets[k].index !== picked)
                    continue
                if (source.width && targets[k].width
                        && (source.width !== targets[k].width || source.height !== targets[k].height)) {
                    warning = "⚠ " + targets[k].width + "×" + targets[k].height
                              + " (origen " + source.width + "×" + source.height
                              + "): las posiciones de iconos se reacomodan"
                }
            }

            rows.push({
                label: (source.name || "") + "  ·  " + (source.summary || ""),
                cells: cells,
                warning: warning
            })
        }
        return rows
    }

    function availableWidgetIds() {
        var out = []
        var list = (dlg.plan && dlg.plan.missingWidgets) || []
        for (var i = 0; i < list.length; i++)
            if (list[i].inBackup)
                out.push(list[i].id)
        return out
    }

    function selectedScreens() {
        var count = 0
        for (var key in dlg.screenMapping)
            if (dlg.screenMapping[key] >= 0)
                count++
        return count
    }

    function toggle(name) {
        var sel = selected
        sel[name] = !sel[name]
        selected = sel
        var count = 0
        var cats = (plan && plan.categories) || []
        for (var i = 0; i < cats.length; i++)
            if (sel[cats[i].name] && cats[i].ok > 0)
                count += cats[i].ok
        selectedCount = count
    }

    function chosen() {
        var out = []
        var cats = (plan && plan.categories) || []
        for (var i = 0; i < cats.length; i++)
            if (selected[cats[i].name] && cats[i].ok > 0)
                out.push(cats[i].name)
        return out
    }

    function apply() {
        applying = true
        if (dlg.perScreen) {
            var list = []
            for (var key in dlg.screenMapping) {
                var target = dlg.screenMapping[key]
                if (target >= 0)
                    list.push({ source: parseInt(key), target: target })
            }
            backend.applyScreenRestore(backupId, list, safety)
        } else {
            backend.applyRestore(backupId, chosen(), safety)
        }
    }

    Connections {
        target: backend

        function onPlanReady(p) {
            if (dlg.visible && p.id === dlg.backupId)
                dlg.setPlan(p)
        }

        function onRestoreFinished(r) {
            if (dlg.visible && r.id === dlg.backupId) {
                dlg.applying = false
                dlg.result = r
                dlg.finished()
            }
        }

        function onWidgetsInstalled(r) {
            if (!dlg.opened)
                return
            var done = (r.installed || []).length
            if (done > 0) {
                dlg.notify(done + (done === 1 ? " widget instalado" : " widgets instalados"), false)
                dlg.plan = null
                backend.requestPlan(dlg.backupId)
            }
            var failed = r.failed || []
            if (failed.length > 0)
                dlg.notify(failed[0].message || "no se pudo instalar el widget", true)
        }

        function onScreenRestoreFinished(r) {
            if (dlg.opened && r.id === dlg.backupId) {
                dlg.applying = false
                dlg.result = {
                    applied: r.screens || 0,
                    failures: [],
                    safety: r.safety || "",
                    safetyError: "",
                    perScreen: true
                }
                dlg.finished()
            }
        }

        function onFailed(action, message) {
            if (!dlg.visible)
                return
            if (action === "plan") {
                dlg.errorText = message
            } else if (action === "restore") {
                dlg.applying = false
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
                text: dlg.result ? "Restauración completada" : "Restaurar copia"
                color: Theme.text
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }

            Text {
                text: dlg.plan
                      ? (dlg.plan.title + "  ·  " + dlg.plan.deLabel)
                      : "Preparando el plan de restauración…"
                color: Theme.textDim
                font.pixelSize: 12
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        Item { Layout.preferredHeight: 18 }

        // ---------------------------------------------------------- cargando
        RowLayout {
            visible: dlg.plan === null && dlg.errorText === ""
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 26
            spacing: 10

            Rectangle {
                width: 6
                height: 6
                radius: 3
                color: Theme.accent

                SequentialAnimation on opacity {
                    running: parent.visible
                    loops: Animation.Infinite
                    NumberAnimation { to: 1; duration: 400 }
                    NumberAnimation { to: 0.2; duration: 400 }
                }
            }

            Text {
                text: "Analizando qué se puede aplicar en este sistema…"
                color: Theme.textDim
                font.pixelSize: 12
            }
        }

        // ------------------------------------------------------------- error
        ColumnLayout {
            visible: dlg.errorText !== ""
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 26
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: errText.implicitHeight + 24
                radius: Theme.radiusSmall
                color: "#1af87171"
                border.width: 1
                border.color: "#44f87171"

                Text {
                    id: errText
                    anchors.fill: parent
                    anchors.margins: 12
                    text: dlg.errorText
                    color: Theme.danger
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }
        }

        // ----------------------------------------------------- plan / opciones
        ColumnLayout {
            visible: dlg.plan !== null && dlg.result === null
            spacing: 0

            Rectangle {
                visible: dlg.plan !== null && (dlg.plan.missing || []).length > 0
                Layout.fillWidth: true
                Layout.leftMargin: 26
                Layout.rightMargin: 26
                Layout.bottomMargin: 14
                implicitHeight: missingCol.implicitHeight + 24
                radius: Theme.radiusSmall
                color: "#12fbbf24"
                border.width: 1
                border.color: "#33fbbf24"

                ColumnLayout {
                    id: missingCol
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 3

                    Text {
                        text: "Temas o iconos que este sistema no tiene"
                        color: Theme.warn
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }

                    Text {
                        Layout.fillWidth: true
                        text: {
                            if (!dlg.plan)
                                return ""
                            var list = dlg.plan.missing || []
                            var shown = list.slice(0, 6).join(", ")
                            if (list.length > 6)
                                shown += " y " + (list.length - 6) + " más"
                            return shown + ". Se restauran los archivos, pero el tema activo podría no estar disponible."
                        }
                        color: Theme.textDim
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                }
            }

            Rectangle {
                visible: dlg.plan !== null && (dlg.plan.missingWidgets || []).length > 0
                Layout.fillWidth: true
                Layout.leftMargin: 26
                Layout.rightMargin: 26
                Layout.bottomMargin: 14
                implicitHeight: missingWidgetsCol.implicitHeight + 24
                radius: Theme.radiusSmall
                color: "#12fbbf24"
                border.width: 1
                border.color: "#33fbbf24"

                ColumnLayout {
                    id: missingWidgetsCol
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 6

                    Text {
                        text: "Widgets que no están instalados"
                        color: Theme.warn
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                    }

                    Repeater {
                        model: dlg.plan ? dlg.plan.missingWidgets : []

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                Layout.fillWidth: true
                                text: modelData.name
                                color: Theme.textDim
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }

                            AppButton {
                                visible: modelData.inBackup
                                text: "Instalar"
                                variant: "subtle"
                                small: true
                                onClicked: backend.installBackupWidgets(dlg.backupId, [modelData.id])
                            }

                            AppButton {
                                text: modelData.inBackup ? "Tienda" : "Buscar en la tienda"
                                variant: "ghost"
                                small: true
                                onClicked: dlg.storeRequested(modelData.name)
                            }
                        }
                    }

                    AppButton {
                        visible: dlg.availableWidgetIds().length > 0
                        Layout.topMargin: 2
                        text: "Instalar desde la copia (" + dlg.availableWidgetIds().length + ")"
                        variant: "subtle"
                        small: true
                        onClicked: backend.installBackupWidgets(dlg.backupId, dlg.availableWidgetIds())
                    }
                }
            }

            Text {
                Layout.leftMargin: 26
                Layout.topMargin: 2
                Layout.bottomMargin: 8
                text: "QUÉ RESTAURAR"
                color: Theme.textFaint
                font.pixelSize: 10
                font.weight: Font.DemiBold
                font.letterSpacing: 0.8
            }

            Repeater {
                model: dlg.plan ? dlg.plan.categories : []

                Rectangle {
                    id: catRow
                    Layout.fillWidth: true
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    implicitHeight: 52
                    radius: Theme.radiusSmall
                    opacity: dlg.perScreen ? 0.35 : 1
                    color: rowMouse.containsMouse ? Theme.surfaceHover : "transparent"

                    property bool usable: modelData.ok > 0
                    property bool picked: dlg.selected[modelData.name] === true

                    Rectangle {
                        id: box
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        width: 20
                        height: 20
                        radius: 6
                        color: catRow.picked ? Theme.accent : "transparent"
                        border.width: 1.5
                        border.color: catRow.picked ? Theme.accent : Theme.borderStrong
                        opacity: catRow.usable ? 1 : 0.35

                        Text {
                            anchors.centerIn: parent
                            visible: catRow.picked
                            text: "✓"
                            color: "#ffffff"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                        }
                    }

                    ColumnLayout {
                        anchors.left: box.right
                        anchors.leftMargin: 12
                        anchors.right: badge.left
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 1

                        Text {
                            Layout.fillWidth: true
                            text: modelData.label
                            color: catRow.usable ? Theme.text : Theme.textDim
                            font.pixelSize: 13
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            text: modelData.ok + (modelData.ok === 1 ? " elemento aplicable" : " elementos aplicables")
                            color: Theme.textFaint
                            font.pixelSize: 10
                        }
                    }

                    Rectangle {
                        id: badge
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        visible: modelData.blocked > 0
                        width: blockedText.implicitWidth + 14
                        height: 20
                        radius: 10
                        color: "#18fbbf24"

                        Text {
                            id: blockedText
                            anchors.centerIn: parent
                            text: modelData.blocked + " sin aplicar"
                            color: Theme.warn
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                        }
                    }

                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: catRow.usable ? Qt.PointingHandCursor : Qt.ArrowCursor
                        enabled: !dlg.perScreen
                        onClicked: {
                            if (catRow.usable)
                                dlg.toggle(modelData.name)
                        }
                    }
                }
            }

            Rectangle {
                visible: dlg.plan !== null && dlg.plan.kde
                         && (dlg.plan.screens || []).length > 1
                         && (dlg.plan.targetScreens || []).length > 0
                Layout.fillWidth: true
                Layout.leftMargin: 26
                Layout.rightMargin: 26
                Layout.topMargin: 14
                implicitHeight: screenCol.implicitHeight + 26
                radius: Theme.radiusSmall
                color: Theme.surfaceAlt

                ColumnLayout {
                    id: screenCol
                    anchors.fill: parent
                    anchors.margins: 13
                    spacing: 9

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        ColumnLayout {
                            spacing: 1

                            Text {
                                text: "Restaurar por pantalla"
                                color: Theme.text
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }

                            Text {
                                text: "Elegí qué pantalla de la copia va en cuál de tu equipo."
                                color: Theme.textFaint
                                font.pixelSize: 10
                            }
                        }

                        Item { Layout.fillWidth: true }

                        AppSwitch {
                            checked: dlg.perScreen
                            onToggled: function(value) { dlg.perScreen = value }
                        }
                    }

                    Repeater {
                        model: dlg.perScreen ? dlg.screenRows() : []

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5

                            Text {
                                Layout.fillWidth: true
                                text: modelData.label
                                color: Theme.textDim
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }

                            Flow {
                                Layout.fillWidth: true
                                spacing: 6

                                Repeater {
                                    model: modelData.cells

                                    Rectangle {
                                        height: 26
                                        width: cellText.implicitWidth + 20
                                        radius: 13
                                        color: modelData.selected ? Theme.accent : Theme.surface
                                        border.width: 1
                                        border.color: modelData.selected ? Theme.accent : Theme.border

                                        Text {
                                            id: cellText
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            color: modelData.selected ? "#ffffff" : Theme.textDim
                                            font.pixelSize: 10
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: dlg.setTarget(modelData.source, modelData.target)
                                        }
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: (modelData.warning || "").length > 0
                                text: modelData.warning || ""
                                color: Theme.warn
                                font.pixelSize: 9
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    Text {
                        visible: dlg.perScreen
                        Layout.fillWidth: true
                        text: "Se reiniciará plasmashell (~2 s) y solo se aplican las pantallas elegidas; las categorías de arriba no se usan. Colores e iconos son globales: aplicalos aparte si querés el aspecto completo. Tus ventanas no se cierran."
                        color: Theme.warn
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 26
                Layout.rightMargin: 26
                Layout.topMargin: 14
                implicitHeight: 52
                radius: Theme.radiusSmall
                color: Theme.surfaceAlt

                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2

                    Text {
                        text: "Crear un punto de retorno antes de aplicar"
                        color: Theme.text
                        font.pixelSize: 12
                    }

                    Text {
                        text: "Guarda el estado actual para poder deshacer la restauración."
                        color: Theme.textFaint
                        font.pixelSize: 10
                    }
                }

                AppSwitch {
                    id: safetySwitch
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    checked: dlg.safety
                    onToggled: function(value) { dlg.safety = value }
                }
            }
        }

        // ----------------------------------------------------------- resultado
        ColumnLayout {
            visible: dlg.result !== null
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 8
            }

            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 62
                height: 62
                radius: 31
                color: (dlg.result && dlg.result.failures.length === 0) ? "#1f34d399" : "#1ffbbf24"
                border.width: 1
                border.color: (dlg.result && dlg.result.failures.length === 0) ? "#4434d399" : "#44fbbf24"

                Text {
                    anchors.centerIn: parent
                    text: (dlg.result && dlg.result.failures.length === 0) ? "✓" : "!"
                    color: (dlg.result && dlg.result.failures.length === 0) ? Theme.ok : Theme.warn
                    font.pixelSize: 28
                    font.weight: Font.Bold
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 14
                text: {
                    if (!dlg.result)
                        return ""
                    var n = dlg.result.applied
                    if (dlg.result.perScreen)
                        return n + (n === 1 ? " pantalla restaurada" : " pantallas restauradas")
                    return n + (n === 1 ? " elemento restaurado" : " elementos restaurados")
                }
                color: Theme.text
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 4
                visible: dlg.result && dlg.result.safety.length > 0
                text: dlg.result ? ("Punto de retorno: " + dlg.result.safety) : ""
                color: Theme.textFaint
                font.pixelSize: 11
            }

            Text {
                Layout.leftMargin: 26
                Layout.rightMargin: 26
                Layout.topMargin: 8
                Layout.fillWidth: true
                visible: dlg.result && dlg.result.safetyError.length > 0
                text: dlg.result ? ("No se pudo crear el punto de retorno: " + dlg.result.safetyError) : ""
                color: Theme.warn
                font.pixelSize: 11
                wrapMode: Text.Wrap
            }

            Repeater {
                model: (dlg.result && dlg.result.failures) ? dlg.result.failures : []

                Text {
                    Layout.leftMargin: 26
                    Layout.rightMargin: 26
                    Layout.topMargin: 6
                    Layout.fillWidth: true
                    text: "· " + modelData[0] + ": " + modelData[1]
                    color: Theme.danger
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                }
            }

            Text {
                Layout.leftMargin: 26
                Layout.rightMargin: 26
                Layout.topMargin: 12
                Layout.fillWidth: true
                visible: dlg.result && !dlg.result.perScreen && dlg.result.applied > 0
                         && dlg.plan && ["kde", "gnome", "hyprland", "niri", "sway",
                                         "river", "wayfire", "labwc"].indexOf(dlg.plan.de) >= 0
                text: {
                    if (!dlg.plan)
                        return ""
                    if (dlg.plan.de === "hyprland")
                        return "Ejecutá `hyprctl reload` o reiniciá la sesión para aplicar atajos y reglas."
                    if (dlg.plan.de === "niri")
                        return "Ejecutá `niri validate`; niri recarga la configuración automáticamente."
                    if (dlg.plan.de === "sway")
                        return "Ejecutá `swaymsg reload` para aplicar los cambios."
                    if (dlg.plan.de === "labwc")
                        return "Ejecutá `labwc --reconfigure` o reiniciá la sesión."
                    return "Reiniciá la sesión para ver todos los cambios."
                }
                color: Theme.textDim
                font.pixelSize: 12
            }
        }

        Item { Layout.preferredHeight: 20 }

        // -------------------------------------------------------------- footer
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.rightMargin: 26
            Layout.bottomMargin: 24
            spacing: 10

            Text {
                visible: dlg.applying
                text: "Aplicando cambios…"
                color: Theme.textDim
                font.pixelSize: 12
            }

            Item { Layout.fillWidth: true }

            AppButton {
                visible: dlg.result === null
                text: "Cancelar"
                variant: "ghost"
                enabled: !dlg.applying
                onClicked: dlg.close()
            }

            AppButton {
                visible: dlg.result === null
                text: dlg.perScreen
                      ? ("Restaurar " + dlg.selectedScreens() + (dlg.selectedScreens() === 1 ? " pantalla" : " pantallas"))
                      : ("Restaurar " + dlg.selectedCount + (dlg.selectedCount === 1 ? " elemento" : " elementos"))
                variant: "primary"
                enabled: (dlg.perScreen ? dlg.selectedScreens() > 0 : dlg.selectedCount > 0) && !dlg.applying
                onClicked: dlg.apply()
            }

            AppButton {
                visible: dlg.result !== null
                text: "Cerrar"
                variant: "primary"
                onClicked: dlg.close()
            }
        }
    }
}
