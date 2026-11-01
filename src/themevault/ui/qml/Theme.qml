pragma Singleton
import QtQuick

QtObject {
    // Fondo y superficies
    readonly property color bg: "#0a0a0f"
    readonly property color surface: "#101018"
    readonly property color surfaceAlt: "#15151f"
    readonly property color surfaceHover: "#191924"
    readonly property color border: "#232330"
    readonly property color borderStrong: "#30303f"

    // Texto
    readonly property color text: "#e9e9f2"
    readonly property color textDim: "#9b9bb0"
    readonly property color textFaint: "#6a6a7e"

    // Acento
    readonly property color accent: "#8b5cf6"
    readonly property color accent2: "#6366f1"
    readonly property color accentSoft: "#268b5cf6"
    readonly property color accentLine: "#668b5cf6"

    // Estados
    readonly property color ok: "#34d399"
    readonly property color warn: "#fbbf24"
    readonly property color danger: "#f87171"

    readonly property int radius: 16
    readonly property int radiusSmall: 10
    readonly property int radiusInput: 9

    readonly property string appVersion: "0.4.0"
}
