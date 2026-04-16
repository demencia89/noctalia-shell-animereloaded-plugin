import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml
import qs.Commons

Item {
    id: settingsView

    property var pluginApi: null
    readonly property var anime: pluginApi?.mainInstance || null
    property string malInspectorFilter: ""
    readonly property var malInspectorEntries: {
        var _ = anime?.libraryVersion ?? 0
        var __ = anime?.malSyncResults ?? []
        var ___ = anime?.malSync?.enabled ?? false
        var ____ = anime?.malSync?.lastSyncAt ?? 0
        return settingsView._buildMalInspectorEntries()
    }
    readonly property var malInspectorCounts: settingsView._malInspectorCounts(malInspectorEntries)
    readonly property string effectiveMalInspectorFilter:
        settingsView._resolvedMalInspectorFilter()
    readonly property var filteredMalInspectorEntries:
        settingsView._filterMalInspectorEntries(malInspectorEntries, effectiveMalInspectorFilter)

    signal backRequested()

    function _malToneFill(tone, dense) {
        var alpha = dense === true ? 0.94 : 0.88
        var base = Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, alpha)
        if (tone === "error")
            return Qt.tint(base, Qt.rgba(Color.mError.r, Color.mError.g, Color.mError.b, 0.18))
        if (tone === "accent")
            return Qt.tint(base, Qt.rgba(Color.mTertiary.r, Color.mTertiary.g, Color.mTertiary.b, 0.18))
        if (tone === "primary")
            return Qt.tint(base, Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.18))
        return base
    }

    function _malToneBorder(tone) {
        if (tone === "error")
            return Qt.rgba(Color.mError.r, Color.mError.g, Color.mError.b, 0.34)
        if (tone === "accent")
            return Qt.rgba(Color.mTertiary.r, Color.mTertiary.g, Color.mTertiary.b, 0.34)
        if (tone === "primary")
            return Qt.rgba(Color.mPrimary.r, Color.mPrimary.g, Color.mPrimary.b, 0.34)
        return Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.38)
    }

    function _malToneText(tone) {
        if (tone === "error")
            return Color.mError
        if (tone === "accent")
            return Color.mTertiary
        if (tone === "primary")
            return Color.mPrimary
        return Color.mOnSurfaceVariant
    }

    function _malInspectorPriority(item) {
        var key = String(item?.badgeKey || "")
        if (key === "error")
            return 0
        if (key === "unmapped")
            return 1
        if (key === "skipped")
            return 2
        if (key === "removed")
            return 3
        if (key === "linked")
            return 4
        if (key === "imported")
            return 5
        if (key === "synced")
            return 6
        return 7
    }

    function _buildMalInspectorEntries() {
        var entries = anime?.libraryList || []
        var items = entries.map(function(entry) {
            return anime?.malSyncStatusEntry ? anime.malSyncStatusEntry(entry) : null
        }).filter(function(item) {
            return item !== null
        })

        items.sort(function(a, b) {
            var priorityDelta = settingsView._malInspectorPriority(a) - settingsView._malInspectorPriority(b)
            if (priorityDelta !== 0)
                return priorityDelta
            return String(a.title || "").localeCompare(String(b.title || ""))
        })
        return items
    }

    function _matchesMalInspectorFilter(item, filterKey) {
        var key = String(item?.badgeKey || "")
        var filter = String(filterKey || "")
        if (filter === "attention")
            return settingsView._malNeedsAttention(item)
        if (filter === "synced")
            return key === "synced" || key === "imported"
        if (filter === "ready")
            return key === "linked"
        return true
    }

    function _filterMalInspectorEntries(entries, filterKey) {
        return (entries || []).filter(function(item) {
            return settingsView._matchesMalInspectorFilter(item, filterKey)
        })
    }

    function _malNeedsAttention(item) {
        var key = String(item?.badgeKey || "")
        return key === "error" || key === "unmapped" || key === "skipped" || key === "removed"
    }

    function _malInspectorCounts(entries) {
        var list = entries || []
        var counts = {
            total: list.length,
            mapped: 0,
            attention: 0,
            ready: 0,
            synced: 0
        }

        for (var i = 0; i < list.length; i++) {
            var item = list[i] || ({})
            var key = String(item?.badgeKey || "")
            if (String(item.malId || "").length > 0)
                counts.mapped += 1
            if (_malNeedsAttention(item))
                counts.attention += 1
            else if (key === "linked")
                counts.ready += 1
            else if (key === "synced" || key === "imported")
                counts.synced += 1
        }

        return counts
    }

    function _resolvedMalInspectorFilter() {
        if (malInspectorFilter === "attention" || malInspectorFilter === "ready" || malInspectorFilter === "synced")
            return malInspectorFilter

        var counts = malInspectorCounts || ({})
        if (Number(counts.attention || 0) > 0)
            return "attention"
        if (Number(counts.ready || 0) > 0)
            return "ready"
        if (Number(counts.synced || 0) > 0)
            return "synced"
        return "attention"
    }

    function _malInspectorSummary() {
        var counts = malInspectorCounts || ({})
        var entries = malInspectorEntries || []
        if (entries.length === 0)
            return "No library titles are available for MAL inspection yet."

        if (Number(counts.attention || 0) > 0)
            return String(counts.attention) + " title"
                + (counts.attention === 1 ? "" : "s")
                + " need attention before the next clean sync."
        if (Number(counts.ready || 0) > 0)
            return String(counts.ready) + " mapped title"
                + (counts.ready === 1 ? "" : "s")
                + " are ready to push when you want MAL updated."
        if (Number(counts.synced || 0) > 0)
            return "Recent MAL sync state looks healthy across "
                + String(counts.synced) + " title"
                + (counts.synced === 1 ? "" : "s") + "."
        return String(counts.total || 0) + " titles are tracked locally, but none are mapped to MAL yet."
    }

    function _malInspectorSectionTitle() {
        if (effectiveMalInspectorFilter === "attention")
            return "Needs Attention"
        if (effectiveMalInspectorFilter === "ready")
            return "Ready To Push"
        return "Recently Synced"
    }

    function _malInspectorSectionHint() {
        if (effectiveMalInspectorFilter === "attention")
            return "Review these titles first. They are the ones most likely to block or confuse your next MAL sync."
        if (effectiveMalInspectorFilter === "ready")
            return "These titles are mapped cleanly. Push when you want local watch progress reflected on MAL."
        return "These titles are already aligned. No action is needed unless you changed progress locally."
    }

    function _malInspectorEmptyText() {
        if (effectiveMalInspectorFilter === "attention")
            return "Nothing currently needs MAL attention."
        if (effectiveMalInspectorFilter === "ready")
            return "No mapped titles are currently waiting for a manual push."
        return "No recently synced titles are available to show yet."
    }

    function _malInspectorMetaText(item) {
        var parts = []
        if (String(item?.malId || "").length > 0)
            parts.push("MAL #" + String(item.malId))
        if (String(item?.remoteStatus || "").length > 0)
            parts.push("Remote: " + String(item.remoteStatus))
        else if (String(item?.badgeKey || "") === "linked")
            parts.push("Mapped and ready")
        parts.push(String(item?.localProgress || ""))
        if (Number(item?.remoteWatchedEpisodes || 0) > 0)
            parts.push("MAL watched " + String(item.remoteWatchedEpisodes))
        return parts.filter(function(part) {
            return String(part || "").length > 0
        }).join(" · ")
    }

    function _malInspectorDetailText(item) {
        if (!settingsView._malNeedsAttention(item))
            return ""
        return String(item?.detail || "")
    }

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
                                        text: "Keep AniList as the in-app metadata source and use MyAnimeList only for account sync. Regular login now happens in the browser and returns automatically to AnimeReloaded through a localhost callback."
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

                                    Column {
                                        width: parent.width
                                        spacing: 10
                                        visible: (settingsView.malInspectorEntries || []).length > 0

                                        Text {
                                            text: "Library Sync Status"
                                            font.pixelSize: 11
                                            font.bold: true
                                            color: Color.mOnSurface
                                        }

                                        Text {
                                            width: parent.width
                                            text: settingsView._malInspectorSummary()
                                            wrapMode: Text.Wrap
                                            lineHeight: 1.35
                                            font.pixelSize: 10
                                            color: Color.mOnSurfaceVariant
                                            opacity: 0.74
                                        }

                                        Flow {
                                            width: parent.width
                                            spacing: 8

                                            Repeater {
                                                model: [
                                                    {
                                                        key: "attention",
                                                        label: "Attention " + String(settingsView.malInspectorCounts.attention || 0)
                                                    },
                                                    {
                                                        key: "ready",
                                                        label: "Ready " + String(settingsView.malInspectorCounts.ready || 0)
                                                    },
                                                    {
                                                        key: "synced",
                                                        label: "Synced " + String(settingsView.malInspectorCounts.synced || 0)
                                                    }
                                                ]

                                                delegate: SettingChoiceButton {
                                                    text: modelData.label
                                                    active: settingsView.effectiveMalInspectorFilter === modelData.key
                                                    minWidth: 84
                                                    controlHeight: 30
                                                    fontPixelSize: 11
                                                    onClicked: settingsView.malInspectorFilter = modelData.key
                                                }
                                            }
                                        }

                                        Rectangle {
                                            width: parent.width
                                            radius: 16
                                            color: settingsView.effectiveMalInspectorFilter === "attention"
                                                ? settingsView._malToneFill("error")
                                                : (settingsView.effectiveMalInspectorFilter === "ready"
                                                    ? settingsView._malToneFill("accent")
                                                    : settingsView._malToneFill("primary"))
                                            border.width: 1
                                            border.color: settingsView.effectiveMalInspectorFilter === "attention"
                                                ? settingsView._malToneBorder("error")
                                                : (settingsView.effectiveMalInspectorFilter === "ready"
                                                    ? settingsView._malToneBorder("accent")
                                                    : settingsView._malToneBorder("primary"))
                                            implicitHeight: inspectorFocusColumn.implicitHeight + 18

                                            Column {
                                                id: inspectorFocusColumn
                                                anchors.fill: parent
                                                anchors.margins: 10
                                                spacing: 4

                                                Text {
                                                    text: settingsView._malInspectorSectionTitle()
                                                    font.pixelSize: 11
                                                    font.bold: true
                                                    color: Color.mOnSurface
                                                }

                                                Text {
                                                    width: parent.width
                                                    text: settingsView._malInspectorSectionHint()
                                                    wrapMode: Text.Wrap
                                                    lineHeight: 1.35
                                                    font.pixelSize: 10
                                                    color: Color.mOnSurfaceVariant
                                                    opacity: 0.8
                                                }
                                            }
                                        }

                                        Column {
                                            width: parent.width
                                            spacing: 8

                                            Repeater {
                                                model: settingsView.filteredMalInspectorEntries.slice(0, 8)

                                                delegate: Rectangle {
                                                    width: parent.width
                                                    radius: 16
                                                    color: Qt.rgba(Color.mSurface.r, Color.mSurface.g, Color.mSurface.b, 0.9)
                                                    border.width: 1
                                                    border.color: Qt.rgba(Color.mOutlineVariant.r, Color.mOutlineVariant.g, Color.mOutlineVariant.b, 0.34)
                                                    implicitHeight: inspectorEntryColumn.implicitHeight + 18

                                                    Column {
                                                        id: inspectorEntryColumn
                                                        anchors.fill: parent
                                                        anchors.margins: 10
                                                        spacing: 6

                                                        Row {
                                                            width: parent.width
                                                            spacing: 8

                                                            Rectangle {
                                                                id: inspectorStatusChip
                                                                width: inspectorStatusLabel.implicitWidth + 16
                                                                height: 24
                                                                radius: 12
                                                                color: settingsView._malToneFill(modelData.badgeTone, true)
                                                                border.width: 1
                                                                border.color: settingsView._malToneBorder(modelData.badgeTone)

                                                                Text {
                                                                    id: inspectorStatusLabel
                                                                    anchors.centerIn: parent
                                                                    text: modelData.badge?.label || ""
                                                                    font.pixelSize: 10
                                                                    font.bold: true
                                                                    color: settingsView._malToneText(modelData.badgeTone)
                                                                }
                                                            }

                                                            Text {
                                                                width: Math.max(0, parent.width - inspectorStatusChip.width - 12)
                                                                text: modelData.title || "Untitled"
                                                                elide: Text.ElideRight
                                                                font.pixelSize: 11
                                                                font.bold: true
                                                                color: Color.mOnSurface
                                                            }
                                                        }

                                                        Text {
                                                            width: parent.width
                                                            wrapMode: Text.Wrap
                                                            lineHeight: 1.3
                                                            font.pixelSize: 10
                                                            color: Color.mOnSurfaceVariant
                                                            opacity: 0.78
                                                            text: settingsView._malInspectorMetaText(modelData)
                                                        }

                                                        Text {
                                                            width: parent.width
                                                            visible: String(settingsView._malInspectorDetailText(modelData)).length > 0
                                                            wrapMode: Text.Wrap
                                                            lineHeight: 1.3
                                                            font.pixelSize: 10
                                                            color: Color.mOnSurfaceVariant
                                                            opacity: 0.72
                                                            text: settingsView._malInspectorDetailText(modelData)
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        Text {
                                            visible: settingsView.filteredMalInspectorEntries.length === 0
                                            width: parent.width
                                            text: settingsView._malInspectorEmptyText()
                                            wrapMode: Text.Wrap
                                            lineHeight: 1.35
                                            font.pixelSize: 10
                                            color: Color.mOnSurfaceVariant
                                            opacity: 0.72
                                        }

                                        Text {
                                            readonly property int extraCount:
                                                Math.max(0, settingsView.filteredMalInspectorEntries.length - 8)
                                            visible: extraCount > 0
                                            text: "+" + String(extraCount) + " more title"
                                                + (extraCount === 1 ? "" : "s")
                                                + " in " + settingsView._malInspectorSectionTitle().toLowerCase()
                                            font.pixelSize: 10
                                            color: Color.mOnSurfaceVariant
                                            opacity: 0.72
                                        }
                                    }
                                }
                            }

                            Column {
                                visible: anime?.malSyncShowAdvanced ?? false
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
                                visible: anime?.malSyncShowAdvanced ?? false
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
                                visible: anime?.malSyncShowAdvanced ?? false
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
                                visible: anime?.malSyncShowAdvanced ?? false
                                spacing: 8

                                Text {
                                    text: "Manual Authorization Code"
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

                                Text {
                                    width: parent.width
                                    text: anime?.malSync?.autoPush
                                        ? "Auto Push sends local watch changes to MyAnimeList after a short delay. Pulls and imports never push back automatically."
                                        : "Manual means AnimeReloaded only updates MyAnimeList when you press Push To MAL."
                                    wrapMode: Text.Wrap
                                    lineHeight: 1.35
                                    font.pixelSize: 10
                                    color: Color.mOnSurfaceVariant
                                    opacity: 0.7
                                }
                            }

                            Flow {
                                width: parent.width
                                spacing: 10

                                ActionChip {
                                    text: anime?.malSync?.enabled ? "Reconnect MAL" : "Connect MAL"
                                    leadingText: "M"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.startMalBrowserAuth()
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

                                ActionChip {
                                    text: anime?.malSyncShowAdvanced ? "Hide Advanced" : "Advanced"
                                    leadingText: anime?.malSyncShowAdvanced ? "-" : "+"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.malSyncShowAdvanced = !anime.malSyncShowAdvanced
                                }
                            }

                            Text {
                                width: parent.width
                                text: "Flow: click Connect MAL, approve access in the browser, then AnimeReloaded captures the callback automatically. Pull merges progress and can import MAL-only titles that resolve to AniList. Push sends AnimeReloaded progress back out."
                                wrapMode: Text.Wrap
                                lineHeight: 1.35
                                font.pixelSize: 11
                                color: Color.mOnSurfaceVariant
                                opacity: 0.72
                            }

                            Text {
                                visible: !(anime?.malSyncShowAdvanced ?? false)
                                width: parent.width
                                text: "Advanced OAuth overrides stay hidden unless you need to debug a custom MAL app."
                                wrapMode: Text.Wrap
                                lineHeight: 1.35
                                font.pixelSize: 10
                                color: Color.mOnSurfaceVariant
                                opacity: 0.62
                            }

                            Flow {
                                visible: anime?.malSyncShowAdvanced ?? false
                                width: parent.width
                                spacing: 10

                                ActionChip {
                                    text: "Open Auth"
                                    leadingText: "↗"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.startMalAuth()
                                }

                                ActionChip {
                                    text: "Finish Manual Connect"
                                    leadingText: "✓"
                                    enabled: !(anime?.isMalSyncBusy ?? false)
                                    onClicked: if (anime) anime.exchangeMalAuthCode()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
