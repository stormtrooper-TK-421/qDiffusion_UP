import QtQuick
import QtQuick.Controls

import gui

ApplicationWindow {
    id: root
    readonly property string startupQmlDirUrl: STARTUP_QML_DIR_URL
    visible: true
    width: 1100
    height: 600
    color: "#1a1a1a"
    title: TRANSLATOR.instance.translate("qDiffusion", "Title");
    flags: Qt.Window | Qt.WindowStaysOnTopHint

    Item {
        anchors.fill: parent

        Image {
            opacity: 0.5
            id: spinner
            source: startupQmlDirUrl + "/icons/loading.svg"
            width: 80
            height: 80
            sourceSize: Qt.size(width, height)
            anchors.centerIn: parent
            smooth: true
            antialiasing: true
        }

        RotationAnimator {
            id: spinnerAnimator
            loops: Animation.Infinite
            target: spinner
            from: 0
            to: 360
            duration: 1000
            running: spinner.visible
        }
    }

    Component.onCompleted: {
        root.flags = Qt.Window
        root.requestActivate()
        COORDINATOR.load()
    }

    Connections {
        target: COORDINATOR
        property var installer: null
        function onShow() {
            var component = Qt.createComponent(startupQmlDirUrl + "/Installer.qml")
            if(component.status != Component.Ready) {
                console.log("ERROR", component.errorString())
            } else {
                installer = component.createObject(root, { window: root, spinner: spinner })
            }
        }

        function onProceed() {
            var component = Qt.createComponent(startupQmlDirUrl + "/Main.qml")
            if(component.status != Component.Ready) {
                console.log("ERROR", component.errorString())
            } else {
                component.createObject(root, { window: root, spinner: spinner })
            }
        }
    }
}
