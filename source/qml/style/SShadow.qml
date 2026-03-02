import QtQuick 2.15
import QtQuick.Controls 2.15
import Qt5Compat.GraphicalEffects

import gui 1.0

Item {
    id: root
    property var color: COMMON.bg00
    property var shadowColor: "#f0000000"
    property var radius: 16
    property var samples: 16

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        color: root.color
    }

    layer.enabled: COMMON.effectsEnabled
    layer.effect: InnerShadow {
        id: innerShadow
        visible: COMMON.effectsEnabled
        color: root.shadowColor
        samples: root.samples
        radius: root.radius
        spread: 0
        fast: true
    }
}