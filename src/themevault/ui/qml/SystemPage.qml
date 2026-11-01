import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page

    property string pageId: "system"
    property var info: ({})

    signal openStore()

    Component.onCompleted: info = backend.systemInfo()

    component InfoCard: Rectangle {
        id: cardRoot
        property string label: ""
        property string value: ""
        property string hint: ""

        Layout.fillWidth: true
        implicitHeight: 92
        radius: Theme.radius
        color: Theme.surface
        border.width: 1
        border.color: Theme.border

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 3

            Text {
                text: cardRoot.label
                color: Theme.textFaint
                font.pixelSize: 10
                font.weight: Font.DemiBold
                font.letterSpacing: 0.8
            }

            Text {
                Layout.fillWidth: true
                text: cardRoot.value
                color: Theme.text
                font.pixelSize: 14
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: cardRoot.hint
                color: Theme.textDim
                font.pixelSize: 10
                elide: Text.ElideRight
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 18

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                spacing: 4

                Text {
                    text: "Sistema"
                    color: Theme.text
                    font.pixelSize: 26
                    font.weight: Font.DemiBold
                }

                Text {
                    text: "Detección del entorno y herramientas disponibles"
                    color: Theme.textDim
                    font.pixelSize: 13
                }
            }

            Item { Layout.fillWidth: true }

            AppButton {
                text: "Tienda de widgets"
                variant: "ghost"
                onClicked: page.openStore()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 14

            InfoCard {
                label: "DISTRIBUCIÓN"
                value: page.info.distro || "—"
                hint: page.info.distroId || ""
            }

            InfoCard {
                label: "ESCRITORIO"
                value: page.info.de || "—"
                hint: page.info.session || ""
            }

            InfoCard {
                label: "COPIAS"
                value: (page.info.backups || 0) + ((page.info.backups || 0) === 1 ? " copia" : " copias")
                hint: page.info.storage || ""
            }

            InfoCard {
                label: "ACTIVOS"
                value: (page.info.assets ? page.info.assets.themes : 0) + " temas"
                hint: (page.info.assets ? page.info.assets.icons : 0) + " juegos de iconos"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.radius
                color: Theme.surface
                border.width: 1
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 0

                    Text {
                        text: "ADAPTADORES"
                        color: Theme.textFaint
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.8
                        Layout.bottomMargin: 12
                    }

                    Repeater {
                        model: page.info.adapters || []

                        Item {
                            Layout.fillWidth: true
                            implicitHeight: 40

                            Rectangle {
                                id: dot
                                width: 8
                                height: 8
                                radius: 4
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                color: modelData.detected ? Theme.ok : Theme.borderStrong
                            }

                            Text {
                                anchors.left: dot.right
                                anchors.leftMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.label
                                color: modelData.detected ? Theme.text : Theme.textDim
                                font.pixelSize: 12
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.detected ? "activo" : "inactivo"
                                color: modelData.detected ? Theme.ok : Theme.textFaint
                                font.pixelSize: 10
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    Text {
                        Layout.fillWidth: true
                        text: "Los adaptadores inactivos se pueden forzar al crear una copia desde la línea de comandos."
                        color: Theme.textFaint
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.radius
                color: Theme.surface
                border.width: 1
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 0

                    Text {
                        text: "HERRAMIENTAS"
                        color: Theme.textFaint
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.8
                        Layout.bottomMargin: 12
                    }

                    Repeater {
                        model: page.info.tools || []

                        Item {
                            Layout.fillWidth: true
                            implicitHeight: 40

                            Rectangle {
                                id: statusDot
                                width: 8
                                height: 8
                                radius: 4
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                color: modelData.ok ? Theme.ok : Theme.borderStrong
                            }

                            Text {
                                anchors.left: statusDot.right
                                anchors.leftMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.name
                                color: modelData.ok ? Theme.text : Theme.textDim
                                font.pixelSize: 12
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.purpose
                                color: Theme.textFaint
                                font.pixelSize: 10
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 68
            radius: Theme.radius
            color: Theme.surface
            border.width: 1
            border.color: Theme.border

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3

                Text {
                    text: "UBICACIÓN DEL ALMACÉN"
                    color: Theme.textFaint
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }

                Text {
                    text: page.info.root || ""
                    color: Theme.text
                    font.pixelSize: 12
                }
            }

            AppButton {
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                text: "Abrir carpeta"
                variant: "ghost"
                small: true
                onClicked: backend.openFolder()
            }
        }

        Item { Layout.fillHeight: true }
    }
}
