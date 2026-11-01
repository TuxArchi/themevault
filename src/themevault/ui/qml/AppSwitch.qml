import QtQuick

Item {
    id: root

    property bool checked: true
    signal toggled(bool value)

    implicitWidth: 44
    implicitHeight: 26

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.checked ? Theme.accent : Theme.borderStrong
        opacity: mouse.containsMouse ? 1 : 0.92

        Behavior on color {
            ColorAnimation { duration: 150 }
        }
    }

    Rectangle {
        id: knob
        width: 20
        height: 20
        radius: 10
        y: 3
        x: root.checked ? root.width - width - 3 : 3
        color: "#ffffff"

        Behavior on x {
            NumberAnimation { duration: 170; easing.type: Easing.OutCubic }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            root.checked = !root.checked
            root.toggled(root.checked)
        }
    }
}
