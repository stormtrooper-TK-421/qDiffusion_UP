import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects
import Qt.labs.platform

import gui
import "../../style"
import "../../components"

Item {
    id: root

    SShadow {
        opacity: 0.7
        anchors.fill: parent
    }

    BasicInputs {
        id: inputArea
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: divider.top
    }

    BasicOutputs {
        id: outputArea
        anchors.top: divider.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
    }

    SDividerHB {
        id: divider
        minOffset: 128
        maxOffset: parent.height-128
        offset: snap
        snap: Math.floor(parent.height/2)+2
        snapSize: 20
        height: 4
        topOverflow: inputArea.scrollBar.policy == ScrollBar.AlwaysOn ? 0 : 6
        bottomOverflow: 6
        color: "transparent"
        Rectangle {
            anchors.fill: parent
            color: COMMON.bg5
            anchors.topMargin: 1
            anchors.bottomMargin: 1
        }
    }
}