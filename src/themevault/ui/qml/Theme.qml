pragma Singleton
import QtQuick

QtObject {
    // Fondo y superficies
    readonly property color bg: "#080e12"
    readonly property color surface: "#0d1519"
    readonly property color surfaceAlt: "#121e23"
    readonly property color surfaceHover: "#17272d"
    readonly property color border: "#1e2b31"
    readonly property color borderStrong: "#2b3d44"

    // Texto
    readonly property color text: "#e9f2f1"
    readonly property color textDim: "#9bb3b0"
    readonly property color textFaint: "#6a8582"

    // Acento
    readonly property color accent: "#2dd4bf"
    readonly property color accent2: "#0891b2"
    readonly property color accentSoft: "#262dd4bf"
    readonly property color accentLine: "#662dd4bf"

    // Estados
    readonly property color ok: "#34d399"
    readonly property color warn: "#fbbf24"
    readonly property color danger: "#f87171"

    readonly property int radius: 16
    readonly property int radiusSmall: 10
    readonly property int radiusInput: 9

    readonly property string appVersion: "0.9.0"
}
