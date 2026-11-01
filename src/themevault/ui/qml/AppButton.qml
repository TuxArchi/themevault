import QtQuick
import QtQuick.Controls

Button {
    id: control

    // primary | ghost | subtle | danger
    property string variant: "primary"
    property bool small: false

    implicitHeight: small ? 32 : 38
    implicitWidth: Math.max(74, contentItem.implicitWidth + (small ? 24 : 34))
    padding: 0
    hoverEnabled: true
    focusPolicy: Qt.NoFocus

    contentItem: Text {
        text: control.text
        color: {
            if (control.variant === "primary") return "#ffffff"
            if (control.variant === "danger") return Theme.danger
            if (!control.enabled) return Theme.textFaint
            return Theme.text
        }
        font.pixelSize: control.small ? 12.5 : 13.5
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: Theme.radiusSmall
        color: {
            if (control.variant === "primary") {
                return control.hovered ? "#7c4eff" : Theme.accent
            }
            if (control.variant === "ghost") {
                return control.hovered ? Theme.surfaceHover : "transparent"
            }
            if (control.variant === "subtle") {
                return control.hovered ? Theme.borderStrong : Theme.surfaceAlt
            }
            if (control.variant === "danger") {
                return control.hovered ? "#18f87171" : "transparent"
            }
            return "transparent"
        }
        border.width: (control.variant === "ghost" || control.variant === "danger") ? 1 : 0
        border.color: control.variant === "danger" ? "#44f87171" : Theme.border
        opacity: control.enabled ? 1 : 0.45

        Behavior on color {
            ColorAnimation { duration: 120 }
        }
    }
}
