import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects
import QtQuick.Layouts
import Qt.labs.platform

import gui

import "../../qml/style"
import "../../qml/components"

SColumnButton {
    id: root

    function tr(str, file = "CategoryButton.qml") {
        return TRANSLATOR.instance.translate(str, file)
    }

    property var mode
    label: root.tr(EXPLORER.getLabel(mode), "Category")
    active: EXPLORER.currentTab == mode

    signal move(string model, string folder, string subfolder)
    
    onPressed: {
        EXPLORER.setCurrent(mode, "")
    }

    AdvancedDropArea {
        id: basicDrop
        anchors.fill: parent
        onContainsDragChanged: {
            if(containsDrag) {
                dragTimer.start()
            } else {
                dragTimer.stop()
            }
        }
        Timer {
            id: dragTimer
            interval: 200
            onTriggered: {
                EXPLORER.setCurrent(mode, "")
            }
        }
        onDropped: {
            var model = EXPLORER.onDrop(mimeData)
            if(model != "") {
                root.move(model, mode, "")
            }
        }
    }
}