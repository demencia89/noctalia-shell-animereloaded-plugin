import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Widgets

ColumnLayout {
    id: root

    property var pluginApi: null
    property var defaults: pluginApi?.manifest?.metadata?.defaultSettings || ({})

    function _settingValue(key, fallback) {
        var value = pluginApi?.pluginSettings?.[key]
        return value !== undefined && value !== null ? value : fallback
    }

    property string barWidgetIconName:
        _settingValue("barWidgetIconName", defaults.barWidgetIconName || "device-tv")
    property string barWidgetText:
        _settingValue("barWidgetText", defaults.barWidgetText || "AnimeReloaded")
    property string barWidgetIconColor:
        _settingValue("barWidgetIconColor", defaults.barWidgetIconColor || "mPrimary")

    readonly property var colorOptions: [
        { key: "mPrimary", name: "Primary" },
        { key: "mSecondary", name: "Secondary" },
        { key: "mTertiary", name: "Tertiary" },
        { key: "mOnSurface", name: "On Surface" },
        { key: "mOnSurfaceVariant", name: "On Surface Variant" }
    ]

    function resetToDefaults() {
        root.barWidgetIconName = defaults.barWidgetIconName || "device-tv"
        root.barWidgetText = defaults.barWidgetText || "AnimeReloaded"
        root.barWidgetIconColor = defaults.barWidgetIconColor || "mPrimary"
    }

    spacing: Style.marginL

    NLabel {
        label: "Bar Widget"
        description: "Customize the bar button icon, label, and icon color."
    }

    RowLayout {
        spacing: Style.marginM

        Rectangle {
            Layout.preferredWidth: Math.max(160, previewRow.implicitWidth + Style.marginM * 2)
            Layout.preferredHeight: 42
            radius: Style.radiusL
            color: Style.capsuleColor
            border.color: Style.capsuleBorderColor
            border.width: Style.capsuleBorderWidth

            RowLayout {
                id: previewRow
                anchors.centerIn: parent
                spacing: Style.marginXS

                NIcon {
                    icon: root.barWidgetIconName
                    color: Color.resolveColorKey(root.barWidgetIconColor)
                }

                NText {
                    visible: root.barWidgetText.length > 0
                    text: root.barWidgetText
                    color: Color.mOnSurface
                }
            }
        }

        NButton {
            text: "Choose Icon"
            onClicked: iconPicker.open()
        }
    }

    NIconPicker {
        id: iconPicker
        initialIcon: root.barWidgetIconName
        onIconSelected: function(iconName) {
            root.barWidgetIconName = iconName
        }
    }

    NTextInput {
        Layout.fillWidth: true
        label: "Button Text"
        description: "Text shown next to the icon in the bar. Leave it empty for an icon-only button."
        placeholderText: "AnimeReloaded"
        text: root.barWidgetText
        onTextChanged: root.barWidgetText = text
    }

    NComboBox {
        Layout.fillWidth: true
        label: "Icon Color"
        description: "Choose one of the five theme colors for the bar icon."
        model: root.colorOptions
        currentKey: root.barWidgetIconColor
        onSelected: key => root.barWidgetIconColor = key
    }

    RowLayout {
        Layout.fillWidth: true

        Item {
            Layout.fillWidth: true
        }

        NButton {
            text: "Reset to Defaults"
            icon: "refresh"
            onClicked: root.resetToDefaults()
        }
    }

    function saveSettings() {
        if (!pluginApi) {
            Logger.e("AnimeReloaded", "Cannot save settings: pluginApi is null")
            return
        }

        pluginApi.pluginSettings.barWidgetIconName = root.barWidgetIconName
        pluginApi.pluginSettings.barWidgetText = root.barWidgetText
        pluginApi.pluginSettings.barWidgetIconColor = root.barWidgetIconColor
        pluginApi.saveSettings()
    }
}
