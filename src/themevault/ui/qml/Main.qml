import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window

    width: 1280
    height: 840
    minimumWidth: 1000
    minimumHeight: 640
    visible: true
    title: "ThemeVault"
    color: Theme.bg

    property int navIndex: 0
    property string toastText: ""
    property bool toastError: false
    property bool toastVisible: false

    function showToast(message, kind) {
        toastText = message
        toastError = (kind === "error")
        toastVisible = true
        toastTimer.restart()
    }

    Timer {
        id: toastTimer
        interval: 4200
        onTriggered: window.toastVisible = false
    }

    // Modo debug: --screenshot lo maneja app.py (captura toda la ventana,
    // incluyendo dialogos y overlays).

    Shortcut {
        sequence: "Ctrl+N"
        onActivated: newDialog.openDialog()
    }

    Shortcut {
        sequence: "Ctrl+R"
        onActivated: backend.refresh()
    }

    Item {
        id: rootItem
        anchors.fill: parent

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Sidebar {
            Layout.preferredWidth: 238
            Layout.fillHeight: true
            currentIndex: window.navIndex
            backupCount: backend.backupCount
            storageText: backend.storageSummary

            onNavigate: function(index) {
                if (index === 1) {
                    if (!(stack.currentItem && stack.currentItem.pageId === "system"))
                        stack.push(systemComponent)
                } else {
                    stack.pop(null)
                }
            }

            onNewBackup: newDialog.openDialog()
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            StackView {
                id: stack
                anchors.fill: parent
                initialItem: galleryComponent
                clip: true

                // Ojo: pushExit/popExit bajan la opacidad a 0 y el item queda
                // asi mientras esta en la pila. Por eso las transiciones de
                // entrada tienen que volver a subirla, o al volver se ve en
                // blanco.
                pushEnter: Transition {
                    ParallelAnimation {
                        NumberAnimation {
                            property: "x"
                            from: stack.width
                            to: 0
                            duration: 300
                            easing.type: Easing.OutCubic
                        }
                        NumberAnimation {
                            property: "opacity"
                            from: 0
                            to: 1
                            duration: 220
                        }
                    }
                }

                pushExit: Transition {
                    NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 200 }
                }

                popEnter: Transition {
                    ParallelAnimation {
                        NumberAnimation {
                            property: "x"
                            from: -stack.width * 0.18
                            to: 0
                            duration: 300
                            easing.type: Easing.OutCubic
                        }
                        NumberAnimation {
                            property: "opacity"
                            from: 0
                            to: 1
                            duration: 220
                        }
                    }
                }

                popExit: Transition {
                    NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 200 }
                }

                onCurrentItemChanged: {
                    var page = currentItem ? currentItem.pageId : "gallery"
                    window.navIndex = (page === "system") ? 1 : 0
                }
            }

            Rectangle {
                id: busyPill
                visible: backend.busy
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 22
                height: 40
                width: busyRow.implicitWidth + 36
                radius: 20
                color: Theme.surfaceAlt
                border.width: 1
                border.color: Theme.border

                Row {
                    id: busyRow
                    anchors.centerIn: parent
                    spacing: 10

                    Row {
                        spacing: 4

                        Repeater {
                            model: 3

                            Rectangle {
                                y: 4
                                width: 5
                                height: 5
                                radius: 2.5
                                color: Theme.accent
                                opacity: 0.3

                                SequentialAnimation on opacity {
                                    running: true
                                    loops: Animation.Infinite
                                    PauseAnimation { duration: index * 140 }
                                    NumberAnimation { to: 1; duration: 300 }
                                    NumberAnimation { to: 0.3; duration: 300 }
                                    PauseAnimation { duration: 380 }
                                }
                            }
                        }
                    }

                    Text {
                        text: backend.status
                        color: Theme.text
                        font.pixelSize: 12
                    }
                }
            }

            Rectangle {
                id: toast
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: 26
                anchors.bottomMargin: 22
                height: 44
                width: Math.min(430, toastLabel.implicitWidth + 34)
                radius: 12
                color: window.toastError ? "#2a1418" : Theme.surfaceAlt
                border.width: 1
                border.color: window.toastError ? "#44f87171" : Theme.border
                opacity: window.toastVisible ? 1 : 0
                visible: opacity > 0.01

                Behavior on opacity {
                    NumberAnimation { duration: 180 }
                }

                Text {
                    id: toastLabel
                    anchors.centerIn: parent
                    width: Math.min(390, implicitWidth)
                    text: window.toastText
                    color: window.toastError ? Theme.danger : Theme.text
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
            }
        }
    }

    }

    NewBackupDialog {
        id: newDialog
    }

    StoreDialog {
        id: storeDialog

        onNotify: function(message, error) {
            window.showToast(message, error ? "error" : "ok")
        }
    }

    RestoreDialog {
        id: restoreDialog

        onStoreRequested: function(query) {
            storeDialog.openWith(query)
        }

        onNotify: function(message, error) {
            window.showToast(message, error ? "error" : "ok")
        }

        onFinished: {
            if (result && result.applied > 0)
                window.showToast(result.applied + (result.applied === 1 ? " elemento restaurado" : " elementos restaurados"), "ok")
        }
    }

    Connections {
        target: backend

        function onBackupCreated(info) {
            window.showToast("Copia creada · " + info.title, "ok")
        }

        function onBackupDeleted(id) {
            window.showToast("Copia eliminada", "ok")
        }

        function onFailed(action, message) {
            window.showToast(message, "error")
        }

        function onVerified(info) {
            if (info.problems.length === 0)
                window.showToast("Copia íntegra · " + info.id, "ok")
            else
                window.showToast(info.problems.length + " problemas de integridad", "error")
        }
    }

    Component {
        id: galleryComponent

        GalleryPage {
            pageId: "gallery"

            onOpenBackup: function(id) {
                stack.push(detailComponent, { backupId: id })
            }

            onNewBackup: newDialog.openDialog()

            onRestoreRequested: function(id) {
                restoreDialog.openFor(id)
            }
        }
    }

    Component {
        id: detailComponent

        DetailPage {
            pageId: "detail"

            onBack: stack.pop()

            onRestoreRequested: restoreDialog.openFor(backupId)
        }
    }

    Component {
        id: systemComponent

        SystemPage {
            pageId: "system"

            onOpenStore: storeDialog.openWith("")
        }
    }

    Component.onCompleted: {
        if (initialBackup && initialBackup.length > 0) {
            stack.push(detailComponent, { backupId: initialBackup })
        } else if (initialPage === "system") {
            stack.push(systemComponent)
        }

        if (initialAction === "restore" && initialBackup && initialBackup.length > 0)
            restoreDialog.openFor(initialBackup)
        else if (initialAction === "new")
            newDialog.openDialog()
    }
}
