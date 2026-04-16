import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml
import qs.Commons

Item {
    id: settingsView

    property var pluginApi: null
    readonly property var anime: pluginApi?.mainInstance || null

    signal backRequested()

    component SettingChoiceButton: ChoiceChip {
        property bool active: false

        selected: active
        minWidth: 92
        controlHeight: 38
        horizontalPadding: 18
        fontPixelSize: 12
        letterSpacing: 0.3
        idleBackgroundColor: Color.mSurface
        hoverBackgroundColor: Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.18)
        idleBorderColor: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.55)
        hoverTextColor: Color.mPrimary
        idleTextColor: Color.mOnSurface
    }

    component SettingTextField: Rectangle {
        id: fieldRoot

        property string value: ""
        property string placeholderText: ""
        property bool secret: false
        signal textEdited(string text)

        implicitHeight: 40
        radius: 20
        color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.92)
        border.width: input.activeFocus ? 1.5 : 1
        border.color: input.activeFocus
            ? Color.mPrimary
            : Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.5)

        Behavior on border.color { ColorAnimation { duration: 160 } }

        Binding {
            target: input
            property: "text"
            value: fieldRoot.value
            when: !input.activeFocus
        }

        TextInput {
            id: input
            anchors {
                left: parent.left
                right: parent.right
                verticalCenter: parent.verticalCenter
                leftMargin: 14
                rightMargin: 14
            }
            color: Color.mOnSurface
            font.pixelSize: 12
            clip: true
            selectByMouse: true
            echoMode: fieldRoot.secret ? TextInput.Password : TextInput.Normal
            onTextChanged: fieldRoot.textEdited(text)
        }

        Text {
            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
                leftMargin: 14
            }
            text: fieldRoot.placeholderText
            color: Color.mOnSurfaceVariant
            font.pixelSize: 12
            opacity: 0.58
            visible: input.text.length === 0
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(Color.mSurfaceVariant.r, Color.mSurfaceVariant.g, Color.mSurfaceVariant.b, 0.08) }
            GradientStop { position: 1.0; color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.12) }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ────────────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 68
            color: "transparent"
            z: 2

            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 1
                color: Color.mOutlineVariant
                opacity: 0.35
            }

            RowLayout {
                anchors {
                    fill: parent
                    leftMargin: 10
                    rightMargin: 16
                    topMargin: 8
                    bottomMargin: 8
                }
                spacing: 10

                HoverIconButton {
                    text: "←"
                    buttonSize: 40
                    innerSize: 40
                    iconPixelSize: 18
                    idleOpacity: 0.82
                    activeOpacity: 1.0
                    onClicked: settingsView.backRequested()
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 40
                    radius: 20
                    color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.88)
                    border.width: 1
                    border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.45)

                    Row {
                        anchors {
                            left: parent.left
                            verticalCenter: parent.verticalCenter
                            leftMargin: 14
                        }
                        spacing: 8

                        Rectangle {
                            width: 24
                            height: 24
                            radius: 12
                            color: Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.14)

                            Text {
                                anchors.centerIn: parent
                                text: "⚙"
                                font.pixelSize: 12
                                color: Color.mPrimary
                            }
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 1

                            Text {
                                text: "Settings"
                                font.pixelSize: 14
                                font.bold: true
                                color: Color.mOnSurface
                            }

                            Text {
                                text: "Layout and browsing preferences"
                                font.pixelSize: 10
                                color: Color.mOnSurfaceVariant
                                opacity: 0.72
                            }
                        }
                    }
                }
            }
        }

        // ── Content ───────────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "transparent"

            ScrollView {
                id: settingsScroll
                anchors.fill: parent
                anchors.margins: 14
                contentWidth: availableWidth
                clip: true

                Column {
                    width: settingsScroll.availableWidth
                    spacing: 14

                    Rectangle {
                        width: parent.width
                        radius: 18
                        color: Qt.rgba(Color.mSurfaceVariant.r, Color.mSurfaceVariant.g, Color.mSurfaceVariant.b, 0.7)
                        border.width: 1
                        border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.38)
                        implicitHeight: heroColumn.implicitHeight + 28

                        Column {
                            id: heroColumn
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 8

                            Text {
                                text: "Tune the panel"
                                font.pixelSize: 17
                                font.bold: true
                                color: Color.mOnSurface
                            }

                            Text {
                                width: parent.width
                                text: "Adjust the drawer width, poster density, and sync preferences while the provider split settles."
                                wrapMode: Text.Wrap
                                lineHeight: 1.35
                                font.pixelSize: 11
                                color: Color.mOnSurfaceVariant
                                opacity: 0.82
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        radius: 20
                        color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.86)
                        border.width: 1
                        border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.4)
                        implicitHeight: panelSection.implicitHeight + 32

                        Column {
                            id: panelSection
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 12

                            Row {
                                spacing: 10

                                Rectangle {
                                    width: 28
                                    height: 28
                                    radius: 14
                                    color: Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.12)

                                    Text {
                                        anchors.centerIn: parent
                                        text: "▣"
                                        font.pixelSize: 12
                                        color: Color.mPrimary
                                    }
                                }

                                Column {
                                    spacing: 2

                                    Text {
                                        text: "Panel Size"
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: Color.mOnSurface
                                    }

                                    Text {
                                        text: "Controls how wide the plugin drawer appears"
                                        font.pixelSize: 11
                                        color: Color.mOnSurfaceVariant
                                        opacity: 0.72
                                    }
                                }
                            }

                            Flow {
                                width: parent.width
                                spacing: 10

                                Repeater {
                                    model: [
                                        { label: "Small",  value: "small" },
                                        { label: "Medium", value: "medium" },
                                        { label: "Large",  value: "large" }
                                    ]

                                    delegate: SettingChoiceButton {
                                        text: modelData.label
                                        active: anime?.panelSize === modelData.value
                                        onClicked: if (anime) anime.setSetting("panelSize", modelData.value)
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        radius: 20
                        color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.86)
                        border.width: 1
                        border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.4)
                        implicitHeight: posterSection.implicitHeight + 32

                        Column {
                            id: posterSection
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 12

                            Row {
                                spacing: 10

                                Rectangle {
                                    width: 28
                                    height: 28
                                    radius: 14
                                    color: Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.12)

                                    Text {
                                        anchors.centerIn: parent
                                        text: "◫"
                                        font.pixelSize: 12
                                        color: Color.mPrimary
                                    }
                                }

                                Column {
                                    spacing: 2

                                    Text {
                                        text: "Poster Size"
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: Color.mOnSurface
                                    }

                                    Text {
                                        text: "Adjust the size of anime covers in the grid"
                                        font.pixelSize: 11
                                        color: Color.mOnSurfaceVariant
                                        opacity: 0.72
                                    }
                                }
                            }

                            Flow {
                                width: parent.width
                                spacing: 10

                                Repeater {
                                    model: [
                                        { label: "Small",  value: "small" },
                                        { label: "Medium", value: "medium" },
                                        { label: "Large",  value: "large" }
                                    ]

                                    delegate: SettingChoiceButton {
                                        text: modelData.label
                                        active: anime?.posterSize === modelData.value
                                        enabled: !(anime?.panelSize === "small" && modelData.value === "small")
                                        onClicked: if (anime) anime.setSetting("posterSize", modelData.value)
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        visible: false  // Hidden for now; keep mirror preference wiring intact.
                        width: parent.width
                        radius: 20
                        color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.86)
                        border.width: 1
                        border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.4)
                        implicitHeight: providerSection.implicitHeight + 32

                        Column {
                            id: providerSection
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 12

                            Row {
                                spacing: 10

                                Rectangle {
                                    width: 28
                                    height: 28
                                    radius: 14
                                    color: Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.12)

                                    Text {
                                        anchors.centerIn: parent
                                        text: "↺"
                                        font.pixelSize: 12
                                        color: Color.mPrimary
                                    }
                                }

                                Column {
                                    spacing: 2

                                    Text {
                                        text: "Preferred Stream Mirror"
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: Color.mOnSurface
                                    }

                                    Text {
                                        text: "Prioritize an AllAnime-backed mirror while keeping fallback behavior"
                                        font.pixelSize: 11
                                        color: Color.mOnSurfaceVariant
                                        opacity: 0.72
                                    }
                                }
                            }

                            Flow {
                                width: parent.width
                                spacing: 10

                                Repeater {
                                    model: [
                                        { label: "Auto", value: "auto" },
                                        { label: "Default", value: "default" },
                                        { label: "SharePoint", value: "sharepoint" },
                                        { label: "HiAnime", value: "hianime" },
                                        { label: "YouTube", value: "youtube" }
                                    ]

                                    delegate: SettingChoiceButton {
                                        text: modelData.label
                                        active: anime?.preferredProvider === modelData.value
                                        onClicked: if (anime) anime.setSetting("preferredProvider", modelData.value)
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        radius: 20
                        color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.86)
                        border.width: 1
                        border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.4)
                        implicitHeight: malSection.implicitHeight + 32

                        Column {
                            id: malSection
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 14

                            Row {
                                spacing: 10

                                Rectangle {
                                    width: 28
                                    height: 28
                                    radius: 14
                                    color: Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.12)

                                    Text {
                                        anchors.centerIn: parent
                                        text: "M"
                                        font.pixelSize: 12
                                        font.bold: true
                                        color: Color.mPrimary
                                    }
                                }

                                Column {
                                    spacing: 2

                                    Text {
                                        text: "MyAnimeList Sync"
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: Color.mOnSurface
                                    }

                                    Text {
                                        width: settingsScroll.availableWidth - 80
                                        text: "Keep AniList as the in-app metadata source and use MyAnimeList only for account sync. This first pass syncs the current local library both ways for mapped titles."
                                        wrapMode: Text.Wrap
                                        lineHeight: 1.35
                                        font.pixelSize: 11
                                        color: Color.mOnSurfaceVariant
                                        opacity: 0.76
                                    }
                                }
                            }

                            Rectangle {
                                width: parent.width
                                radius: 18
                                color: Qt.rgba(Color.mSurfaceVariant.r, Color.mSurfaceVariant.g, Color.mSurfaceVariant.b, 0.56)
                                border.width: 1
                                border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.32)
                                implicitHeight: malStatusColumn.implicitHeight + 22

                                Column {
                                    id: malStatusColumn
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 8

                                    Row {
                                        spacing: 8

                                        Rectangle {
                                            width: statusLabel.implicitWidth + 18
                                            height: 26
                                            radius: 13
                                            color: anime?.malSync?.enabled
                                                ? Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.16)
                                                : Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.8)
                                            border.width: 1
                                            border.color: anime?.malSync?.enabled
                                                ? Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.42)
                                                : Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.4)

                                            Text {
                                                id: statusLabel
                                                anchors.centerIn: parent
                                                text: anime?.malSync?.enabled
                                                    ? ("Connected" + (anime?.malSync?.userName ? " · " + anime.malSync.userName : ""))
                                                    : "Not Connected"
                                                font.pixelSize: 11
                                                font.bold: true
                                                color: anime?.malSync?.enabled ? Color.mPrimary : Color.mOnSurface
                                            }
                                        }

                                        Rectangle {
                                            width: autoPushLabel.implicitWidth + 18
                                            height: 26
                                            radius: 13
                                            color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.82)
                                            border.width: 1
                                            border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.38)

                                            Text {
                                                id: autoPushLabel
                                                anchors.centerIn: parent
                                                text: anime?.malSync?.autoPush ? "Auto Push On" : "Auto Push Off"
                                                font.pixelSize: 11
                                                color: Color.mOnSurfaceVariant
                                            }
                                        }
                                    }

                                    Text {
                                        width: parent.width
                                        text: anime?.malSync?.lastSyncAt
                                            ? ("Last " + (anime?.malSync?.lastSyncDirection || "sync") + " · " + new Date(Number(anime.malSync.lastSyncAt) * 1000).toLocaleString())
                                            : "No successful MyAnimeList sync yet."
                                        wrapMode: Text.Wrap
                                        font.pixelSize: 11
                                        color: Color.mOnSurfaceVariant
                                        opacity: 0.74
                                    }

                                    Text {
                                        visible: (anime?.malSyncMessage || "").length > 0
                                        width: parent.width
                                        text: anime?.malSyncMessage || ""
                                        wrapMode: Text.Wrap
                                        font.pixelSize: 11
                                        color: Color.mPrimary
                                    }

                                    Text {
                                        visible: (anime?.malSyncError || "").length > 0
                                        width: parent.width
                                        text: anime?.malSyncError || ""
                                        wrapMode: Text.Wrap
                                        font.pixelSize: 11
                                        color: Color.mError
                                    }
                                }
                            }

                            Column {
                                spacing: 8

                                Text {
                                    text: "Client ID"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: Color.mOnSurface
                                }

                                SettingTextField {
                                    width: parent.width
                                    value: anime?.malSync?.clientId || ""
                                    placeholderText: "MyAnimeList client id"
                                    onTextEdited: if (anime) anime.setMalSyncField("clientId", text)
                                }
                            }

                            Column {
                                spacing: 8

                                Text {
                                    text: "Client Secret"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: Color.mOnSurface
                                }

                                SettingTextField {
                                    width: parent.width
                                    value: anime?.malSync?.clientSecret || ""
                                    placeholderText: "Optional client secret"
                                    secret: true
                                    onTextEdited: if (anime) anime.setMalSyncField("clientSecret", text)
                                }
                            }

                            Column {
                                spacing: 8

                                Text {
                                    text: "Redirect URI"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: Color.mOnSurface
                                }

                                SettingTextField {
                                    width: parent.width
                                    value: anime?.malSync?.redirectUri || ""
                                    placeholderText: "Registered redirect URI, if your MAL app requires one"
                                    onTextEdited: if (anime) anime.setMalSyncField("redirectUri", text)
                                }
                            }

                            Column {
                                spacing: 8

                                Text {
                                    text: "Authorization Code"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: Color.mOnSurface
                                }

                                SettingTextField {
                                    width: parent.width
                                    value: anime?.malSyncAuthCode || ""
                                    placeholderText: "Paste the `code` query parameter from the browser redirect"
                                    onTextEdited: if (anime) anime.malSyncAuthCode = text
                                }
                            }

                            Column {
                                spacing: 8

                                Text {
                                    text: "Auto Push"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: Color.mOnSurface
                                }

                                Flow {
                                    width: parent.width
                                    spacing: 10

                                    Repeater {
                                        model: [
                                            { label: "Manual", value: false },
                                            { label: "Auto Push", value: true }
                                        ]

                                        delegate: SettingChoiceButton {
                                            text: modelData.label
                                            active: (anime?.malSync?.autoPush === true) === modelData.value
                                            onClicked: if (anime) anime.setMalSyncField("autoPush", modelData.value)
                                        }
                                    }
                                }
                            }

                            Flow {
                                width: parent.width
                                spacing: 10

                                ActionChip {
                                    text: "Open Auth"
                                    leadingText: "↗"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.startMalAuth()
                                }

                                ActionChip {
                                    text: "Finish Connect"
                                    leadingText: "✓"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.exchangeMalAuthCode()
                                }

                                ActionChip {
                                    text: "Refresh Session"
                                    leadingText: "↺"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.refreshMalSyncSession(true)
                                }

                                ActionChip {
                                    text: "Pull From MAL"
                                    leadingText: "↓"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.pullMalSync(true)
                                }

                                ActionChip {
                                    text: "Push To MAL"
                                    leadingText: "↑"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.pushMalSync(true)
                                }

                                ActionChip {
                                    text: "Disconnect"
                                    leadingText: "✕"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    baseColor: Qt.rgba(Color.mSurfaceVariant.r, Color.mSurfaceVariant.g, Color.mSurfaceVariant.b, 0.86)
                                    hoverColor: Qt.rgba(Color.mError.r, Color.mError.g, Color.mError.b, 0.18)
                                    hoverBorderColor: Qt.rgba(Color.mError.r, Color.mError.g, Color.mError.b, 0.4)
                                    hoverTextColor: Color.mError
                                    onClicked: if (anime) anime.clearMalSyncSession()
                                }
                            }

                            Text {
                                width: parent.width
                                text: "Flow: save your MAL app credentials here, open auth in the browser, approve access, paste back the `code`, then finish connect. Pull updates local progress from MAL. Push sends AnimeReloaded progress back out."
                                wrapMode: Text.Wrap
                                lineHeight: 1.35
                                font.pixelSize: 11
                                color: Color.mOnSurfaceVariant
                                opacity: 0.72
                            }
                        }
                    }
                }
            }
        }
    }
}
