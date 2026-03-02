import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects
import QtQuick.Layouts
import Qt.labs.platform

import gui

import "../../style"
import "../../components"

Item {
    id: root

    function tr(str, file = "Settings.qml") {
        return TRANSLATOR.instance.translate(str, file)
    }

    Rectangle {
        anchors.fill: column
        color: COMMON.bg0
    }
    
    Column {
        id: column
        width: 150
        height: parent.height

        SColumnButton {
            property var name: "Program"
            label: root.tr(name)
            active: SETTINGS.currentTab == name
            onPressed: {
                SETTINGS.getGitInfo()
                SETTINGS.currentTab = name
            }
        }

        SColumnButton {
            property var name: "Remote"
            label: root.tr(name)
            active: SETTINGS.currentTab == name
            onPressed: {
                SETTINGS.currentTab = name
            }
        }

        SColumnButton {
            property var name: "Host"
            label: root.tr(name)
            active: SETTINGS.currentTab == name
            onPressed: {
                SETTINGS.currentTab = name
            }
        }
    }

    STextSelectable {
        anchors.bottom: column.bottom
        anchors.left: column.left
        anchors.right: column.right
        height: 20
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        monospace: true
        pointSize: 9.5

        color: COMMON.fg2
        text: GraphicsInfo.api + " " + GraphicsInfo.majorVersion + " " + GraphicsInfo.minorVersion + " " + GraphicsInfo.profile
    }

    Rectangle {
        id: divider
        anchors.top: column.top
        anchors.bottom: column.bottom
        anchors.left: column.right
        width: 3
        color: COMMON.bg4
    }

    Rectangle {
        anchors.top: column.top
        anchors.bottom: column.bottom
        anchors.left: divider.right
        anchors.right: parent.right
        color: COMMON.bg00

        StackLayout {
            id: settingsStack
            anchors.fill: parent
            currentIndex: ["Program", "Remote", "Host"].indexOf(SETTINGS.currentTab)
            
            ProgramSettings { }
            RemoteSettings { }
            HostSettings { }
        }
    }
}